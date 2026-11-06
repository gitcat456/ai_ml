import json
import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.schemas import ChatRequest, ChatResponse
from app.chatbot.service import ChatbotService
from app.chatbot.logger import DEFAULT_LOG_FILE

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


@router.get("/chat-logs")
def view_chat_logs():
    """
    View all logged chatbot interactions directly in the browser or via API.
    """
    log_file = DEFAULT_LOG_FILE
    if not log_file.exists():
        cwd_log = Path("logs") / "chat_interactions.jsonl"
        if cwd_log.exists():
            log_file = cwd_log
        else:
            return {"interactions": []}

    try:
        return [
            json.loads(line)
            for line in log_file.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
    except Exception as exc:
        logger.exception("Failed reading chat logs: %s", exc)
        return {"interactions": [], "error": str(exc)}
