import os
from pathlib import Path

from dotenv import load_dotenv

# Project root: python-foundations/prod/
BASE_DIR = Path(__file__).resolve().parent.parent

# Load environment variables from prod/.env
load_dotenv(BASE_DIR / ".env")

# -----------------------------------------------------------------------------
# LLM Configuration (Groq API)
# -----------------------------------------------------------------------------
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
LLM_MODEL = os.getenv("LLM_MODEL", "qwen/qwen3.8-27b")
FAST_LLM_MODEL = os.getenv("FAST_LLM_MODEL", "qwen/qwen3.8-27b")

# -----------------------------------------------------------------------------
# Embeddings Configuration (Google Gemini API)
# -----------------------------------------------------------------------------
EMBEDDING_PROVIDER = os.getenv("EMBEDDING_PROVIDER", "gemini").lower()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "gemini-embedding-001")
try:
    EMBEDDING_DIM = int(os.getenv("EMBEDDING_DIM", "768"))
except (ValueError, TypeError):
    EMBEDDING_DIM = 768

# -----------------------------------------------------------------------------
# Vector Database Configuration (Qdrant Cloud)
# -----------------------------------------------------------------------------
QDRANT_URL = os.getenv("QDRANT_URL")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION", "eusda_docs")

# -----------------------------------------------------------------------------
# Application Environment
# -----------------------------------------------------------------------------
APP_ENV = os.getenv("APP_ENV", "development")


def validate_config():
    """Check that all required external API configuration is present."""
    missing = []
    if not GROQ_API_KEY:
        missing.append("GROQ_API_KEY")
    if not GEMINI_API_KEY:
        missing.append("GEMINI_API_KEY")
    if not QDRANT_URL:
        missing.append("QDRANT_URL")
    if not QDRANT_API_KEY:
        missing.append("QDRANT_API_KEY")
    if not QDRANT_COLLECTION:
        missing.append("QDRANT_COLLECTION")

    if missing:
        raise RuntimeError(
            f"Missing required environment variable(s): {', '.join(missing)}. "
            "Please check your prod/.env file or deployment environment settings."
        )