import json
import logging
import os
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

from app.config import BASE_DIR

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


def log_interaction(
    question: str,
    answer: str | None,
    latency_ms: int,
    error: str | None = None,
    session_id: str | None = None,
    log_file: Path | str | None = None,
) -> None:
    """
    Append one chatbot interaction as a JSON line to chat_interactions.jsonl.

    Captures what the user asked, what the bot answered, how long it took,
    and whether it errored. Never raises or crashes the chatbot.
    """
    try:
        if not session_id:
            session_id = str(uuid.uuid4())

        entry = {
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
        }

        line = json.dumps(entry, ensure_ascii=False) + "\n"

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

