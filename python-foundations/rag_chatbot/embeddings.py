from sentence_transformers import SentenceTransformer

print("Loading embedding model...")

model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")

print("Embedding model loaded!")


def embed(text):
    return model.encode(text)