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
        response = self.chat_engine.chat(message)
        sources = []
        
        for node in response.source_nodes:
            sources.append({
                "file": node.metadata.get("file_name"),
                "page": node.metadata.get("page_label"),
                "score": node.score,
            })
            
        return {
            "answer": str(response),
            "sources": sources,
        }