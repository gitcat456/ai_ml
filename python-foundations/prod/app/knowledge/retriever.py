import logging
import re
from dataclasses import dataclass

from qdrant_client import QdrantClient
from qdrant_client.http import models

from app.config import (
    EMBEDDING_DIM,
    QDRANT_API_KEY,
    QDRANT_COLLECTION,
    QDRANT_URL,
)
from app.knowledge.embeddings import BaseEmbeddingProvider, get_embedding_provider

logger = logging.getLogger(__name__)


def format_document_title(filename: str | None) -> str:
    """Format a user-friendly document name without raw file extensions."""
    if not filename:
        return "EUSDA Document"
    clean = filename
    # Strip extensions
    clean = re.sub(r"\.(pdf|txt|md)$", "", clean, flags=re.IGNORECASE)
    lower = clean.lower()
    if "constitution" in lower:
        return "EUSDA Constitution"
    if "church_manual" in lower or "church manual" in lower:
        return "SDA Church Manual"
    # General cleanup: replace underscores/dashes with spaces, title case
    clean = re.sub(r"[_\-]+", " ", clean).strip()
    return clean.title() if clean.islower() else clean


def extract_structural_context(
    text: str, filename: str | None, page: int | None
) -> tuple[str, str | None, str | None, str | None, str]:
    """Extract Article, Section, Chapter, and a clean citation label."""
    doc_title = format_document_title(filename)
    article = None
    section = None
    chapter = None

    art_match = re.search(
        r"\b(ARTICLE\s+[0-9IVXLCDM]+(?::\s*[^\n\r]+|\b[^\n\r]*))",
        text,
        re.IGNORECASE,
    )
    if art_match:
        article = re.sub(r"\s+", " ", art_match.group(1)).strip()

    sec_match = re.search(
        r"\b(Section\s+[A-Z0-9]+(?::\s*[^\n\r]+|\b[^\n\r]*))",
        text,
        re.IGNORECASE,
    )
    if sec_match:
        section = re.sub(r"\s+", " ", sec_match.group(1)).strip()

    chap_match = re.search(
        r"\b(Chapter\s+[0-9IVXLCDM]+(?::\s*[^\n\r]+|\b[^\n\r]*))",
        text,
        re.IGNORECASE,
    )
    if chap_match:
        chapter = re.sub(r"\s+", " ", chap_match.group(1)).strip()

    parts = [doc_title]
    if chapter:
        c_short = re.search(r"Chapter\s+([0-9IVXLCDM]+)", chapter, re.IGNORECASE)
        parts.append(f"Ch. {c_short.group(1)}" if c_short else chapter)
    if article:
        a_short = re.search(r"ARTICLE\s+([0-9IVXLCDM]+)", article, re.IGNORECASE)
        parts.append(f"Art. {a_short.group(1)}" if a_short else article)
    if section:
        s_short = re.search(r"Section\s+([A-Z0-9]+)", section, re.IGNORECASE)
        parts.append(f"Sec. {s_short.group(1)}" if s_short else section)
    if page is not None:
        parts.append(f"p. {page}")

    citation_label = ", ".join(parts)
    return doc_title, article, section, chapter, citation_label


@dataclass(frozen=True)
class RetrievedChunk:
    text: str
    filename: str | None = None
    document_title: str | None = None
    article: str | None = None
    section: str | None = None
    chapter: str | None = None
    page: int | None = None
    score: float | None = None
    citation_label: str | None = None
    doc_type: str = "reference"


