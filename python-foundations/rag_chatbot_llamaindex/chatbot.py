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


query_engine = index.as_query_engine()


while True:

    question = input("\nYou: ")

    if question.lower() in ["quit", "exit", "bye"]:
        print("Goodbye!")
        break


    response = query_engine.query(question)

    print("\nAssistant:", response)