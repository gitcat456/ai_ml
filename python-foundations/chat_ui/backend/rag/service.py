from llama_index.core import (
    StorageContext,
    load_index_from_storage,
)
from llama_index.core.postprocessor import SentenceTransformerRerank

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

        self.retriever = self.index.as_retriever(
            similarity_top_k=8
        )

        self.chat_engine = self.index.as_chat_engine(
            chat_mode="context",
            similarity_top_k=8,
            node_postprocessors=[
                self.reranker
            ],
        )

        self.relevance_threshold = -3.0

    def chat(self, message):

        nodes = self.retriever.retrieve(
            message
        )

        reranked_nodes = self.reranker.postprocess_nodes(
            nodes,
            query_str=message,
        )
        
        print("\nRERANKED RESULTS")

        for node in reranked_nodes:
            print(
                "Score:",
                node.score,
                "| File:",
                node.metadata.get("file_name"),
                "| Page:",
                node.metadata.get("page_label"),
            )

        if not reranked_nodes:
            return {
                "answer": (
                    "I don't have enough information "
                    "in the knowledge base to answer "
                    "that question."
                ),
                "sources": [],
            }

        best_score = reranked_nodes[0].score

        if (
            best_score is None
            or best_score < self.relevance_threshold
        ):
            return {
                "answer": (
                    "I don't have enough information "
                    "in the knowledge base to answer "
                    "that question."
                ),
                "sources": [],
            }

        response = self.chat_engine.chat(
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