from app.schemas import ChatRequest, ChatResponse
from app.chatbot.router import QueryRouter, Route


class ChatbotService:
    """
    Coordinates the chatbot's processing pipeline.
    """

    def __init__(self):
        self.router = QueryRouter()

    def chat(self, request: ChatRequest) -> ChatResponse:
        """
        Process a user's message and return a chatbot response.
        """

        decision = self.router.route(request.message)

        if decision.route == Route.DIRECT:
            return ChatResponse(
                answer="Hello! I'm the organization's assistant. How can I help you?",
                sources=[],
            )

        if decision.route == Route.KNOWLEDGE:
            return ChatResponse(
                answer="Your question has been routed for knowledge-base checking.",
                sources=[],
            )