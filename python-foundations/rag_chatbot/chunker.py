# def load_chunks(file_path):
    
#     with open(file_path, "r", encoding="utf-8") as file:
#         text = file.read()
        
#     chunks = text.split("\n\n")
    
#     return chunks 

def chunk_text(text):

    chunks = text.split("\n\n")

    return [
        chunk.strip()
        for chunk in chunks
        if chunk.strip()
    ]

    # for i, chunk in enumerate(chunks, start=1):
    #     print(f"Chunk {i}")
    #     print(chunk)
    #     print("-" * 40)
        
        
# chunk_embeddings = []

# for chunk in chunks:

#     embedding = model.encode(chunk)

#     chunk_embeddings.append({
#         "text": chunk,
#         "embedding": embedding
#     })