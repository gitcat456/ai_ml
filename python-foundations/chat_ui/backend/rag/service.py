from llama_index.core import (
    StorageContext,
    load_index_from_storage,
)

import settings


class RAGService:

    def __init__(self):
        storage_context = StorageContext.from_defaults(
            persist_dir="../../rag_chatbot_llamaindex/storage"
        )

        index = load_index_from_storage(
            storage_context
        )

        self.chat_engine = index.as_chat_engine(
            chat_mode="context",
            similarity_top_k=3,
        )

    def chat(self, message):
        return self.chat_engine.chat(message)