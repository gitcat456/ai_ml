from dataclasses import dataclass
from enum import Enum
import re


class Route(str, Enum):
    DIRECT = "direct"
    KNOWLEDGE = "knowledge"


@dataclass(frozen=True)
class RouteDecision:
    route: Route
    reason: str


class QueryRouter:
    """
    Performs the first routing decision for an incoming message.

    DIRECT:
        Safe conversational messages that do not need the knowledge base.

    KNOWLEDGE:
        Anything that may require information from the organization's
        knowledge base. The knowledge layer will later determine whether
        the question is actually within scope.
    """

    def route(self, message: str) -> RouteDecision:
        text = self._normalize(message)

        if self._is_direct_conversation(text):
            return RouteDecision(
                route=Route.DIRECT,
                reason="Message is simple conversational input.",
            )

        return RouteDecision(
            route=Route.KNOWLEDGE,
            reason="Message requires knowledge-base scope checking.",
        )

    @staticmethod
    def _normalize(message: str) -> str:
        return re.sub(r"\s+", " ", message.strip().lower())

    @staticmethod
    def _is_direct_conversation(text: str) -> bool:
        direct_phrases = {
            "hi",
            "hello",
            "hey",
            "hiya",
            "good morning",
            "good afternoon",
            "good evening",
            "thanks",
            "thank you",
            "thank you so much",
            "you're welcome",
            "bye",
            "goodbye",
            "see you",
            "who are you",
            "what can you do",
            "what do you do",
            "help",
        }

        return text in direct_phrases