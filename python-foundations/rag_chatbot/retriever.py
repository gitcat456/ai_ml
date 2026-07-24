import chromadb
from embeddings import embed

client = chromadb.PersistentClient(
    path="./database"
)

collection = client.get_or_create_collection(
    name="knowledge_base"
)

def retrieve(question, k=3):

    query_embedding = embed(question)

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=k
    )

    return results






# from embeddings import embed
# from sklearn.metrics.pairwise import cosine_similarity
# import chromadb

# client = chromadb.PersistentClient(path="./database")

# collection = client.get_or_create_collection(
#     name="knowledge_base"
# )

# def build_index(chunks):

#     for i, chunk in enumerate(chunks, start=1):

#         chunk_id = f"chunk_{i}"

#         collection.add(
#             ids=[chunk_id],
#             documents=[chunk],
#             embeddings=[embed(chunk)]
#         )

#     return collection

#     #     index.append({
#     #         "text": chunk,
#     #         "embedding": embed(chunk)
#     #     })

#     # return index
    
    

# def retrieve(question, k=3):

#     query_embedding = embed(question)

#     results = collection.query(
#         query_embeddings=[query_embedding],
#         n_results=k
#     )

#     return results


# def retrieve(question, index, k=3):
    
#     query_embedding = embed(question)
    
#     results = []
    
#     for document in index:
#         score = cosine_similarity(
#             [query_embedding],
#             [document["embedding"]]
#         )[0][0]
        
#         results.append(
#             (score, document)
#         )
    
#     results = sorted(
#         results,
#         reverse=True
#     )
    
#     top_results = results[:k]
    
#     return top_results






# import math

# def cosine_similarity(a, b):

#     dot_product = sum(
#         x*y for x,y in zip(a,b)
#     )

#     magnitude_a = math.sqrt(
#         sum(x*x for x in a)
#     )

#     magnitude_b = math.sqrt(
#         sum(x*x for x in b)
#     )

#     return dot_product / (magnitude_a * magnitude_b)


# query_embedding = [0.85, 0.75]

# documents = [
#     {
#         "text": "Functions help reuse code",
#         "embedding": [0.9, 0.8]
#     },

#     {
#         "text": "Lists store ordered data",
#         "embedding": [0.2, 0.1]
#     },

#     {
#         "text": "Dictionaries store key value pairs",
#         "embedding": [0.3, 0.2]
#     }
# ]



# results = []
# highest_score = -1


# for document in documents:

#     score = cosine_similarity(
#         query_embedding,
#         document["embedding"]
#     )
    
#     results.append((score, document))
   
       
# results = sorted(results, reverse=True)
# top_results = results[:3]


# print("Top Results:\n")

# for i, topresult in enumerate(top_results, start=1):
   
#     print(f"{i}.{topresult[1]['text']}\n Score: {topresult[0]}\n")