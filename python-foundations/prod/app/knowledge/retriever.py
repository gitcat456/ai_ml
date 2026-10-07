import re
from dataclasses import dataclass
from pathlib import Path

from llama_index.core import (
    Settings,
    StorageContext,
    load_index_from_storage,
)
from llama_index.core.schema import NodeWithScore
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.core.postprocessor import SentenceTransformerRerank

from app.config import (
    EMBEDDING_MODEL,
    RERANKER_MODEL,
)


BASE_DIR = Path(__file__).resolve().parents[2]
STORAGE_DIR = BASE_DIR / "storage"


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


class KnowledgeRetriever:
    """
    Retrieves and reranks relevant organizational document chunks.
    """

    def __init__(self):
        self.index = None
        self.retriever = None
        self.reranker = None

    def _load_index(self):
        """
        Load the persisted index only when retrieval is first requested.
        """

        if self.index is not None:
            return

        if not STORAGE_DIR.exists():
            raise RuntimeError(
                "Knowledge index does not exist. "
                "Run the document ingestion pipeline first."
            )

        embed_model = HuggingFaceEmbedding(
            model_name=EMBEDDING_MODEL,
        )

        Settings.embed_model = embed_model

        storage_context = StorageContext.from_defaults(
            persist_dir=str(STORAGE_DIR)
        )

        self.index = load_index_from_storage(
            storage_context
        )

        self.retriever = self.index.as_retriever(
            similarity_top_k=15,
        )

        self.reranker = SentenceTransformerRerank(
            model=RERANKER_MODEL,
            top_n=7,
        )

    def retrieve(self, query: str) -> list[RetrievedChunk]:
        """
        Retrieve candidate chunks and rerank them for a query.
        """

        self._load_index()

        nodes: list[NodeWithScore] = self.retriever.retrieve(
            query
        )

        reranked_nodes = self.reranker.postprocess_nodes(
            nodes,
            query_str=query,
        )

        results = []

        for item in reranked_nodes:
            node = item.node
            metadata = node.metadata or {}
            raw_filename = (
                metadata.get("file_name")
                or metadata.get("filename")
            )
            raw_page = metadata.get("page_label")
            try:
                page_num = int(raw_page) if raw_page is not None else None
            except (ValueError, TypeError):
                page_num = None

            content = node.get_content()
            doc_title, article, section, chapter, citation_label = (
                extract_structural_context(content, raw_filename, page_num)
            )

            # Clean filename to never expose .pdf
            clean_filename = format_document_title(raw_filename)

            results.append(
                RetrievedChunk(
                    text=content,
                    filename=clean_filename,
                    document_title=doc_title,
                    article=article or metadata.get("article"),
                    section=section or metadata.get("section"),
                    chapter=chapter or metadata.get("chapter"),
                    page=page_num,
                    score=(
                        float(item.score)
                        if item.score is not None
                        else None
                    ),
                    citation_label=citation_label,
                )
            )

        return results