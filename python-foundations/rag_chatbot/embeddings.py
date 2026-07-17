from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity

print("Loading embedding model...\n")

model = SentenceTransformer(
    "sentence-transformers/all-MiniLM-L6-v2"
)

print("\nModel loaded!\n")

sentence1 = "Functions help reuse code."
sentence2 = "Functions prevent repeating code."
sentence3 = "Pizza tastes delicious."

embedding1 = model.encode(sentence1)
embedding2 = model.encode(sentence2)
embedding3 = model.encode(sentence3)

print(
    cosine_similarity(
        [embedding1],
        [embedding2]
    )
)

print(
    cosine_similarity(
        [embedding1],
        [embedding3]
    )
)