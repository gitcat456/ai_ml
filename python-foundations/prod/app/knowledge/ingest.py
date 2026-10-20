import hashlib
import logging
import os
import re
import sys
import time
import uuid
from pathlib import Path

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


class DailyQuotaExhaustedError(Exception):
    """Raised when Gemini API daily quota is reached."""
    pass


def generate_deterministic_point_id(source_name: str, chunk_index: int) -> str:
    """Generate a consistent, deterministic UUIDv5 for a document chunk."""
    unique_key = f"{source_name}::chunk_{chunk_index}"
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, unique_key))


def compute_content_hash(text: str) -> str:
    """Compute SHA-256 hash of chunk text to detect content changes."""
    return hashlib.sha256(text.strip().encode("utf-8")).hexdigest()


def split_text_into_chunks(
    text: str, chunk_size: int = 600, overlap: int = 100
) -> list[str]:
    """
    Split text into overlapping chunks, respecting paragraph and sentence boundaries.
    """
    if not text or not text.strip():
        return []

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
                overlap_text = current_chunk[-overlap:] if len(current_chunk) > overlap else ""
                current_chunk = f"{overlap_text}\n\n{para}".strip() if overlap_text else para
            else:
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
    [{"source": filename, "page": page_number, "text": text_content, "doc_type": str}]
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
        doc_type = "reference" if ext == ".pdf" else "general_knowledge"

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
                            "doc_type": doc_type,
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
                        "doc_type": doc_type,
                    })
            except Exception as exc:
                logger.warning("Could not read text file %s: %s", filename, exc)

    logger.info("Loaded %d page/document sections from %d files.", len(records), len(raw_files))
    return records


def prepare_chunks(records: list[dict]) -> list[dict]:
    """
    Chunk documents and attach structured metadata including active chapter, article,
    section, and SHA-256 content_hash across sequential document pages.
    """
    prepared_chunks = []
    chunk_counter = 0

    current_source = None
    active_chapter = None
    active_article = None
    active_section = None

    for rec in records:
        source = rec["source"]
        page = rec.get("page")
        page_text = rec["text"]
        doc_type = rec.get("doc_type", "reference")

        # When transitioning to a new document, reset active structural context
        if source != current_source:
            current_source = source
            active_chapter = None
            active_article = None
            active_section = None

        # Inspect the entire page text first for any chapter/article/section headers
        _, p_art, p_sec, p_chap, _ = extract_structural_context(page_text, source, page)
        if p_chap:
            active_chapter = p_chap
        if p_art:
            active_article = p_art
            active_section = None  # Reset section on new article
        if p_sec:
            active_section = p_sec

        chunks = split_text_into_chunks(page_text, chunk_size=600, overlap=100)

        for chunk_text in chunks:
            chunk_counter += 1

            # Extract any chunk-local structural header
            doc_title, chunk_art, chunk_sec, chunk_chap, _ = extract_structural_context(
                chunk_text, source, page
            )

            # Update active context if the chunk itself begins with a new header
            if chunk_chap:
                active_chapter = chunk_chap
            if chunk_art:
                active_article = chunk_art
                active_section = None
            if chunk_sec:
                active_section = chunk_sec

            resolved_chapter = chunk_chap or active_chapter
            resolved_article = chunk_art or active_article
            resolved_section = chunk_sec or active_section

            # Build enriched citation label
            parts = [doc_title]
            if resolved_chapter:
                c_short = re.search(r"Chapter\s+([0-9IVXLCDM]+)", resolved_chapter, re.IGNORECASE)
                parts.append(f"Ch. {c_short.group(1)}" if c_short else resolved_chapter)
            if resolved_article:
                a_short = re.search(r"ARTICLE\s+([0-9IVXLCDM]+)", resolved_article, re.IGNORECASE)
                parts.append(f"Art. {a_short.group(1)}" if a_short else resolved_article)
            if resolved_section:
                s_short = re.search(r"Section\s+([A-Z0-9]+)", resolved_section, re.IGNORECASE)
                parts.append(f"Sec. {s_short.group(1)}" if s_short else resolved_section)
            if page is not None:
                parts.append(f"p. {page}")

            citation_label = ", ".join(parts)

            point_id = generate_deterministic_point_id(source, chunk_counter)
            content_hash = compute_content_hash(chunk_text)

            payload = {
                "text": chunk_text,
                "source": source,
                "filename": format_document_title(source),
                "document_title": doc_title,
                "doc_type": doc_type,
                "page": page,
                "article": resolved_article,
                "section": resolved_section,
                "chapter": resolved_chapter,
                "citation_label": citation_label,
                "content_hash": content_hash,
            }

            prepared_chunks.append({
                "id": point_id,
                "text": chunk_text,
                "payload": payload,
            })

    logger.info("Created %d enriched chunks with active structural metadata & content hashes.", len(prepared_chunks))
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


