"""
Query router for the EUSDA chatbot.

Uses a two-phase strategy:

Phase 1 — Fast heuristic gate:
    Catches obvious single-word greetings / acks before touching the LLM.

Phase 2 — LLM intent classification:
    Classifies everything else into:
        DIRECT       – greetings, small talk, pleasantries
        KNOWLEDGE    – organizational questions (enter the RAG pipeline)
        OUT_OF_SCOPE – general-world questions clearly outside org context

Routing is intentionally cheap relative to full answer generation.
The LLM call here uses a tiny prompt, temperature=0, and max_tokens=10.

The KNOWLEDGE / OUT_OF_SCOPE distinction at routing time is an optimistic
first filter.  ScopeGuard provides a second, evidence-based check after
retrieval.  OUT_OF_SCOPE at the router level is reserved for questions
that are unambiguously general-knowledge (math, current events, etc.).
Ambiguous questions default to KNOWLEDGE and let ScopeGuard decide.
"""

import logging
import re
from dataclasses import dataclass
from enum import Enum

from groq import Groq

from app.config import FAST_LLM_MODEL, GROQ_API_KEY, LLM_MODEL

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Heuristic phrase sets used in the fast-path check (Phase 1).
# These are exact, normalized matches only.
# ---------------------------------------------------------------------------
_EXACT_DIRECT_PHRASES: frozenset[str] = frozenset(
    {
        # greetings
        "hi",
        "hello",
        "hey",
        "hiya",
        "heya",
        "hey there",
        "hi there",
        "hello there",
        "howdy",
        "greetings",
        "good morning",
        "good afternoon",
        "good evening",
        "good night",
        "good day",
        # acks / affirmations
        "thanks",
        "thank you",
        "thank you so much",
        "many thanks",
        "cheers",
        "ok",
        "okay",
        "ok thanks",
        "okay thanks",
        "alright",
        "got it",
        "understood",
        "noted",
        "great",
        "cool",
        "awesome",
        "nice",
        "sure",
        # farewells
        "bye",
        "goodbye",
        "see you",
        "see ya",
        "later",
        "good bye",
        "take care",
        # meta / identity
        "who are you",
        "what are you",
        "what can you do",
        "what do you do",
        "help",
    }
)


# ---------------------------------------------------------------------------
# Public enumerations and data classes
# ---------------------------------------------------------------------------


class Route(str, Enum):
    DIRECT = "direct"
    KNOWLEDGE = "knowledge"
    OUT_OF_SCOPE = "out_of_scope"


@dataclass(frozen=True)
class RouteDecision:
    route: Route
    reason: str
    # For DIRECT responses the router may supply a ready-made reply so
    # the service layer does not need to compose one.
    direct_answer: str | None = None


# ---------------------------------------------------------------------------
# Direct-response templates
# ---------------------------------------------------------------------------

_DIRECT_RESPONSES: dict[str, str] = {
    "greeting": (
        "Hello! I'm the EUSDA Assistant. "
        "I can answer questions about our church, leadership, departments, "
        "ministries, events, constitution, and church manual. How can I help you today?"
    ),
    "acknowledgement": (
        "You're very welcome! Is there anything else about EUSDA I can help you with?"
    ),
    "farewell": (
        "Goodbye and God bless! Feel free to return whenever you have questions about EUSDA."
    ),
    "identity": (
        "I'm the official EUSDA AI Assistant. I'm here to help members, students, "
        "and visitors find information about the church — departments, ministries, "
        "events, leadership roles, the EUSDA Constitution, and Church Manual. What would you like to know?"
    ),
    "fallback_direct": (
        "I'm here to help with questions about EUSDA. "
        "What would you like to know?"
    ),
}

_OUT_OF_SCOPE_RESPONSE = (
    "That question is outside the scope of what I can help with here. "
    "I'm specifically designed to assist with EUSDA — its "
    "departments, ministries, events, policies, constitution, and church documents. "
    "Is there something about EUSDA I can help you with?"
)


# ---------------------------------------------------------------------------
# LLM intent classification prompt
# ---------------------------------------------------------------------------

