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
    Split documents into overlapping text chunks and enrich with structural metadata.
    """
    from app.knowledge.retriever import extract_structural_context, format_document_title

    splitter = SentenceSplitter(
        chunk_size=512,
        chunk_overlap=80,
    )

    nodes = splitter.get_nodes_from_documents(
        documents,
        show_progress=True,
    )

    for node in nodes:
        raw_filename = node.metadata.get("file_name") or node.metadata.get("filename")
        page_label = node.metadata.get("page_label")
        try:
            page_num = int(page_label) if page_label is not None else None
        except (ValueError, TypeError):
            page_num = None

        doc_title, article, section, chapter, citation_label = extract_structural_context(
            node.get_content(), raw_filename, page_num
        )

        node.metadata["clean_filename"] = format_document_title(raw_filename)
        node.metadata["document_title"] = doc_title
        if article:
            node.metadata["article"] = article
        if section:
            node.metadata["section"] = section
        if chapter:
            node.metadata["chapter"] = chapter
        if citation_label:
            node.metadata["citation_label"] = citation_label

    print(f"Created {len(nodes)} chunks with structural metadata.")

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