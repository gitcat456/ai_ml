import os
from pathlib import Path

from dotenv import load_dotenv

# Project root: python-foundations/prod/
BASE_DIR = Path(__file__).resolve().parent.parent

# Load environment variables from prod/.env
load_dotenv(BASE_DIR / ".env")

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
LLM_MODEL = os.getenv(
    "LLM_MODEL",
    "qwen/qwen3.8-27b"
)
FAST_LLM_MODEL = os.getenv(
    "FAST_LLM_MODEL",
    "qwen/qwen3.8-27b"
)

EMBEDDING_MODEL = os.getenv(
    "EMBEDDING_MODEL",
    "BAAI/bge-small-en-v1.5"
)

RERANKER_MODEL = os.getenv(
    "RERANKER_MODEL",
    "cross-encoder/ms-marco-MiniLM-L-2-v2"
)

APP_ENV = os.getenv("APP_ENV", "development")


def validate_config():
    """Check that required configuration is present."""
    if not GROQ_API_KEY:
        raise RuntimeError(
            "GROQ_API_KEY is missing. Check your prod/.env file."
        )