import logging
import random
import re
import time
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


class RateLimitError(Exception):
    """Custom RateLimitError for offline testing and 429 handling."""
    pass


@dataclass
class FakeResponse:
    content: str | None = None
    choices: list[Any] | None = None

    def __post_init__(self):
        if self.choices is None and self.content is not None:
            # Emulate OpenAI / Groq response structure if needed
            class Message:
                def __init__(self, c):
                    self.content = c

            class Choice:
                def __init__(self, m):
                    self.message = m

            self.choices = [Choice(Message(self.content))]


@dataclass
class RetryResult:
    answer: str | None
    error: str | None = None
    retry_count: int = 0
    choices: list[Any] | None = None


def parse_wait_time(error_message: str) -> float | None:
    """
    Parse wait time from error message, e.g.
    'Please try again in 22.3425s' or 'try again in 0.1s'.
    """
    match = re.search(
        r"(?:please\s+)?try\s+again\s+in\s+([0-9.]+)\s*s?",
        error_message,
        re.IGNORECASE,
    )
    if match:
        try:
            return float(match.group(1))
        except ValueError:
            return None
    return None


def is_rate_limit_error(exc: Exception) -> bool:
    """Check if exception is a 429 rate limit error."""
    exc_name = type(exc).__name__
    if "RateLimit" in exc_name:
        return True
    msg = str(exc).lower()
    return "429" in msg or "rate limit" in msg


def call_with_retry(
    client: Any,
    prompt_or_kwargs: Any,
    max_retries: int = 3,
    fallback_backoffs: tuple[float, ...] = (2.0, 4.0, 8.0),
) -> RetryResult:
    """
    Execute chat completion with automatic retry on 429 rate limit errors.
    Parses wait time from message, applies jitter, and retries up to max_retries.
    If all retries are exhausted, returns graceful message with error='rate_limited_after_retries'.
    """
    attempts = 0
    while True:
        try:
            # Check client call style
            if hasattr(client, "chat"):
                if callable(client.chat):
                    response = client.chat(prompt_or_kwargs)
                elif hasattr(client.chat, "completions") and callable(
                    getattr(client.chat.completions, "create", None)
                ):
                    if isinstance(prompt_or_kwargs, dict):
                        response = client.chat.completions.create(**prompt_or_kwargs)
                    else:
                        response = client.chat.completions.create(
                            messages=[{"role": "user", "content": str(prompt_or_kwargs)}]
                        )
                else:
                    response = client.chat(prompt_or_kwargs)
            elif callable(client):
                response = client(prompt_or_kwargs)
            else:
                raise TypeError(f"Unsupported client type: {type(client)}")

            # Extract answer content
            answer_content = None
            if hasattr(response, "choices") and response.choices:
                first = response.choices[0]
                if hasattr(first, "message") and hasattr(first.message, "content"):
                    answer_content = first.message.content
                elif isinstance(first, dict):
                    answer_content = first.get("message", {}).get("content")
            elif hasattr(response, "content"):
                answer_content = response.content
            elif isinstance(response, str):
                answer_content = response

            return RetryResult(
                answer=answer_content,
                error=None,
                retry_count=attempts,
            )

        except Exception as exc:
            if not is_rate_limit_error(exc):
                # Non-rate-limit exception
                raise

            attempts += 1
            if attempts > max_retries:
                logger.warning(
                    "Exhausted %d retries on rate limit (429): %s",
                    max_retries,
                    exc,
                )
                return RetryResult(
                    answer="I'm getting a lot of requests right now — please try again in a minute.",
                    error="rate_limited_after_retries",
                    retry_count=max_retries,
                )

            # Determine sleep duration
            wait_time = parse_wait_time(str(exc))
            if wait_time is not None:
                sleep_s = wait_time + random.uniform(0.01, 0.05)
            else:
                idx = min(attempts - 1, len(fallback_backoffs) - 1)
                sleep_s = fallback_backoffs[idx] + random.uniform(0.01, 0.1)

            logger.info(
                "Rate limit encountered (attempt %d/%d). Sleeping for %.3fs: %s",
                attempts,
                max_retries,
                sleep_s,
                exc,
            )
            time.sleep(sleep_s)

