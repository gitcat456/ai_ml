with open("notes.txt", "r", encoding="utf-8") as file:
    text = file.read()
    
chunks = text.split("\n\n")

for i, chunk in enumerate(chunks, start=1):
    print(f"Chunk {i}")
    print(chunk)
    print("-" * 40)