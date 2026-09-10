from llama_index.core import SimpleDirectoryReader
from llama_index.readers.file import PDFReader


def load_documents():

    reader = PDFReader()

    documents = SimpleDirectoryReader(
        "documents",
        file_extractor={
            ".pdf": reader
        }
    ).load_data()

    return documents