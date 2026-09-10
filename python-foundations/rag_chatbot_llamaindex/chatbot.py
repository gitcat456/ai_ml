from llama_index.core import (
    StorageContext,
    load_index_from_storage
)

import settings


print("Loading existing index...")

storage_context = StorageContext.from_defaults(
    persist_dir="./storage"
)

index = load_index_from_storage(
    storage_context
)

print("Index loaded!")

retriever = index.as_retriever(
    similarity_top_k=3
)

query_engine = index.as_query_engine(
    similarity_top_k=3
)


while True:

    question = input("\nYou: ")

    if question.lower() in ["quit", "exit", "bye"]:
        print("Goodbye!")
        break
    
    # metadata and real source attribution
    nodes = retriever.retrieve(question)

    print("\n--- Retrieved Sources ---")

    for i, node in enumerate(nodes, start=1):
        print(f"\n--- RESULT {i} ---")
        print("Score:", node.score)
        print("Source:", node.metadata.get("file_name"))
        print("Page:", node.metadata.get("page_label"))
        print(node.text[:300])

        response = query_engine.query(question)

    print("\n--- Answer ---")
    print(response)  