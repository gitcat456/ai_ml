from pathlib import Path
from llama_index.core import SimpleDirectoryReader
from llama_index.core.node_parser import SentenceSplitter

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

        self.relevance_threshold = -5.0

        self.sessions = {}
        

    def ingest_document(self, file_path: str):
        from pathlib import Path

        from llama_index.core import (
            SimpleDirectoryReader,
        )
        from llama_index.core.node_parser import (
            SentenceSplitter,
        )

        documents = SimpleDirectoryReader(
            input_files=[file_path]
        ).load_data()

        if not documents:
            raise ValueError(
                "No readable content was found in the document."
            )


        for document in documents:
            document.metadata["file_name"] = (
                Path(file_path).name
            )


        splitter = SentenceSplitter(
            chunk_size=512,
            chunk_overlap=50,
        )


        nodes = splitter.get_nodes_from_documents(
            documents
        )


        if not nodes:
            raise ValueError(
                "No readable text could be extracted from the PDF."
            )


        self.index.insert_nodes(
            nodes
        )


        self.index.storage_context.persist(
            persist_dir="../../rag_chatbot_llamaindex/storage"
        )


        self.sessions.clear()


        return {
            "documents": len(documents),
            "nodes": len(nodes),
        }



    def get_chat_engine(self, session_id):

        if session_id not in self.sessions:

            memory = ChatMemoryBuffer.from_defaults(
                token_limit=4000
            )

            chat_engine = self.index.as_chat_engine(
                chat_mode="condense_plus_context",
                memory=memory,
                similarity_top_k=5,
                node_postprocessors=[
                    self.reranker
                ],
            )
           #temporary in-memory session store
            self.sessions[session_id] = chat_engine

        return self.sessions[session_id]

    def chat(self, session_id, message):

        chat_engine = self.get_chat_engine(
            session_id
        )

        response = chat_engine.chat(
            message
        )

        if not response.source_nodes:
            return {
                "answer": (
                    "I don't have enough information "
                    "in the knowledge base to answer "
                    "that question."
                ),
                "sources": [],
            }

        best_score = response.source_nodes[0].score

        if (
            best_score is None
            or float(best_score) < self.relevance_threshold
        ):
            return {
                "answer": (
                    "I don't have enough information "
                    "in the knowledge base to answer "
                    "that question."
                ),
                "sources": [],
            }

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
        
    def delete_document(self, filename: str):
        docstore = self.index.docstore

        node_ids_to_delete = []

        for node_id, node in docstore.docs.items():
            if node.metadata.get("file_name") == filename:
                node_ids_to_delete.append(node_id)

        if not node_ids_to_delete:
            return False

        for node_id in node_ids_to_delete:
            self.index.delete_nodes(
                [node_id],
                delete_from_docstore=True,
            )

        self.index.storage_context.persist(
            persist_dir="../../rag_chatbot_llamaindex/storage"
        )

        self.sessions.clear()

        return True