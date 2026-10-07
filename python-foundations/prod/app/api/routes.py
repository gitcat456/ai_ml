import logging

from fastapi import APIRouter, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.schemas import ChatRequest, ChatResponse
from app.chatbot.service import ChatbotService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")

# ChatbotService is instantiated once at import time.
# The retriever uses lazy loading, so the embedding model
# is not loaded until the first knowledge request.
chatbot_service = ChatbotService()


@router.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    """
    Main chatbot endpoint.

    Receives a session_id and message.
    Returns an answer and optional source references.

    Errors from the service layer are caught here and translated
    into controlled HTTP responses so callers always receive JSON.
    """
    try:
        return chatbot_service.chat(request)
    except Exception as exc:
        logger.exception(
            "Unhandled error in /api/chat for session=%s: %s",
            request.session_id,
            exc,
        )
        raise HTTPException(
            status_code=500,
            detail="An internal error occurred. Please try again.",
        )