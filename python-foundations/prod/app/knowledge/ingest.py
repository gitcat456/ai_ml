import logging
import os
import re
import sys
import uuid
from pathlib import Path
from typing import Generator

from dotenv import load_dotenv
from qdrant_client import QdrantClient
from qdrant_client.http import models

# Ensure project root is in sys.path when run directly
BASE_DIR = Path(__file__).resolve().parents[2]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

# Load environment from prod/.env
load_dotenv(BASE_DIR / ".env")

from app.config import (
    EMBEDDING_DIM,
    QDRANT_API_KEY,
    QDRANT_COLLECTION,
    QDRANT_URL,
)
from app.knowledge.embeddings import get_embedding_provider
from app.knowledge.retriever import (
    extract_structural_context,
    format_document_title,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("ingest")

DOCUMENTS_DIR = BASE_DIR / "data" / "documents"


def generate_deterministic_point_id(source_name: str, chunk_index: int) -> str:
    """Generate a consistent, deterministic UUIDv5 for a document chunk."""
    unique_key = f"{source_name}::chunk_{chunk_index}"
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, unique_key))


def split_text_into_chunks(
    text: str, chunk_size: int = 600, overlap: int = 100
) -> list[str]:
    """
    Split text into overlapping chunks, respecting paragraph and sentence boundaries.
    """
    if not text or not text.strip():
        return []

    # Clean multiple spaces and form feeds
    cleaned = re.sub(r"\r\n", "\n", text)
    cleaned = re.sub(r"[ \t]+", " ", cleaned)

    paragraphs = cleaned.split("\n\n")
    chunks = []
    current_chunk = ""

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue

        if len(current_chunk) + len(para) + 2 <= chunk_size:
            current_chunk = (
                f"{current_chunk}\n\n{para}".strip() if current_chunk else para
            )
        else:
            if current_chunk:
                chunks.append(current_chunk)
                # Keep overlap from the end of the current chunk
                overlap_text = current_chunk[-overlap:] if len(current_chunk) > overlap else ""
                current_chunk = f"{overlap_text}\n\n{para}".strip() if overlap_text else para
            else:
                # Large paragraph: split by sentences or hard chunks
                sentences = re.split(r"(?<=[.?!])\s+", para)
                for sentence in sentences:
                    sentence = sentence.strip()
                    if not sentence:
                        continue
                    if len(current_chunk) + len(sentence) + 1 <= chunk_size:
                        current_chunk = (
                            f"{current_chunk} {sentence}".strip()
                            if current_chunk
                            else sentence
                        )
                    else:
                        if current_chunk:
                            chunks.append(current_chunk)
                        current_chunk = sentence

    if current_chunk:
        chunks.append(current_chunk)

    return [c.strip() for c in chunks if len(c.strip()) > 20]


def load_raw_documents() -> list[dict]:
    """
    Load raw files (.pdf, .txt, .md) from data/documents/.
    Returns a list of page/document records:
    [{"source": filename, "page": page_number, "text": text_content}]
    """
    if not DOCUMENTS_DIR.exists():
        raise RuntimeError(f"Documents directory not found: {DOCUMENTS_DIR}")

    supported_exts = {".pdf", ".txt", ".md"}
    raw_files = [
        f for f in DOCUMENTS_DIR.rglob("*")
        if f.is_file() and f.suffix.lower() in supported_exts
    ]

    if not raw_files:
        raise RuntimeError(
            f"No supported documents (.pdf, .txt, .md) found in: {DOCUMENTS_DIR}"
        )

    records = []

    for file_path in raw_files:
        filename = file_path.name
        ext = file_path.suffix.lower()

        logger.info("Reading document: %s", filename)

        if ext == ".pdf":
            try:
                import pypdf

                reader = pypdf.PdfReader(str(file_path))
                for page_idx, page in enumerate(reader.pages, start=1):
                    page_text = page.extract_text() or ""
                    if page_text.strip():
                        records.append({
                            "source": filename,
                            "page": page_idx,
                            "text": page_text,
                        })
            except ImportError:
                raise RuntimeError(
                    "Package 'pypdf' is required for PDF ingestion. "
                    "Install it via: pip install pypdf"
                )
        else:
            try:
                content = file_path.read_text(encoding="utf-8")
                if content.strip():
                    records.append({
                        "source": filename,
                        "page": 1,
                        "text": content,
                    })
            except Exception as exc:
                logger.warning("Could not read text file %s: %s", filename, exc)

    logger.info("Loaded %d page/document sections from %d files.", len(records), len(raw_files))
    return records


