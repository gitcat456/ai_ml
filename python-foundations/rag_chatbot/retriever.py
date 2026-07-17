import math

def cosine_similarity(a, b):

    dot_product = sum(
        x*y for x,y in zip(a,b)
    )

    magnitude_a = math.sqrt(
        sum(x*x for x in a)
    )

    magnitude_b = math.sqrt(
        sum(x*x for x in b)
    )

    return dot_product / (magnitude_a * magnitude_b)


query_embedding = [0.85, 0.75]

documents = [
    {
        "text": "Functions help reuse code",
        "embedding": [0.9, 0.8]
    },

    {
        "text": "Lists store ordered data",
        "embedding": [0.2, 0.1]
    },

    {
        "text": "Dictionaries store key value pairs",
        "embedding": [0.3, 0.2]
    }
]



results = []
highest_score = -1


for document in documents:

    score = cosine_similarity(
        query_embedding,
        document["embedding"]
    )
    
    results.append((score, document))
   
       
results = sorted(results, reverse=True)
top_results = results[:3]


print("Top Results:\n")

for i, topresult in enumerate(top_results, start=1):
   
    print(f"{i}.{topresult[1]['text']}\n Score: {topresult[0]}\n")