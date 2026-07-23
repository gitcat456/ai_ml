import os
import chromadb

from pypdf import PdfReader
from sentence_transformers import SentenceTransformer

# ------------------------
# Load embedding model
# ------------------------

print("Loading embedding model...")

model = SentenceTransformer(
    "sentence-transformers/all-MiniLM-L6-v2"
)

print("Embedding model loaded!")

# ------------------------
# ChromaDB
# ------------------------

client = chromadb.PersistentClient(path="./database")

collection = client.get_or_create_collection(
    name="knowledge_base"
)

# ------------------------
# Documents folder
# ------------------------

documents_folder = "documents"

chunk_counter = 1

# ------------------------
# Read every PDF
# ------------------------

for filename in os.listdir(documents_folder):

    if not filename.endswith(".pdf"):
        continue

    filepath = os.path.join(
        documents_folder,
        filename
    )

    print(f"Reading {filename}")

    reader = PdfReader(filepath)

    text = ""

    for page in reader.pages:

        page_text = page.extract_text()

        if page_text:
            text += page_text + "\n"

    # ------------------------
    # Chunking
    # ------------------------

    chunks = text.split("\n\n")

    # ------------------------
    # Store chunks
    # ------------------------

    for chunk in chunks:

        chunk = chunk.strip()

        if len(chunk) == 0:
            continue

        embedding = model.encode(chunk).tolist()

        collection.add(

            ids=[f"chunk_{chunk_counter}"],

            documents=[chunk],

            embeddings=[embedding],

            metadatas=[
                {
                    "source": filename
                }
            ]

        )

        chunk_counter += 1

print("Finished indexing all PDFs!")