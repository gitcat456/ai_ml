from fastapi import FastAPI
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from rag.service import RAGService

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

rag = RAGService()

class ChatRequest(BaseModel):
    message: str


@app.get("/")
def root():
    return {"message": "Chat UI backend is running"}


@app.post("/api/chat")
def chat(request: ChatRequest):
    response = rag.chat(request.message)

    return response