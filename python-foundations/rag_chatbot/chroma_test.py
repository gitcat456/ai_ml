import chromadb

client = chromadb.PersistentClient(path="./database")

collection = client.get_or_create_collection(
    name="anime_notes"
)

print("Collection created successfully!")