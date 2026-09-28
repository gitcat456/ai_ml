from collections import defaultdict
from threading import Lock


class ConversationMemory:
    def __init__(self, max_messages=6):
        self.max_messages = max_messages
        self.histories = defaultdict(list)
        self.lock = Lock()

    def get_history(self, session_id):
        with self.lock:
            return list(self.histories[session_id])

    def add_message(self, session_id, role, content):
        with self.lock:
            history = self.histories[session_id]

            history.append({
                "role": role,
                "content": content
            })

            self.histories[session_id] = history[
                -self.max_messages:
            ]

    def clear_history(self, session_id):
        with self.lock:
            self.histories.pop(session_id, None)