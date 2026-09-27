from fastapi import APIRouter

from app.schemas import ChatRequest, ChatResponse


router = APIRouter(prefix="/api")


@router.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    return ChatResponse(
        answer="Chatbot service not connected yet.",
        sources=[],
    )