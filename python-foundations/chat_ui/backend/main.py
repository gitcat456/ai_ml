from fastapi import FastAPI
from rag.service import RAGService

app = FastAPI()

rag = RAGService()


@app.get("/")
def root():
    return {"message": "Chat UI backend is running"}


@app.post("/api/chat")
def chat(message: str):
    response = rag.chat(message)

    return {
        "answer": str(response)
    }