class KnowledgeRetriever:
    """
    Retrieves relevant organizational document chunks from Qdrant Cloud
    using Google Gemini embeddings.
    """

    def __init__(
        self,
        embedding_provider: BaseEmbeddingProvider | None = None,
        qdrant_client: QdrantClient | None = None,
        collection_name: str | None = None,
    ):
        self.embedding_provider = embedding_provider
        self.client = qdrant_client
        self.collection_name = collection_name or QDRANT_COLLECTION
        self._vector_name: str | None = None
        self._initialized = False

    def _load_index(self):
        """
        Initialize the embedding provider and Qdrant client connection.
        Verifies collection dimensions and vector naming.
        """
        if self._initialized:
            return

        if not self.embedding_provider:
            self.embedding_provider = get_embedding_provider()

        if not self.client:
            if not QDRANT_URL or not QDRANT_API_KEY:
                raise RuntimeError(
                    "QDRANT_URL and QDRANT_API_KEY must be set in environment."
                )
            self.client = QdrantClient(
                url=QDRANT_URL,
                api_key=QDRANT_API_KEY,
                timeout=20.0,
            )

        # Inspect collection configuration
        try:
            coll_info = self.client.get_collection(self.collection_name)
            vectors_config = coll_info.config.params.vectors

            # Check if vector configuration is a dict with named vectors or single VectorParams
            if isinstance(vectors_config, dict):
                # If there's an empty key '', it's the default unnamed vector
                if "" not in vectors_config and len(vectors_config) > 0:
                    self._vector_name = list(vectors_config.keys())[0]
                    v_params = vectors_config[self._vector_name]
                else:
                    v_params = vectors_config.get("")
            else:
                v_params = vectors_config

            if v_params and hasattr(v_params, "size"):
                if v_params.size != EMBEDDING_DIM:
                    logger.warning(
                        "Qdrant collection '%s' vector dimension (%d) does not match EMBEDDING_DIM (%d).",
                        self.collection_name,
                        v_params.size,
                        EMBEDDING_DIM,
                    )
            logger.info(
                "Connected to Qdrant Cloud collection '%s' (points: %d, vector_name: %s)",
                self.collection_name,
                coll_info.points_count or 0,
                self._vector_name or "<default>",
            )
        except Exception as exc:
            logger.warning(
                "Could not verify Qdrant collection '%s' at startup (%s). Will attempt retrieval on demand.",
                self.collection_name,
                exc,
            )

        self._initialized = True

    def retrieve(self, query: str, top_k: int = 8) -> list[RetrievedChunk]:
        """
        Retrieve top-k semantically relevant chunks from Qdrant Cloud.
        """
        self._load_index()

        if not query or not query.strip():
            return []

        # 1. Generate query embedding via Gemini
        query_vector = self.embedding_provider.embed_query(query)

        # 2. Query Qdrant Cloud
        try:
            # Query points
            if hasattr(self.client, "query_points"):
                response = self.client.query_points(
                    collection_name=self.collection_name,
                    query=query_vector,
                    using=self._vector_name,
                    limit=top_k,
                )
                points = response.points
            else:
                points = self.client.search(
                    collection_name=self.collection_name,
                    query_vector=(
                        (self._vector_name, query_vector)
                        if self._vector_name
                        else query_vector
                    ),
                    limit=top_k,
                )
        except Exception as exc:
            logger.error("Qdrant retrieval error: %s", exc)
            raise RuntimeError(f"Vector search failed: {exc}") from exc

        # 3. Parse retrieved points into RetrievedChunk objects
        results = []
        for point in points:
            payload = point.payload or {}
            content = payload.get("text") or ""
            raw_filename = payload.get("source") or payload.get("filename")
            raw_page = payload.get("page")

            try:
                page_num = int(raw_page) if raw_page is not None else None
            except (ValueError, TypeError):
                page_num = None

            # Fallback metadata extraction if not stored in payload
            doc_title = payload.get("document_title")
            article = payload.get("article")
            section = payload.get("section")
            chapter = payload.get("chapter")
            citation_label = payload.get("citation_label")
            doc_type = payload.get("doc_type")
            if not doc_type:
                # Fallback: .txt or .md files are general knowledge, .pdf are reference
                doc_type = (
                    "general_knowledge"
                    if (raw_filename and raw_filename.lower().endswith((".txt", ".md")))
                    else "reference"
                )

            if not doc_title or not citation_label:
                (
                    extracted_doc_title,
                    extracted_art,
                    extracted_sec,
                    extracted_chap,
                    extracted_label,
                ) = extract_structural_context(content, raw_filename, page_num)
                doc_title = doc_title or extracted_doc_title
                article = article or extracted_art
                section = section or extracted_sec
                chapter = chapter or extracted_chap
                citation_label = citation_label or extracted_label

            clean_filename = format_document_title(raw_filename)

            results.append(
                RetrievedChunk(
                    text=content,
                    filename=clean_filename,
                    document_title=doc_title,
                    article=article,
                    section=section,
                    chapter=chapter,
                    page=page_num,
                    score=float(point.score) if point.score is not None else None,
                    citation_label=citation_label,
                    doc_type=doc_type,
                )
            )

        return results