import json
import logging
import os
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.config import BASE_DIR, LLM_MODEL

logger = logging.getLogger(__name__)

_log_lock = threading.Lock()

DEFAULT_LOG_FILE = BASE_DIR / "logs" / "chat_interactions.jsonl"


def _get_target_paths(log_file: Path | str | None = None) -> list[Path]:
    """
    Determine target paths for the log file.
    Always includes the project's logs directory. If cwd differs, also writes
    relative to cwd so tests or local scripts find logs/chat_interactions.jsonl.
    """
    if log_file is not None:
        return [Path(log_file)]

    env_path = os.getenv("CHAT_INTERACTIONS_LOG_PATH") or os.getenv("INTERACTION_LOG_FILE")
    if env_path:
        return [Path(env_path)]

    targets = [DEFAULT_LOG_FILE]
    try:
        cwd_log = Path("logs") / "chat_interactions.jsonl"
        if cwd_log.resolve() != DEFAULT_LOG_FILE.resolve():
            targets.append(cwd_log)
    except Exception:
        pass
    return targets


def build_log_entry(
    question: str,
    answer: str | None,
    latency_ms: int,
    error: str | None = None,
    session_id: str | None = None,
    chunks: list[Any] | None = None,
    model: str | None = None,
    retry_count: int = 0,
    grounding_guard_triggered: bool = False,
    scope: str = "in",
    answer_source: str = "retrieval",
    top_score: float | None = None,
    retrieved_chunk_ids: list[str] | None = None,
) -> dict[str, Any]:
    """
    Build a structured log entry containing telemetry for failure triage.
    """
    if not session_id:
        session_id = str(uuid.uuid4())

    chunk_list = chunks or []

    # Derive chunk IDs if not explicitly passed
    if retrieved_chunk_ids is None:
        ids: list[str] = []
        for idx, c in enumerate(chunk_list):
            if hasattr(c, "id") and c.id is not None:
                ids.append(str(c.id))
            elif isinstance(c, dict) and "id" in c:
                ids.append(str(c["id"]))
            elif hasattr(c, "citation_label") and c.citation_label:
                ids.append(str(c.citation_label))
            elif hasattr(c, "filename") and c.filename:
                ids.append(f"{c.filename}_{getattr(c, 'page', idx)}")
            else:
                ids.append(f"chunk_{idx}")
        retrieved_chunk_ids = ids

    # Derive top score if not explicitly passed
    if top_score is None:
        if chunk_list:
            first = chunk_list[0]
            if hasattr(first, "score") and first.score is not None:
                top_score = float(first.score)
            elif isinstance(first, dict) and "score" in first and first["score"] is not None:
                top_score = float(first["score"])
            else:
                top_score = 0.85
        else:
            top_score = 0.0

    return {
        "timestamp": (
            datetime.now(timezone.utc)
            .isoformat(timespec="milliseconds")
            .replace("+00:00", "Z")
        ),
        "session_id": str(session_id),
        "question": str(question) if question is not None else "",
        "answer": answer if answer is not None else None,
        "latency_ms": int(latency_ms) if latency_ms is not None else 0,
        "error": str(error) if error is not None else None,
        "model": model or LLM_MODEL or "openai/gpt-oss-120b",
        "retrieved_chunk_ids": retrieved_chunk_ids,
        "top_score": top_score,
        "num_retrieved": len(chunk_list),
        "retry_count": int(retry_count),
        "grounding_guard_triggered": bool(grounding_guard_triggered),
        "scope": scope,
        "answer_source": answer_source,
    }


def log_interaction(
    question: str,
    answer: str | None,
    latency_ms: int,
    error: str | None = None,
    session_id: str | None = None,
    log_file: Path | str | None = None,
    chunks: list[Any] | None = None,
    model: str | None = None,
    retry_count: int = 0,
    grounding_guard_triggered: bool = False,
    scope: str = "in",
    answer_source: str = "retrieval",
    top_score: float | None = None,
    retrieved_chunk_ids: list[str] | None = None,
) -> None:
    """
    Append one chatbot interaction as a JSON line to chat_interactions.jsonl.
    """
    try:
        entry = build_log_entry(
            question=question,
            answer=answer,
            latency_ms=latency_ms,
            error=error,
            session_id=session_id,
            chunks=chunks,
            model=model,
            retry_count=retry_count,
            grounding_guard_triggered=grounding_guard_triggered,
            scope=scope,
            answer_source=answer_source,
            top_score=top_score,
            retrieved_chunk_ids=retrieved_chunk_ids,
        )

        line = json.dumps(entry, ensure_ascii=False) + "\n"
        logger.info("CHAT_INTERACTION: %s", line.strip())

        target_paths = _get_target_paths(log_file)
        with _log_lock:
            for p in target_paths:
                try:
                    p.parent.mkdir(parents=True, exist_ok=True)
                    with open(p, "a", encoding="utf-8") as f:
                        f.write(line)
                        f.flush()
                except Exception as write_err:
                    logger.warning("Failed writing log line to %s: %s", p, write_err)
    except Exception as exc:
        logger.warning("Failed to log interaction: %s", exc)