_CLASSIFICATION_SYSTEM_PROMPT = """\
You are a fast intent classifier for the EUSDA Church AI Assistant.

Classify the user's message into exactly one of these categories:

DIRECT_GREETING
  - Greetings, hello, good morning, hey, etc.
  - Member introductions (e.g. "hello there am Denz a church member")
  - Casual questions like "Hello, how are you?"

DIRECT_ACK
  - Acknowledgements: thanks, thank you, okay, got it, great, cool, etc.
  - Short affirmations or closings with no actual question.

DIRECT_FAREWELL
  - Bye, goodbye, see you, take care, etc.

DIRECT_IDENTITY
  - "Who are you?", "What can you do?", "What are you?", etc.

KNOWLEDGE
  - Questions about the church/organization: departments, leaders, pastors,
    elders, deacons, events, policies, constitution, ministries, Sabbath school, finances.
  - Any query asking about roles, rules, procedures, or church doctrines.
  - When in doubt, prefer KNOWLEDGE.

OUT_OF_SCOPE
  - Clearly general-knowledge questions with no plausible church/org angle.
  - Examples: math equations, secular politics, coding, recipes, general trivia.

Rules:
- Respond with ONLY the category name, nothing else.
- If uncertain between KNOWLEDGE and OUT_OF_SCOPE, output KNOWLEDGE.
"""


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------


class QueryRouter:
    """
    Routes incoming messages to the appropriate handling path.

    DIRECT       → a friendly direct response (no knowledge retrieval).
    KNOWLEDGE    → enters the RAG pipeline (retrieval + scope guard + LLM).
    OUT_OF_SCOPE → returns a controlled out-of-scope message without RAG.
    """

    def __init__(self) -> None:
        self._client = Groq(api_key=GROQ_API_KEY)
        self._model = FAST_LLM_MODEL or LLM_MODEL

    def route(self, message: str) -> RouteDecision:
        """
        Route a message. Never raises; falls back to KNOWLEDGE on error.
        """
        normalized = _normalize(message)

        # Phase 1: fast exact-match and regex heuristic
        heuristic = _heuristic_check(normalized)
        if heuristic is not None:
            logger.debug(
                "Router heuristic match: route=%s message=%r",
                heuristic.route,
                message[:80],
            )
            return heuristic

        # Phase 2: fast LLM classification
        try:
            label = self._classify_with_llm(message)
        except Exception as exc:
            logger.warning(
                "Router LLM call failed (%s). Falling back to KNOWLEDGE.",
                exc,
            )
            return RouteDecision(
                route=Route.KNOWLEDGE,
                reason="LLM classification unavailable; defaulting to knowledge pipeline.",
            )

        decision = _label_to_decision(label, message)
        logger.info(
            "Router decision: route=%s label=%s message=%r",
            decision.route,
            label,
            message[:80],
        )
        return decision

    def _classify_with_llm(self, message: str) -> str:
        """
        Ask the LLM to classify the message.
        Returns one of the category strings defined in the system prompt.
        """
        response = self._client.chat.completions.create(
            model=self._model,
            messages=[
                {
                    "role": "system",
                    "content": _CLASSIFICATION_SYSTEM_PROMPT,
                },
                {
                    "role": "user",
                    "content": message[:400],
                },
            ],
            temperature=0,
            max_tokens=20,
        )
        raw = (response.choices[0].message.content or "").strip()
        return raw


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _normalize(message: str) -> str:
    return re.sub(r"\s+", " ", message.strip().lower())


