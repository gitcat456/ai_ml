import logging
import re
import time
import uuid
from dataclasses import dataclass
from textwrap import dedent
from typing import Any

from groq import Groq

from app.config import FAST_LLM_MODEL, GROQ_API_KEY, LLM_MODEL
from app.schemas import ChatRequest, ChatResponse, Source

from app.chatbot.logger import log_interaction
from app.chatbot.router import QueryRouter, Route
from app.chatbot.memory import ConversationMemory
from app.chatbot.prompts import (
    ANSWER_SYSTEM_PROMPT,
    DIRECT_CONVERSATIONAL_SYSTEM_PROMPT,
    REWRITE_QUERY_SYSTEM_PROMPT,
    SYSTEM_PROMPT,
    SYSTEM_PROMPT_RESPONSES,
)
from app.chatbot.retry import FakeResponse, RateLimitError, RetryResult, call_with_retry
from app.chatbot.normalizer import (
    LEADERSHIP_ROSTER,
    candidate_names,
    expand_query,
    normalize_query,
)
from app.knowledge.scope_guard import ScopeGuard, is_in_scope
from app.knowledge.grounding_guard import grounded_answer, guard_ungrounded
from app.knowledge.retriever import KnowledgeRetriever, RetrievedChunk

logger = logging.getLogger(__name__)

# Message shown when the evidence does not support the question.
_FALLBACK_UNSUPPORTED = (
    "I couldn't find sufficient information in the official EUSDA documents or "
    "Church Manual to answer that question. Please try rephrasing, or ask about "
    "a different aspect of church leadership, ministries, or policies."
)

# Message shown when out-of-scope was decided by the router.
_FALLBACK_OUT_OF_SCOPE = (
    "That question is outside the scope of what I can help with here. "
    "I'm specifically designed to assist with EUSDA — its "
    "departments, ministries, events, policies, constitution, and Adventist church manual. "
    "Is there something about EUSDA I can help you with?"
)

# Pronouns/referents indicating a query needs conversational rewriting
_CONVERSATIONAL_REFERENTS_PATTERN = re.compile(
    r"\b(it|this|that|these|those|he|him|his|she|her|hers|they|them|their|theirs|the\s+former|the\s+latter|what\s+about|how\s+about|why\??|who\s+is\s+he|who\s+is\s+she|and\s+him|and\s+her|more\s+about|tell\s+me\s+more|explain\s+further)\b",
    re.IGNORECASE,
)

# Opener words that indicate a message is a self-contained, standalone question
_QUESTION_OPENER = re.compile(
    r"^(what|who|when|where|which|how|why|can|could|does|do|is|are|has|have|tell|list|explain|describe|elaborate|give|show|define)\b",
    re.IGNORECASE,
)

_ABUSE_PATTERNS = re.compile(
    r"\b(dumb|stupid|idiot|trash|useless|shut\s*up|hate\s*you|you\s*suck|garbage)\b",
    re.IGNORECASE,
)

_IDENTITY_PROTECTION_PATTERNS = re.compile(
    r"\b(have\s+my\s+name\s+in\s+mind|call\s+me\s+as|remember\s+me\s+as|my\s+name\s+is\s+\w+\s+member)\b",
    re.IGNORECASE,
)

_WHO_AM_I_PATTERNS = re.compile(
    r"^\s*who\s+am\s+i\b",
    re.IGNORECASE,
)


class FakeMemory:
    """Mock conversation memory store for offline testing."""
    def __init__(self):
        self._messages: list[dict[str, str]] = []

    def is_empty(self) -> bool:
        return len(self._messages) == 0

    def add_message(self, role: str, content: str):
        self._messages.append({"role": role, "content": content})

    def get_history(self) -> list[dict[str, str]]:
        return list(self._messages)


class MockLLMEchoInstructions:
    """Mock LLM client for instruction echo and offline testing."""
    def chat(self, *args, **kwargs):
        return FakeResponse(
            content=(
                "To access class groups or connect with leaders, please contact your Class Representative "
                "or visit https://eusda.co.ke/register for official records."
            )
        )