def inspect_gemini_error(exc: Exception) -> tuple[bool, float | None]:
    """
    Examines a Gemini API exception to determine:
    1. is_daily_quota: True if daily limit reached (stop immediately).
    2. retry_delay: Server-recommended delay in seconds from RetryInfo / headers / message.
    """
    exc_str = str(exc).lower()

    # Check for daily quota indicators
    is_daily = bool(re.search(r"\b(per\s*day|daily|requests_per_day|perday)\b", exc_str))

    details = getattr(exc, "details", None)
    if isinstance(details, dict):
        details_str = str(details).lower()
        if "per_day" in details_str or "per day" in details_str or "daily" in details_str:
            is_daily = True

    # Check for retry delay provided by Google API
    retry_delay = None
    if isinstance(details, dict):
        # Look for type.googleapis.com/google.rpc.RetryInfo
        err_dict = details.get("error", details)
        rpc_details = err_dict.get("details", []) if isinstance(err_dict, dict) else []
        for item in rpc_details:
            if isinstance(item, dict) and "RetryInfo" in item.get("@type", ""):
                delay_val = item.get("retryDelay")
                if delay_val:
                    # Format: "47.452s" or "47s"
                    delay_match = re.search(r"([0-9]+(?:\.[0-9]+)?)", str(delay_val))
                    if delay_match:
                        retry_delay = float(delay_match.group(1))
                        break

    # Check response headers if present
    response = getattr(exc, "response", None)
    if response and hasattr(response, "headers") and retry_delay is None:
        retry_header = response.headers.get("retry-after")
        if retry_header:
            try:
                retry_delay = float(retry_header)
            except (ValueError, TypeError):
                pass

    # Regex fallback from error message string: e.g. "retry in 47.4s"
    if retry_delay is None:
        m = re.search(r"retry\s+in\s+([0-9]+(?:\.[0-9]+)?)\s*s", exc_str)
        if m:
            retry_delay = float(m.group(1))

    return is_daily, retry_delay


def embed_batch_with_retry(
    provider, texts: list[str], max_retries: int = 3, initial_backoff: float = 5.0
) -> list[list[float]]:
    """
    Embeds a single batch of texts with immediate daily-quota abort and server-delay backoff.
    """
    backoff = initial_backoff

    for attempt in range(1, max_retries + 1):
        try:
            return provider.embed_documents(texts)
        except Exception as exc:
            is_daily, retry_delay = inspect_gemini_error(exc)

            if is_daily:
                raise DailyQuotaExhaustedError(
                    f"Gemini API DAILY quota exhausted: {exc}"
                ) from exc

            is_rate_limit = "429" in str(exc) or "resource_exhausted" in str(exc).lower()

            if is_rate_limit and attempt < max_retries:
                wait_sec = (retry_delay + 1.0) if retry_delay else backoff
                logger.warning(
                    "Rate limit hit on attempt %d/%d. Waiting %.1fs before retrying...",
                    attempt,
                    max_retries,
                    wait_sec,
                )
                time.sleep(wait_sec)
                backoff = max(backoff * 2, 5.0)
            elif attempt < max_retries:
                logger.warning(
                    "Embedding error on attempt %d/%d (%s). Retrying in %.1fs...",
                    attempt,
                    max_retries,
                    exc,
                    backoff,
                )
                time.sleep(backoff)
                backoff = max(backoff * 2, 5.0)
            else:
                raise RuntimeError(
                    f"Failed to embed batch after {max_retries} attempts: {exc}"
                ) from exc


