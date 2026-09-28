from pathlib import Path

from llama_index.core import (
    Settings,
    SimpleDirectoryReader,
    VectorStoreIndex,
)
from llama_index.core.node_parser import SentenceSplitter
from llama_index.embeddings.huggingface import HuggingFaceEmbedding

from app.config import EMBEDDING_MODEL


# Project directories
BASE_DIR = Path(__file__).resolve().parents[2]

DOCUMENTS_DIR = BASE_DIR / "data" / "documents"
STORAGE_DIR = BASE_DIR / "storage"


def load_documents():
    """
    Load supported documents from the documents directory.
    """

    if not DOCUMENTS_DIR.exists():
        raise RuntimeError(
            f"Documents directory not found: {DOCUMENTS_DIR}"
        )

    reader = SimpleDirectoryReader(
        input_dir=str(DOCUMENTS_DIR),
        recursive=True,
        required_exts=[".pdf", ".txt", ".md"],
        filename_as_id=True,
    )

    documents = reader.load_data()

    if not documents:
        raise RuntimeError(
            "No documents found. Add PDF, TXT, or MD files "
            "to data/documents/."
        )

    print(f"Loaded {len(documents)} document pages or files.")

    return documents


def configure_embedding():
    """
    Configure the local embedding model.
    """

    embed_model = HuggingFaceEmbedding(
        model_name=EMBEDDING_MODEL,
    )

    Settings.embed_model = embed_model

    return embed_model


def chunk_documents(documents):
    """
    Split documents into overlapping text chunks.
    """

    splitter = SentenceSplitter(
        chunk_size=512,
        chunk_overlap=80,
    )

    nodes = splitter.get_nodes_from_documents(
        documents,
        show_progress=True,
    )

    print(f"Created {len(nodes)} chunks.")

    return nodes


def build_and_persist_index(nodes):
    """
    Generate embeddings, build the vector index,
    and persist it to disk.
    """

    index = VectorStoreIndex(
        nodes,
        show_progress=True,
    )

    STORAGE_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    index.storage_context.persist(
        persist_dir=str(STORAGE_DIR)
    )

    print(f"Index persisted to: {STORAGE_DIR}")

    return index


def main():
    print("Starting document ingestion...")

    documents = load_documents()

    configure_embedding()

    nodes = chunk_documents(documents)

    build_and_persist_index(nodes)

    print("Document ingestion completed successfully.")


if __name__ == "__main__":
    main()