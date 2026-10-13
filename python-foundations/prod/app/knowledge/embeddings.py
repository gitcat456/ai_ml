import logging
import math
import re
import time
from abc import ABC, abstractmethod
from typing import Sequence

from google import genai
from google.genai import types
from google.genai.errors import APIError

from app.config import (
    EMBEDDING_DIM,
    EMBEDDING_MODEL,
    EMBEDDING_PROVIDER,
    GEMINI_API_KEY,
)

logger = logging.getLogger(__name__)


def _normalize_l2(vector: Sequence[float]) -> list[float]:
    """Normalize a vector to unit L2 norm."""
    norm = math.sqrt(sum(x * x for x in vector))
    if norm == 0.0 or math.isclose(norm, 1.0, rel_tol=1e-5):
        return list(vector)
    return [x / norm for x in vector]


class BaseEmbeddingProvider(ABC):
    """Abstract interface for swappable embedding providers."""

    @abstractmethod
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Generate normalized embeddings for a list of document chunks."""
        pass

    @abstractmethod
    def embed_query(self, text: str) -> list[float]:
        """Generate a normalized embedding for a search query."""
        pass


class GeminiEmbeddingProvider(BaseEmbeddingProvider):
    """
    Google Gemini Embeddings provider via the official google-genai SDK.
    Supports:
    - Matryoshka dimensionality reduction (EMBEDDING_DIM = 768)
    - Retrieval task types (RETRIEVAL_DOCUMENT vs RETRIEVAL_QUERY)
    - L2 normalization for exact cosine similarity
    - Batching and exponential backoff retry for rate limits
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        dim: int | None = None,
        batch_size: int = 10,
        max_retries: int = 5,
        initial_backoff: float = 1.5,
    ):
        self.api_key = api_key or GEMINI_API_KEY
        if not self.api_key:
            raise RuntimeError(
                "GEMINI_API_KEY is required for GeminiEmbeddingProvider."
            )
        self.model = model or EMBEDDING_MODEL
        self.dim = dim or EMBEDDING_DIM
        self.batch_size = batch_size
        self.max_retries = max_retries
        self.initial_backoff = initial_backoff

        self.client = genai.Client(api_key=self.api_key)

    def _embed_with_retry(
        self,
        contents: list[str] | str,
        task_type: str,
    ) -> list[list[float]]:
        """Call Gemini embed_content with exponential backoff and retry-after parsing on rate limits."""
        backoff = self.initial_backoff
        last_exception = None

        config = types.EmbedContentConfig(
            task_type=task_type,
            output_dimensionality=self.dim,
        )

        for attempt in range(1, self.max_retries + 1):
            try:
                response = self.client.models.embed_content(
                    model=self.model,
                    contents=contents,
                    config=config,
                )
                raw_embeddings = [emb.values for emb in response.embeddings]
                # Normalize truncated vectors to unit length for cosine distance
                return [_normalize_l2(vec) for vec in raw_embeddings]

            except APIError as exc:
                last_exception = exc
                exc_str = str(exc)
                is_rate_limit = exc.code == 429 or "RESOURCE_EXHAUSTED" in exc_str.upper() or "QUOTA" in exc_str.upper()
                is_server_error = exc.code in (500, 503, 504)

                if (is_rate_limit or is_server_error) and attempt < self.max_retries:
                    # Try to extract the server-suggested retry duration (e.g. "retry in 47.4s")
                    retry_match = re.search(r"retry in\s+([0-9]+(?:\.[0-9]+)?)\s*s", exc_str, re.IGNORECASE)
                    if retry_match:
                        wait_sec = float(retry_match.group(1)) + 1.5
                    else:
                        wait_sec = max(backoff, 5.0)

                    logger.warning(
                        "Gemini Embedding API quota/rate-limit hit on attempt %d/%d. Waiting %.1fs before retrying...",
                        attempt,
                        self.max_retries,
                        wait_sec,
                    )
                    time.sleep(wait_sec)
                    backoff = max(backoff * 2, 5.0)
                else:
                    if is_rate_limit:
                        raise RuntimeError(
                            f"Gemini API rate limit exceeded during embedding (attempt {attempt}/{self.max_retries}). "
                            "Please check your quota or wait before retrying."
                        ) from exc
                    raise RuntimeError(
                        f"Gemini Embedding API call failed: {exc}"
                    ) from exc

            except Exception as exc:
                last_exception = exc
                exc_str = str(exc)
                is_rate_limit = "429" in exc_str or "RESOURCE_EXHAUSTED" in exc_str.upper() or "QUOTA" in exc_str.upper()
                if attempt < self.max_retries:
                    retry_match = re.search(r"retry in\s+([0-9]+(?:\.[0-9]+)?)\s*s", exc_str, re.IGNORECASE)
                    if retry_match:
                        wait_sec = float(retry_match.group(1)) + 1.5
                    else:
                        wait_sec = max(backoff, 5.0 if is_rate_limit else 2.0)

                    logger.warning(
                        "Error calling Gemini Embeddings on attempt %d/%d: %s. Retrying in %.1fs...",
                        attempt,
                        self.max_retries,
                        exc,
                        wait_sec,
                    )
                    time.sleep(wait_sec)
                    backoff = max(backoff * 2, 5.0)
                else:
                    raise RuntimeError(
                        f"Failed to generate Gemini embeddings after {self.max_retries} attempts: {exc}"
                    ) from exc

        raise RuntimeError(
            f"Failed to generate Gemini embeddings: {last_exception}"
        )

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Generate normalized embeddings for document chunks in batches."""
        if not texts:
            return []

        all_vectors = []
        for i in range(0, len(texts), self.batch_size):
            batch = texts[i : i + self.batch_size]
            vectors = self._embed_with_retry(
                contents=batch,
                task_type="RETRIEVAL_DOCUMENT",
            )
            all_vectors.extend(vectors)
            # Brief delay between batches to respect free tier RPM limits
            # if i + self.batch_size < len(texts):
            #     time.sleep(0.2)

        return all_vectors

    def embed_query(self, text: str) -> list[float]:
        """Generate a normalized embedding for a search query."""
        if not text or not text.strip():
            return [0.0] * self.dim

        vectors = self._embed_with_retry(
            contents=text.strip(),
            task_type="RETRIEVAL_QUERY",
        )
        return vectors[0]


def get_embedding_provider() -> BaseEmbeddingProvider:
    """Factory function returning the configured embedding provider."""
    provider = EMBEDDING_PROVIDER.lower()
    if provider == "gemini":
        return GeminiEmbeddingProvider()
    raise ValueError(
        f"Unsupported EMBEDDING_PROVIDER: '{provider}'. Supported providers: 'gemini'"
    )
