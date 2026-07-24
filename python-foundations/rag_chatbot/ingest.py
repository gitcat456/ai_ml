import os
import chromadb

from loaders import load_document
from chunker import chunk_text
from embeddings import embed

# ------------------------
# Connect to ChromaDB
# ------------------------

client = chromadb.PersistentClient(path="./database")

collection = client.get_or_create_collection(
    name="knowledge_base"
)

# Optional: clear old data before rebuilding
collection.delete(where={})

documents_folder = "documents"

chunk_counter = 1

# ------------------------
# Loop through every file
# ------------------------

for filename in os.listdir(documents_folder):

    filepath = os.path.join(
        documents_folder,
        filename
    )

    print(f"Processing {filename}...")

    text = load_document(filepath)

    chunks = chunk_text(text)

    for chunk in chunks:

        collection.add(
            ids=[f"chunk_{chunk_counter}"],
            documents=[chunk],
            embeddings=[embed(chunk)],
            metadatas=[
                {
                    "source": filename
                }
            ]
        )

        chunk_counter += 1

print("Knowledge base built successfully!")