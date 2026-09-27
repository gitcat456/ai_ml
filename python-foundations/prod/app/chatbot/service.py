from app.schemas import ChatRequest, ChatResponse


class ChatbotService:
    """
    Coordinates the chatbot's decision-making and response generation.
    """

    def chat(self, request: ChatRequest) -> ChatResponse:
        """
        Process a user's message and return a chatbot response.
        """

        return ChatResponse(
            answer="Chatbot service is working.",
            sources=[],
        )