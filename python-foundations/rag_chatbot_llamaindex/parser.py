from llama_index.core.node_parser import SentenceSplitter


def parse_nodes(documents):

    splitter = SentenceSplitter(
        chunk_size=512,
        chunk_overlap=50
    )

    nodes = splitter.get_nodes_from_documents(documents)

    return nodes