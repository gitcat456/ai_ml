from collections import defaultdict
from threading import Lock


class ConversationMemory:
    def __init__(self, max_messages: int = 10):
        self.max_messages = max_messages
        self.histories = defaultdict(list)
        self.lock = Lock()

    def get_history(self, session_id: str) -> list[dict[str, str]]:
        with self.lock:
            return list(self.histories[session_id])

    def format_history_text(self, session_id: str) -> str:
        with self.lock:
            history = self.histories.get(session_id, [])
            if not history:
                return "No previous conversation."
            return "\n".join(
                f"{item['role'].upper()}: {item['content']}"
                for item in history
            )

    def add_message(self, session_id: str, role: str, content: str):
        with self.lock:
            history = self.histories[session_id]

            history.append({
                "role": role,
                "content": content
            })

            self.histories[session_id] = history[
                -self.max_messages:
            ]

    def clear_history(self, session_id: str):
        with self.lock:
            self.histories.pop(session_id, None)