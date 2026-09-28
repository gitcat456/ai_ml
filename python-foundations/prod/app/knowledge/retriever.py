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


@dataclass(frozen=True)
class RetrievedChunk:
    text: str
    filename: str | None
    page: int | None
    score: float | None


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
            similarity_top_k=10,
        )

        self.reranker = SentenceTransformerRerank(
            model=RERANKER_MODEL,
            top_n=5,
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

            results.append(
                RetrievedChunk(
                    text=node.get_content(),
                    filename=(
                        metadata.get("file_name")
                        or metadata.get("filename")
                    ),
                    page=metadata.get("page_label"),
                    score=(
                        float(item.score)
                        if item.score is not None
                        else None
                    ),
                )
            )

        return results