def prepare_chunks(records: list[dict]) -> list[dict]:
    """
    Chunk documents and attach structured metadata (article, section, chapter, citation).
    """
    prepared_chunks = []
    chunk_counter = 0

    for rec in records:
        source = rec["source"]
        page = rec.get("page")
        page_text = rec["text"]

        chunks = split_text_into_chunks(page_text, chunk_size=600, overlap=100)

        for chunk_text in chunks:
            chunk_counter += 1
            doc_title, article, section, chapter, citation_label = (
                extract_structural_context(chunk_text, source, page)
            )

            point_id = generate_deterministic_point_id(source, chunk_counter)

            payload = {
                "text": chunk_text,
                "source": source,
                "filename": format_document_title(source),
                "document_title": doc_title,
                "page": page,
                "article": article,
                "section": section,
                "chapter": chapter,
                "citation_label": citation_label,
            }

            prepared_chunks.append({
                "id": point_id,
                "text": chunk_text,
                "payload": payload,
            })

    logger.info("Created %d enriched chunks with deterministic IDs.", len(prepared_chunks))
    return prepared_chunks


def ensure_collection(client: QdrantClient, collection_name: str, dim: int):
    """Ensure the target Qdrant collection exists with proper dimensions & cosine distance."""
    try:
        coll = client.get_collection(collection_name)
        logger.info(
            "Found existing Qdrant collection '%s' with %d points.",
            collection_name,
            coll.points_count or 0,
        )
    except Exception:
        logger.info(
            "Collection '%s' does not exist. Creating collection (size=%d, distance=Cosine)...",
            collection_name,
            dim,
        )
        client.create_collection(
            collection_name=collection_name,
            vectors_config=models.VectorParams(
                size=dim,
                distance=models.Distance.COSINE,
            ),
        )


def ingest_to_qdrant(
    batch_size: int = 50,
):
    """
    Main ingestion execution:
    1. Read local documents
    2. Chunk & extract metadata
    3. Generate Gemini embeddings
    4. Upsert to Qdrant Cloud
    """
    if not QDRANT_URL or not QDRANT_API_KEY:
        raise RuntimeError("QDRANT_URL and QDRANT_API_KEY must be set in .env")

    logger.info("Initializing embedding provider (Gemini)...")
    provider = get_embedding_provider()

    logger.info("Connecting to Qdrant Cloud (%s)...", QDRANT_URL)
    client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY, timeout=30.0)

    # 1. Ensure collection exists
    ensure_collection(client, QDRANT_COLLECTION, EMBEDDING_DIM)

    # 2. Load and chunk documents
    records = load_raw_documents()
    chunks = prepare_chunks(records)

    if not chunks:
        logger.warning("No chunks generated. Ingestion finished.")
        return

    # 3. Generate embeddings and upsert in batches
    total = len(chunks)
    logger.info("Generating embeddings and upserting %d chunks in batches of %d...", total, batch_size)

    for i in range(0, total, batch_size):
        batch = chunks[i : i + batch_size]
        texts = [item["text"] for item in batch]

        logger.info("Embedding batch %d to %d of %d...", i + 1, min(i + batch_size, total), total)
        vectors = provider.embed_documents(texts)

        points = [
            models.PointStruct(
                id=item["id"],
                vector=vec,
                payload=item["payload"],
            )
            for item, vec in zip(batch, vectors)
        ]

        logger.info("Upserting %d points to collection '%s'...", len(points), QDRANT_COLLECTION)
        client.upsert(
            collection_name=QDRANT_COLLECTION,
            points=points,
            wait=True,
        )

    # 4. Final verification
    coll_info = client.get_collection(QDRANT_COLLECTION)
    logger.info(
        "Ingestion complete! Total points in collection '%s': %d",
        QDRANT_COLLECTION,
        coll_info.points_count or 0,
    )


if __name__ == "__main__":
    try:
        ingest_to_qdrant()
    except Exception as exc:
        logger.error("Ingestion failed: %s", exc)
        sys.exit(1)