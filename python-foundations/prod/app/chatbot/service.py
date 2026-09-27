from app.schemas import ChatRequest, ChatResponse
from app.chatbot.router import QueryRouter, Route
from app.knowledge.retriever import KnowledgeRetriever
from app.knowledge.scope_guard import ScopeGuard


class ChatbotService:
    """
    Coordinates routing, retrieval, and evidence checking.
    """

    def __init__(self):
        self.router = QueryRouter()
        self.retriever = KnowledgeRetriever()
        self.scope_guard = ScopeGuard()

    def chat(self, request: ChatRequest) -> ChatResponse:
        decision = self.router.route(request.message)

        if decision.route == Route.DIRECT:
            return ChatResponse(
                answer=(
                    "Hello! I'm the organization's assistant. "
                    "How can I help you?"
                ),
                sources=[],
            )

        chunks = self.retriever.retrieve(request.message)

        scope_decision = self.scope_guard.check(
            query=request.message,
            chunks=chunks,
        )

        if not scope_decision.is_supported:
            return ChatResponse(
                answer=(
                    "I couldn't find sufficient relevant "
                    "information in the organization's "
                    "documents to answer that question. "
                    "Please try asking about the organization."
                ),
                sources=[],
            )

        return ChatResponse(
            answer=(
                "Relevant organizational evidence was found. "
                "Grounded answer generation is the next step."
            ),
            sources=[],
        )