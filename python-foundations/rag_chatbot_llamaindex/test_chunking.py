from llama_index.core import SimpleDirectoryReader
from llama_index.core.node_parser import SentenceSplitter

documents = SimpleDirectoryReader("documents").load_data()

splitter = SentenceSplitter(
    chunk_size=512,
    chunk_overlap=50
)

nodes = splitter.get_nodes_from_documents(documents)

print("Documents:", len(documents))
print("Nodes:", len(nodes))

for i, node in enumerate(nodes[:5], start=1):
    print(f"\n--- NODE {i} ---")
    print("Length:", len(node.text))
    print("Source:", node.metadata.get("file_name"))
    print("Page:", node.metadata.get("page_label"))
    print(node.text[:500])
    
for i, node in enumerate(nodes, start=1):
    print(
        f"Node {i}: "
        f"chars={len(node.text)}, "
        f"source={node.metadata.get('file_name')}, "
        f"page={node.metadata.get('page_label')}"
    )