def _heuristic_check(normalized: str) -> RouteDecision | None:
    """
    Return a RouteDecision if the normalized text is an exact known phrase or matches
    high-confidence fast heuristics, else return None to consult the LLM.
    """
    if normalized in _EXACT_DIRECT_PHRASES:
        category = _guess_direct_category(normalized)
        return _make_direct_decision(category, f"Heuristic match for '{normalized}'.")

    # Math or obvious trivia checks -> OUT_OF_SCOPE
    if re.search(r"^\s*(what\s+is\s+)?\d+\s*[\+\-\*\/\^]\s*\d+\s*\??\s*$", normalized):
        return RouteDecision(
            route=Route.OUT_OF_SCOPE,
            reason="Heuristic: arithmetic calculation detected.",
            direct_answer=_OUT_OF_SCOPE_RESPONSE,
        )

    if re.search(
        r"\b(calculus|recipe\s+for|weather\s+in|stock\s+price|president\s+of\s+the\s+united\s+states)\b",
        normalized,
    ):
        return RouteDecision(
            route=Route.OUT_OF_SCOPE,
            reason="Heuristic: general world knowledge query.",
            direct_answer=_OUT_OF_SCOPE_RESPONSE,
        )

    # Obvious greeting + introduction fast path (without substantive org query keywords)
    has_substantive_kw = bool(
        re.search(
            r"\b(what|who|where|when|why|how|explain|role|roles|duty|duties|constitution|manual|election|elections|department|departments|ministry|ministries|pastor|pastors|elder|elders|deacon|deacons|leader|leaders|event|events|rule|rules|property|finances?|funds?|board|council|fellowship|sabbath|choir|singing)\b",
            normalized,
        )
    )

    if not has_substantive_kw:
        # Greetings / user intros
        if re.search(
            r"^(hi|hello|hey|hiya|howdy|greetings|good\s+(morning|afternoon|evening|day)|i\s*am\s+\w+|am\s+\w+|my\s*name\s*is)\b",
            normalized,
        ):
            return _make_direct_decision(
                "DIRECT_GREETING", "Heuristic: greeting/intro pattern match."
            )

        # Acknowledgements
        if re.search(
            r"^(thanks|thank\s*you|many\s*thanks|cheers|ok|okay|alright|got\s*it|understood|noted|great|cool|awesome|nice|sure)\b",
            normalized,
        ):
            return _make_direct_decision(
                "DIRECT_ACK", "Heuristic: acknowledgement pattern match."
            )

        # Farewells
        if re.search(
            r"^(bye|goodbye|see\s*you|see\s*ya|later|good\s*bye|take\s*care)\b",
            normalized,
        ):
            return _make_direct_decision(
                "DIRECT_FAREWELL", "Heuristic: farewell pattern match."
            )

    return None


def _guess_direct_category(normalized: str) -> str:
    """Crude category guess for heuristic-matched phrases."""
    farewell_words = {"bye", "goodbye", "see you", "see ya", "later", "take care", "good bye"}
    ack_words = {
        "thanks", "thank you", "thank you so much", "many thanks", "cheers",
        "ok", "okay", "ok thanks", "okay thanks", "alright", "got it",
        "understood", "noted", "great", "cool", "awesome", "nice", "sure",
    }
    identity_words = {"who are you", "what are you", "what can you do", "what do you do", "help"}

    if normalized in farewell_words:
        return "DIRECT_FAREWELL"
    if normalized in ack_words:
        return "DIRECT_ACK"
    if normalized in identity_words:
        return "DIRECT_IDENTITY"
    return "DIRECT_GREETING"


def _label_to_decision(label: str, message: str) -> RouteDecision:
    """Convert an LLM label string to a RouteDecision."""
    # Strip markdown formatting, quotes, trailing punctuation, and whitespace
    clean = re.sub(r"[^A-Z0-9_]", "", label.strip().upper())

    if "DIRECT_GREETING" in clean:
        return _make_direct_decision("DIRECT_GREETING", "LLM: greeting detected.")
    if "DIRECT_ACK" in clean:
        return _make_direct_decision("DIRECT_ACK", "LLM: acknowledgement detected.")
    if "DIRECT_FAREWELL" in clean:
        return _make_direct_decision("DIRECT_FAREWELL", "LLM: farewell detected.")
    if "DIRECT_IDENTITY" in clean:
        return _make_direct_decision("DIRECT_IDENTITY", "LLM: identity question detected.")
    if "OUT_OF_SCOPE" in clean or "OUTOF_SCOPE" in clean or "OUTOFSCOPE" in clean:
        return RouteDecision(
            route=Route.OUT_OF_SCOPE,
            reason="LLM: message is outside organization scope.",
            direct_answer=_OUT_OF_SCOPE_RESPONSE,
        )
    if "KNOWLEDGE" in clean:
        return RouteDecision(
            route=Route.KNOWLEDGE,
            reason="LLM: organizational knowledge question.",
        )
    # Default fallback if LLM returned an unrecognized label
    return RouteDecision(
        route=Route.KNOWLEDGE,
        reason=f"LLM output '{label}' default to knowledge pipeline.",
    )


def _make_direct_decision(category: str, reason: str) -> RouteDecision:
    category_to_key = {
        "DIRECT_GREETING": "greeting",
        "DIRECT_ACK": "acknowledgement",
        "DIRECT_FAREWELL": "farewell",
        "DIRECT_IDENTITY": "identity",
    }
    key = category_to_key.get(category, "fallback_direct")
    return RouteDecision(
        route=Route.DIRECT,
        reason=reason,
        direct_answer=_DIRECT_RESPONSES[key],
    )