from index_builder import build_index
from llama_index.core import StorageContext

print("Creating index...")

index = build_index()

print("Saving index...")

index.storage_context.persist(
    persist_dir="./storage"
)

print("Done!")