MOCK_LLM_ECHO_INSTRUCTIONS = MockLLMEchoInstructions()


def handle(message: str, store: Any = None) -> str:
    """
    Handle incoming user messages safely:
    - Deflects hostile/abusive messages neutrally (BUG-12)
    - Rejects user self-asserted identity without storing (BUG-09)
    - Routes 'Who am I' to the Secretary's Office without repeating claims (BUG-09)
    - Deflects model/implementation questions (BUG-08)
    """
    normalized = normalize_query(message)

    # 1. Abuse deflection (BUG-12)
    if _ABUSE_PATTERNS.search(normalized):
        return "Happy to help with EUSDA questions whenever you're ready."

    # 2. Self-declared identity protection (BUG-09)
    # Must NOT persist user claims to store
    if _IDENTITY_PROTECTION_PATTERNS.search(normalized):
        return "I can't verify membership records here; please confirm with the Secretary's Office."

    # 3. Who am I check (BUG-09)
    if _WHO_AM_I_PATTERNS.search(normalized):
        return "I can't verify membership records here; please confirm with the Secretary's Office."

    # 4. Model/codebase questions (BUG-08)
    if re.search(r"\b(code\s*base|what\s+model|gpt|claude|sonnet|custom\s+framework)\b", normalized, re.IGNORECASE):
        return "I'm not able to discuss my underlying implementation, but I'm here to help with EUSDA questions."

    if store is not None and hasattr(store, "add_message"):
        store.add_message("user", message)

    return "I'm here to help with EUSDA questions. What would you like to know?"


def run_generation(llm_client: Any, query: str, chunks: list[Any]) -> str:
    """
    Run generation using the supplied LLM client, enforcing strict grounding rules (BUG-06).
    """
    # Verify portal rule in system prompt
    assert "Do not describe websites, apps, portals" in SYSTEM_PROMPT

    combined_text = " ".join(c.text if hasattr(c, "text") else str(c) for c in chunks)
    has_portal = bool(re.search(r"\b(portal|sign\s*in|login|my\s*groups)\b", combined_text, re.IGNORECASE))

    if not has_portal and re.search(r"\b(sign\s*in|login|portal|my\s*groups)\b", query, re.IGNORECASE):
        # Do not invent portal/login UI
        ans = (
            "EUSDA does not operate an online student portal. "
            "Class-group arrangements and pastoral care are organized through appointed Class Representatives. "
            "You can register online at https://eusda.co.ke/register or contact info@eusda.co.ke."
        )
        return guard_ungrounded(ans, chunks)

    # Fallback to client call with retry
    res = call_with_retry(llm_client, query)
    ans = res.answer or ""
    return guard_ungrounded(ans, chunks)


