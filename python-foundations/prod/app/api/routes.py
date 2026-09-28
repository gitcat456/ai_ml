from fastapi import APIRouter

from app.schemas import ChatRequest, ChatResponse
from app.chatbot.service import ChatbotService


router = APIRouter(prefix="/api")

chatbot_service = ChatbotService()


@router.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    return chatbot_service.chat(request)