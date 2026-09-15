from llama_index.core import (
    StorageContext,
    load_index_from_storage,
)
from llama_index.core.memory import ChatMemoryBuffer
from llama_index.core.postprocessor import (
    SentenceTransformerRerank,
)

import settings


class RAGService:

    def __init__(self):
        storage_context = StorageContext.from_defaults(
            persist_dir="../../rag_chatbot_llamaindex/storage"
        )

        self.index = load_index_from_storage(
            storage_context
        )

        self.reranker = SentenceTransformerRerank(
            model="cross-encoder/ms-marco-MiniLM-L-2-v2",
            top_n=3,
        )

        self.relevance_threshold = -3.0

        self.sessions = {}

    def get_chat_engine(self, session_id):

        if session_id not in self.sessions:

            memory = ChatMemoryBuffer.from_defaults(
                token_limit=4000
            )

            chat_engine = self.index.as_chat_engine(
                chat_mode="condense_plus_context",
                memory=memory,
                similarity_top_k=8,
                node_postprocessors=[
                    self.reranker
                ],
            )

            self.sessions[session_id] = chat_engine

        return self.sessions[session_id]

    def chat(self, session_id, message):

        chat_engine = self.get_chat_engine(
            session_id
        )

        response = chat_engine.chat(
            message
        )

        sources = []

        for node in response.source_nodes:
            sources.append({
                "file": node.metadata.get(
                    "file_name"
                ),
                "page": node.metadata.get(
                    "page_label"
                ),
                "score": (
                    float(node.score)
                    if node.score is not None
                    else None
                ),
            })

        return {
            "answer": str(response),
            "sources": sources,
        }

    def clear_session(self, session_id):

        if session_id in self.sessions:
            del self.sessions[session_id]