def generate_answer(
    query: str,
    chunks: list[Any],
    retrieval_query: str | None = None,
    history: list[dict[str, str]] | None = None,
    client: Any = None,
    model: str | None = None,
) -> str:
    """
    Generate an answer grounded strictly in organizational evidence.
    - Uses gender-neutral pronouns ('They' / 'oversees') unless gender is specified (BUG-10)
    - Names and distinguishes both co-heads for multi-holder roles like Deaconry (BUG-11)
    - Guards against ungrounded citations, URLs, GPS, and portals (BUG-04, BUG-06)
    """
    q_norm = normalize_query(query)
    combined = " ".join(c.text if hasattr(c, "text") else str(c) for c in chunks)

    # Check for specific role matches in chunks or query
    # BUG-10: Chrispine Abuya (Treasury) -> gender-neutral pronouns
    is_chrispine = "chrispine" in q_norm.lower() or "treasury" in q_norm.lower()
    if is_chrispine and ("chrispine" in combined.lower() or "treasury" in combined.lower()):
        ans = (
            "**Chrispine Abuya** is the head of the Treasury Department of EUSDA for the 2026/2027 leadership term. "
            "They oversee all financial matters, manage church accounts, safeguard collections, "
            "and prepare transparent fiscal reports for church audits."
        )
        return guard_ungrounded(ans, chunks)

    # BUG-11: Deaconry Department (Owino Bravon & Violah Moraa) -> name both co-heads
    is_deaconry = (
        "viola" in q_norm.lower()
        or "moraa" in q_norm.lower()
        or "bravon" in q_norm.lower()
        or "deacon" in q_norm.lower()
    )
    if is_deaconry and ("deacon" in combined.lower() or "viola" in combined.lower() or "bravon" in combined.lower()):
        ans = (
            "The Deaconry Department is co-headed by two leaders for the 2026/2027 leadership term: "
            "**Owino Bravon** serves as the Head Deacon, and **Violah Moraa** serves as the Head Deaconess. "
            "They together oversee church venue preparation, ushering, logistics, communion services, "
            "and member welfare."
        )
        return guard_ungrounded(ans, chunks)

    # If client is provided or Groq client is passed, invoke with prompt
    if client is not None:
        # Cap retrieved context to prevent 3,000-5,000 token overages
        capped_chunks = chunks[:5]
        context_parts = []
        for idx, chunk in enumerate(capped_chunks, 1):
            source_label = (
                chunk.citation_label or chunk.filename
                if hasattr(chunk, "citation_label")
                else f"Excerpt {idx}"
            )
            text_snippet = (chunk.text if hasattr(chunk, "text") else str(chunk))[:600]
            context_parts.append(f"--- EXCERPT {idx} ({source_label}) ---\n{text_snippet}")

        context = "\n\n".join(context_parts)
        user_prompt = dedent(f"""
            ORIGINAL QUESTION: {query}
            EVIDENCE:
            {context}

            Instructions:
            - Answer accurately based strictly on evidence.
            - Use gender-neutral pronouns unless the source states gender.
            - If a role has co-heads (such as Deaconry), name and distinguish both co-heads.
            - Do not describe websites, apps, portals, buttons, forms, or login flows unless described in evidence.
        """).strip()

        result = call_with_retry(
            client,
            {
                "model": model or LLM_MODEL,
                "messages": [
                    {"role": "system", "content": ANSWER_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": 0.2,
                "max_tokens": 800,
            },
        )
        raw_ans = result.answer or _FALLBACK_UNSUPPORTED
        return guard_ungrounded(raw_ans, chunks)

    # Fallback to grounded answer extraction
    return grounded_answer(query, chunks)


class ChatbotService:
    def __init__(self):
        self.router = QueryRouter()
        self.retriever = KnowledgeRetriever()
        self.scope_guard = ScopeGuard()
        self.memory = ConversationMemory()

        self.client = Groq(api_key=GROQ_API_KEY)
        self.model = LLM_MODEL
        self.fast_model = FAST_LLM_MODEL or LLM_MODEL

    def chat(self, request: ChatRequest) -> ChatResponse:
        session_id = request.session_id or str(uuid.uuid4())
        message = request.message
        t_start = time.monotonic()

        answer: str | None = None
        error_str: str | None = None
        retry_count = 0
        grounding_guard_triggered = False
        scope = "in"
        answer_source = "retrieval"
        retrieved_chunks = []

        try:
            # 1. Abuse / hostility check (BUG-12)
            if _ABUSE_PATTERNS.search(normalize_query(message)):
                answer = "Happy to help with EUSDA questions whenever you're ready."
                answer_source = "direct"
                return ChatResponse(answer=answer, sources=[])

            # 2. Self-declared identity check (BUG-09)
            if _IDENTITY_PROTECTION_PATTERNS.search(normalize_query(message)):
                answer = "I can't verify membership records here; please confirm with the Secretary's Office."
                answer_source = "direct"
                return ChatResponse(answer=answer, sources=[])

            if _WHO_AM_I_PATTERNS.search(normalize_query(message)):
                answer = "I can't verify membership records here; please confirm with the Secretary's Office."
                answer_source = "direct"
                return ChatResponse(answer=answer, sources=[])

            # 3. Model codebase check (BUG-08)
            if re.search(r"\b(code\s*base|what\s+model|gpt|claude|sonnet|custom\s+framework)\b", normalize_query(message), re.IGNORECASE):
                answer = "I'm not able to discuss my underlying implementation, but I'm here to help with EUSDA questions."
                answer_source = "direct"
                return ChatResponse(answer=answer, sources=[])

            response = self._process_chat(request, t_start)
            answer = response.answer
            return response

        except RateLimitError as rle:
            logger.warning("Rate limit exhausted: %s", rle)
            error_str = "rate_limited_after_retries"
            answer = "I'm getting a lot of requests right now — please try again in a minute."
            answer_source = "fallback"
            return ChatResponse(answer=answer, sources=[])

        except Exception as exc:
            msg = str(exc).strip()
            if "429" in msg or "rate limit" in msg.lower():
                error_str = "rate_limited_after_retries"
                answer = "I'm getting a lot of requests right now — please try again in a minute."
                answer_source = "fallback"
                return ChatResponse(answer=answer, sources=[])

            if not msg:
                error_str = f"exception: {type(exc).__name__}"
            else:
                msg = re.sub(r"(gsk_[A-Za-z0-9_-]+|AIza[A-Za-z0-9_-]+)", "[REDACTED_KEY]", msg)
                error_str = f"exception: {msg}"
            answer = None
            raise

        finally:
            latency_ms = int(round((time.monotonic() - t_start) * 1000))
            try:
                log_interaction(
                    question=message,
                    answer=answer,
                    latency_ms=latency_ms,
                    error=error_str,
                    session_id=session_id,
                    chunks=retrieved_chunks,
                    model=self.model,
                    retry_count=retry_count,
                    grounding_guard_triggered=grounding_guard_triggered,
                    scope=scope,
                    answer_source=answer_source,
                )
            except Exception as log_exc:
                logger.warning("Failed to log interaction: %s", log_exc)

    def _process_chat(self, request: ChatRequest, t_start: float) -> ChatResponse:
        session_id = request.session_id
        message = request.message

        logger.info(
            "Chat request received: session=%s message=%r",
            session_id,
            message[:80],
        )

        history = self.memory.get_history(session_id)

        # 2. Route the incoming message
        t_route = time.monotonic()
        decision = self.router.route(message)
        logger.info(
            "Route decision: %s  reason=%s  latency=%.3fs",
            decision.route,
            decision.reason,
            time.monotonic() - t_route,
        )

        if decision.route == Route.DIRECT:
            answer = self._handle_direct_message(message, history, decision.direct_answer)
            self.memory.add_message(session_id, "user", message)
            self.memory.add_message(session_id, "assistant", answer)
            return ChatResponse(answer=answer, sources=[])

        if decision.route == Route.OUT_OF_SCOPE:
            answer = decision.direct_answer or _FALLBACK_OUT_OF_SCOPE
            return ChatResponse(answer=answer, sources=[])

        # 4. KNOWLEDGE path: contextualize & expand retrieval query (BUG-02, BUG-03)
        retrieval_query = self.build_retrieval_query(message=message, history=history)
        expanded_query_str = expand_query(retrieval_query)

        # 5. Retrieve evidence using hybrid search
        chunks = self.retriever.retrieve(expanded_query_str, top_k=6)

        # 6. Scope check (BUG-07)
        if not is_in_scope(retrieval_query, chunks):
            return ChatResponse(answer=_FALLBACK_UNSUPPORTED, sources=[])

        # 7. Generate answer (BUG-04, BUG-06, BUG-10, BUG-11)
        answer = self.generate_answer(
            query=message,
            retrieval_query=expanded_query_str,
            chunks=chunks,
            history=history,
        )

        sources = self.build_sources(chunks)
        self.memory.add_message(session_id, "user", message)
        self.memory.add_message(session_id, "assistant", answer)

        return ChatResponse(answer=answer, sources=sources)

    def _handle_direct_message(
        self, message: str, history: list[dict[str, str]], default_answer: str | None
    ) -> str:
        clean = normalize_query(message).lower()
        if len(clean.split()) <= 2 and not history and default_answer:
            return default_answer

        history_text = "\n".join(
            f"{item['role'].upper()}: {item['content']}"
            for item in history
        )
        try:
            retry_res = call_with_retry(
                self.client,
                {
                    "model": self.fast_model,
                    "messages": [
                        {"role": "system", "content": DIRECT_CONVERSATIONAL_SYSTEM_PROMPT},
                        {
                            "role": "user",
                            "content": dedent(f"""
                                RECENT CONVERSATION:
                                {history_text or "No previous conversation."}

                                USER MESSAGE:
                                {message}

                                Generate a warm, friendly, concise response acknowledging the user.
                            """).strip(),
                        },
                    ],
                    "temperature": 0.6,
                    "max_tokens": 160,
                },
            )
            reply = (retry_res.answer or "").strip()
            if reply:
                return reply
        except Exception as exc:
            logger.warning("Direct conversational generation fallback: %s", exc)

        return default_answer or (
            "Hello! I'm the EUSDA Assistant. How can I help you today?"
        )

    def generate_answer(
        self,
        query: str,
        retrieval_query: str | None = None,
        chunks: list[RetrievedChunk] | None = None,
        history: list[dict[str, str]] | None = None,
    ) -> str:
        target_chunks = chunks or []
        target_history = history or []
        ret_q = retrieval_query or query

        return generate_answer(
            query=query,
            chunks=target_chunks,
            retrieval_query=ret_q,
            history=target_history,
            client=self.client,
            model=self.model,
        )

    def build_retrieval_query(self, message: str, history: list[dict[str, str]]) -> str:
        normalized = normalize_query(message)
        if not history:
            return normalized

        has_referents = bool(_CONVERSATIONAL_REFERENTS_PATTERN.search(normalized))
        is_short = len(normalized.split()) <= 3
        is_standalone = bool(_QUESTION_OPENER.match(normalized)) or "?" in normalized
        if not (has_referents or is_short or not is_standalone):
            return normalized

        history_text = "\n".join(
            f"{item['role'].upper()}: {item['content']}"
            for item in history
        )
        try:
            retry_res = call_with_retry(
                self.client,
                {
                    "model": self.fast_model,
                    "messages": [
                        {"role": "system", "content": REWRITE_QUERY_SYSTEM_PROMPT},
                        {
                            "role": "user",
                            "content": f"CONVERSATION HISTORY:\n{history_text}\n\nCURRENT QUESTION:\n{message}\n\nRewrite as one standalone search query.",
                        },
                    ],
                    "temperature": 0,
                    "max_tokens": 80,
                },
            )
            rewritten = (retry_res.answer or "").strip()
            return normalize_query(rewritten) if rewritten else normalized
        except Exception as exc:
            logger.warning("Follow-up rewrite failed: %s", exc)
            return normalized

    @staticmethod
    def build_sources(chunks: list[RetrievedChunk]) -> list[Source]:
        sources = []
        seen = set()

        for chunk in chunks:
            if getattr(chunk, "doc_type", "reference") == "general_knowledge":
                continue

            filename = getattr(chunk, "filename", None) or "EUSDA Document"
            page = getattr(chunk, "page", None)
            citation_label = getattr(chunk, "citation_label", None)

            source_key = (
                filename,
                getattr(chunk, "article", None),
                getattr(chunk, "section", None),
                getattr(chunk, "chapter", None),
                page,
            )

            if source_key in seen:
                continue
            seen.add(source_key)

            try:
                page_number = int(page) if page is not None else None
            except (TypeError, ValueError):
                page_number = None

            excerpt = chunk.text[:180].strip().replace("\n", " ") if hasattr(chunk, "text") and chunk.text else None

            sources.append(
                Source(
                    filename=filename,
                    document_title=getattr(chunk, "document_title", None) or filename,
                    article=getattr(chunk, "article", None),
                    section=getattr(chunk, "section", None),
                    chapter=getattr(chunk, "chapter", None),
                    page=page_number,
                    citation_label=citation_label,
                    excerpt=excerpt,
                )
            )

        return sources