def fetch_existing_qdrant_points(
    client: QdrantClient, collection_name: str, point_ids: list[str], batch_size: int = 100
) -> dict[str, dict]:
    """
    Retrieves existing points by ID in batches. Returns {id: payload}.
    """
    existing: dict[str, dict] = {}
    total = len(point_ids)

    for i in range(0, total, batch_size):
        id_batch = point_ids[i : i + batch_size]
        try:
            records = client.retrieve(
                collection_name=collection_name,
                ids=id_batch,
                with_payload=True,
                with_vectors=False,
            )
            for rec in records:
                existing[str(rec.id)] = rec.payload or {}
        except Exception as exc:
            logger.warning("Error fetching existing points batch %d-%d: %s", i, min(i + batch_size, total), exc)

    return existing


def print_summary(total: int, skipped: int, embedded: int, remaining: int):
    """Print a clean execution summary of the ingestion run."""
    logger.info("=" * 60)
    logger.info("INGESTION SUMMARY:")
    logger.info("  Total chunks:    %d", total)
    logger.info("  Skipped:         %d (already present & unchanged)", skipped)
    logger.info("  Embedded:        %d (new or updated)", embedded)
    logger.info("  Remaining:       %d", remaining)
    logger.info("=" * 60)


def ingest_to_qdrant():
    """
    Smart incremental ingestion execution:
    1. Read local documents & prepare chunks with content_hash.
    2. Check existing IDs and hashes in Qdrant (retrieves by ID in batches).
    3. Skip chunks whose content has not changed.
    4. Embed only missing/changed chunks with configurable throttling.
    5. Upsert after EACH batch to save progress immediately.
    6. Stop immediately if daily quota is exhausted.
    7. Print summary at the end.
    """
    if not QDRANT_URL or not QDRANT_API_KEY:
        raise RuntimeError("QDRANT_URL and QDRANT_API_KEY must be set in .env")

    # Configurable batch size & delay between batches
    batch_size = int(os.getenv("EMBED_BATCH_SIZE", "10"))
    delay_seconds = float(os.getenv("EMBED_DELAY_SECONDS", "3.0"))

    logger.info(
        "Ingestion config: EMBED_BATCH_SIZE=%d, EMBED_DELAY_SECONDS=%.1fs",
        batch_size,
        delay_seconds,
    )

    logger.info("Initializing embedding provider (Gemini)...")
    provider = get_embedding_provider()

    logger.info("Connecting to Qdrant Cloud (%s)...", QDRANT_URL)
    client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY, timeout=30.0)

    # 1. Ensure collection exists
    ensure_collection(client, QDRANT_COLLECTION, EMBEDDING_DIM)

    # 2. Load and chunk documents
    records = load_raw_documents()
    chunks = prepare_chunks(records)
    total_chunks = len(chunks)

    if not chunks:
        logger.warning("No chunks generated. Ingestion finished.")
        print_summary(total=0, skipped=0, embedded=0, remaining=0)
        return

    # 3. Check existing points in Qdrant by ID
    logger.info("Checking %d chunk IDs against Qdrant collection '%s'...", total_chunks, QDRANT_COLLECTION)
    all_ids = [c["id"] for c in chunks]
    existing_points = fetch_existing_qdrant_points(client, QDRANT_COLLECTION, all_ids)
    logger.info("Found %d matching point IDs in Qdrant.", len(existing_points))

    # 4. Filter chunks: skip unchanged, collect missing or modified
    chunks_to_embed = []
    skipped_count = 0

    for chunk in chunks:
        cid = chunk["id"]
        chash = chunk["payload"]["content_hash"]
        ctext = chunk["text"]

        if cid in existing_points:
            stored_payload = existing_points[cid]
            stored_hash = stored_payload.get("content_hash")

            if stored_hash is not None:
                if stored_hash == chash:
                    skipped_count += 1
                    continue
                else:
                    # Content changed -> re-embed
                    chunks_to_embed.append(chunk)
            else:
                # Existing point without content_hash:
                # If stored text matches current chunk text, content is identical -> skip!
                if stored_payload.get("text") == ctext:
                    skipped_count += 1
                    continue
                else:
                    # Text differed or was missing -> re-embed
                    chunks_to_embed.append(chunk)
        else:
            # Missing in Qdrant -> new chunk to embed
            chunks_to_embed.append(chunk)

    logger.info(
        "Differential analysis: %d to embed (%d new/changed), %d skipped (already up-to-date).",
        len(chunks_to_embed),
        len(chunks_to_embed),
        skipped_count,
    )

    if not chunks_to_embed:
        logger.info("All chunks are already up-to-date in Qdrant! Nothing to embed.")
        print_summary(total=total_chunks, skipped=skipped_count, embedded=0, remaining=0)
        return

    # 5. Embed and upsert incrementally in batches
    embedded_count = 0
    to_embed_total = len(chunks_to_embed)

    try:
        for i in range(0, to_embed_total, batch_size):
            batch = chunks_to_embed[i : i + batch_size]
            texts = [item["text"] for item in batch]

            logger.info(
                "Embedding batch %d-%d of %d new/changed chunks...",
                i + 1,
                min(i + batch_size, to_embed_total),
                to_embed_total,
            )

            vectors = embed_batch_with_retry(provider, texts)

            points = [
                models.PointStruct(
                    id=item["id"],
                    vector=vec,
                    payload=item["payload"],
                )
                for item, vec in zip(batch, vectors)
            ]

            client.upsert(
                collection_name=QDRANT_COLLECTION,
                points=points,
                wait=True,
            )

            embedded_count += len(points)
            logger.info("Upserted batch of %d points to Qdrant (progress: %d/%d).", len(points), embedded_count, to_embed_total)

            # Throttle between batches if more remain
            if i + batch_size < to_embed_total and delay_seconds > 0:
                time.sleep(delay_seconds)

    except DailyQuotaExhaustedError as dq_exc:
        remaining = to_embed_total - embedded_count
        logger.critical(
            "DAILY QUOTA REACHED: Embedding halted immediately. Progress saved in Qdrant.\n%s",
            dq_exc,
        )
        print_summary(
            total=total_chunks,
            skipped=skipped_count,
            embedded=embedded_count,
            remaining=remaining,
        )
        sys.exit(1)
    except Exception as exc:
        remaining = to_embed_total - embedded_count
        logger.error("Ingestion failed: %s", exc)
        print_summary(
            total=total_chunks,
            skipped=skipped_count,
            embedded=embedded_count,
            remaining=remaining,
        )
        sys.exit(1)

    # 6. Final verification & summary
    coll_info = client.get_collection(QDRANT_COLLECTION)
    logger.info("Total points currently in collection '%s': %d", QDRANT_COLLECTION, coll_info.points_count or 0)

    print_summary(
        total=total_chunks,
        skipped=skipped_count,
        embedded=embedded_count,
        remaining=0,
    )


if __name__ == "__main__":
    try:
        ingest_to_qdrant()
    except Exception as exc:
        logger.error("Ingestion failed: %s", exc)
        sys.exit(1)