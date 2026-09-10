from llama_index.core import VectorStoreIndex

from loaders import load_documents
import settings 


def build_index():

    documents = load_documents()

    index = VectorStoreIndex.from_documents(documents)

    return index