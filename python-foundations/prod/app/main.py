import logging
import sys

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.config import validate_config


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Lifespan: startup / shutdown hooks
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Validate critical configuration and pre-warm AI models on startup."""
    try:
        validate_config()
        logger.info("Configuration validated successfully.")
    except RuntimeError as exc:
        logger.critical("Startup aborted: %s", exc)
        raise SystemExit(1) from exc

    logger.info("EUSDA chatbot service starting up. Pre-warming knowledge retriever index...")
    try:
        from app.api.routes import chatbot_service
        chatbot_service.retriever._load_index()
        logger.info("Knowledge retriever pre-warmed successfully!")
    except Exception as exc:
        logger.warning("Retriever pre-warm warning (will load on demand): %s", exc)

    yield
    logger.info("EUSDA chatbot service shutting down.")


# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------

app = FastAPI(
    title="EUSDA Organization Chatbot API",
    description="Backend AI service for the EUSDA organizational chatbot.",
    version="1.0.0",
    lifespan=lifespan,
)

# Allow the Express backend (and local dev tools) to call this service.
# In production the Express proxy is the only actual caller.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

app.include_router(router)


@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "service": "eusda-chatbot",
    }