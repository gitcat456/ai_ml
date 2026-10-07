import logging
import re
import time
from textwrap import dedent

from groq import Groq

from app.config import FAST_LLM_MODEL, GROQ_API_KEY, LLM_MODEL
from app.schemas import ChatRequest, ChatResponse, Source

from app.chatbot.router import QueryRouter, Route
from app.chatbot.memory import ConversationMemory
from app.chatbot.prompts import (
    ANSWER_SYSTEM_PROMPT,
    DIRECT_CONVERSATIONAL_SYSTEM_PROMPT,
    REWRITE_QUERY_SYSTEM_PROMPT,
)

from app.knowledge.scope_guard import ScopeGuard
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
        session_id = request.session_id
        message = request.message

        t_start = time.monotonic()
        logger.info(
            "Chat request received: session=%s message=%r",
            session_id,
            message[:80],
        )

        # 1. Load this session's conversation history.
        history = self.memory.get_history(session_id)

        # 2. Route the incoming message.
        t_route = time.monotonic()
        decision = self.router.route(message)
        logger.info(
            "Route decision: %s  reason=%s  latency=%.3fs",
            decision.route,
            decision.reason,
            time.monotonic() - t_route,
        )

        # 3a. DIRECT — safe, warm conversational response.
        if decision.route == Route.DIRECT:
            answer = self._handle_direct_message(message, history, decision.direct_answer)

            self.memory.add_message(session_id, "user", message)
            self.memory.add_message(session_id, "assistant", answer)

            logger.info(
                "DIRECT response sent: session=%s total_latency=%.3fs",
                session_id,
                time.monotonic() - t_start,
            )
            return ChatResponse(answer=answer, sources=[])

        # 3b. OUT_OF_SCOPE at routing time — no retrieval needed.
        if decision.route == Route.OUT_OF_SCOPE:
            answer = decision.direct_answer or _FALLBACK_OUT_OF_SCOPE

            logger.info(
                "OUT_OF_SCOPE response sent: session=%s total_latency=%.3fs",
                session_id,
                time.monotonic() - t_start,
            )
            return ChatResponse(answer=answer, sources=[])

        # 4. KNOWLEDGE path — build a contextualized retrieval query if needed.
        t_context = time.monotonic()
        retrieval_query = self.build_retrieval_query(
            message=message,
            history=history,
        )
        logger.info(
            "Retrieval query: latency=%.3fs query=%r",
            time.monotonic() - t_context,
            retrieval_query[:120],
        )

        # 5. Retrieve relevant organizational evidence.
        t_retrieve = time.monotonic()
        chunks = self.retriever.retrieve(retrieval_query)
        retrieve_latency = time.monotonic() - t_retrieve
        logger.info(
            "Retrieval complete: count=%d latency=%.3fs",
            len(chunks),
            retrieve_latency,
        )

        # 6. Check whether the evidence supports answering.
        t_scope = time.monotonic()
        scope_decision = self.scope_guard.check(
            query=retrieval_query,
            chunks=chunks,
        )
        logger.info(
            "Scope guard: supported=%s reason=%s latency=%.3fs",
            scope_decision.is_supported,
            scope_decision.reason,
            time.monotonic() - t_scope,
        )

        if not scope_decision.is_supported:
            logger.info(
                "Scope guard rejected: session=%s total_latency=%.3fs",
                session_id,
                time.monotonic() - t_start,
            )
            return ChatResponse(answer=_FALLBACK_UNSUPPORTED, sources=[])

        # 7. Generate an answer using evidence and history.
        t_generate = time.monotonic()
        try:
            answer = self.generate_answer(
                query=message,
                retrieval_query=retrieval_query,
                chunks=chunks,
                history=history,
            )
        except RuntimeError as exc:
            logger.error("Answer generation failed: %s", exc)
            return ChatResponse(
                answer=(
                    "I encountered an issue generating a response. "
                    "Please try again in a moment."
                ),
                sources=[],
            )

        logger.info(
            "Answer generated: latency=%.3fs",
            time.monotonic() - t_generate,
        )

        # 8. Build rich source references.
        sources = self.build_sources(chunks)

        # 9. Save the successful exchange.
        self.memory.add_message(session_id, "user", message)
        self.memory.add_message(session_id, "assistant", answer)

        logger.info(
            "Knowledge response sent: session=%s sources=%d total_latency=%.3fs",
            session_id,
            len(sources),
            time.monotonic() - t_start,
        )

        return ChatResponse(answer=answer, sources=sources)

    # -----------------------------------------------------------------------
    # Direct conversational response handling
    # -----------------------------------------------------------------------

    def _handle_direct_message(
        self, message: str, history: list[dict[str, str]], default_answer: str | None
    ) -> str:
        """
        Generate a warm, personalized conversational reply for greetings, introductions,
        or acknowledgements rather than a static canned response when context exists.
        """
        # If user simply said a single bare word like 'hello', 'hi', 'thanks', and no history:
        clean = message.strip().lower()
        if len(clean.split()) <= 2 and not history and default_answer:
            return default_answer

        # If user introduced themselves or provided context (e.g. "hello there am Denz a church member"):
        history_text = "\n".join(
            f"{item['role'].upper()}: {item['content']}"
            for item in history
        )
        try:
            response = self.client.chat.completions.create(
                model=self.fast_model,
                messages=[
                    {
                        "role": "system",
                        "content": DIRECT_CONVERSATIONAL_SYSTEM_PROMPT,
                    },
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
                temperature=0.6,
                max_tokens=160,
            )
            reply = (response.choices[0].message.content or "").strip()
            if reply:
                return reply
        except Exception as exc:
            logger.warning("Direct conversational generation fallback: %s", exc)

        return default_answer or (
            "Hello! I'm the EUSDA Assistant. How can I help you today?"
        )

    # -----------------------------------------------------------------------
    # Answer generation with rich inline citations
    # -----------------------------------------------------------------------

    def generate_answer(
        self,
        query: str,
        retrieval_query: str,
        chunks: list[RetrievedChunk],
        history: list[dict[str, str]],
    ) -> str:
        # Build the evidence context with explicit citation headers.
        context_parts = []

        for index, chunk in enumerate(chunks, start=1):
            source_label = chunk.citation_label or chunk.filename or "EUSDA Document"

            evidence = dedent(f"""
                [EVIDENCE {index}]
                Source: {source_label}

                Content:
                {chunk.text}
            """).strip()

            context_parts.append(evidence)

        context = "\n\n".join(context_parts)

        # Build recent conversation history.
        history_text = "\n".join(
            f"{item['role'].upper()}: {item['content']}"
            for item in history
        )

        # Build the prompt enforcing inline fact citations.
        user_prompt = dedent(f"""
            RECENT CONVERSATION:
            {history_text or "No previous conversation."}

            ORIGINAL USER QUESTION:
            {query}

            CONTEXTUALIZED RETRIEVAL QUERY:
            {retrieval_query}

            ORGANIZATIONAL EVIDENCE:
            {context}

            Instructions:
            - Answer the user's question clearly, thoroughly, and helpfully using the organizational evidence.
            - IMPORTANT: If the user asked about qualifications, requirements, or criteria for leadership, treat election conditions, membership requirements (e.g. baptism), term limits, conduct standards, and nominating committee criteria AS qualifications and synthesize them into a cohesive answer.
            - Format key duties, responsibilities, or sections with clean markdown bullet points.
            - FOR EVERY FACTUAL CLAIM, append an inline citation badge immediately after the full stop (e.g. `[EUSDA Constitution, Art. 4, Sec. D, p. 15]` or `[SDA Church Manual, Ch. 8, p. 74]`).
            - Do not include raw file extensions (like `.pdf`).
            - If user context (like member name) was established in recent conversation, address the member warmly.
        """).strip()

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": ANSWER_SYSTEM_PROMPT,
                },
                {
                    "role": "user",
                    "content": user_prompt,
                },
            ],
            temperature=0.2,
            max_tokens=1200,
        )

        answer = response.choices[0].message.content

        if not answer or not answer.strip():
            raise RuntimeError(
                "The answer generation model returned an empty response."
            )

        return answer.strip()

    # -----------------------------------------------------------------------
    # Follow-up query contextualization
    # -----------------------------------------------------------------------

    def build_retrieval_query(self, message: str, history: list[dict[str, str]]) -> str:
        """
        When there is conversation history, only invoke LLM rewriting if the
        message contains referential pronouns or is ambiguous. Otherwise, use
        the message directly to avoid redundant latency.
        """
        if not history:
            return message

        # Check if the query contains pronouns/referents or is very short
        has_referents = bool(_CONVERSATIONAL_REFERENTS_PATTERN.search(message))
        is_short = len(message.strip().split()) <= 3
        # Also rewrite if the message is an assertion/clarification without a clear
        # standalone question structure (no '?' and no clear question word at start)
        is_standalone_question = bool(_QUESTION_OPENER.match(message.strip())) or '?' in message
        needs_rewrite = has_referents or is_short or not is_standalone_question

        # If it's a complete standalone question without pronouns, skip LLM rewrite
        if not needs_rewrite:
            return message

        history_text = "\n".join(
            f"{item['role'].upper()}: {item['content']}"
            for item in history
        )

        try:
            response = self.client.chat.completions.create(
                model=self.fast_model,
                messages=[
                    {
                        "role": "system",
                        "content": REWRITE_QUERY_SYSTEM_PROMPT,
                    },
                    {
                        "role": "user",
                        "content": f"""
CONVERSATION HISTORY:
{history_text}

CURRENT QUESTION:
{message}

Rewrite the current question as one standalone question suitable for searching organizational documents.
""",
                    },
                ],
                temperature=0,
                max_tokens=120,
            )

            rewritten = response.choices[0].message.content

            if not rewritten or not rewritten.strip():
                logger.warning(
                    "Follow-up rewrite returned empty; using original message."
                )
                return message

            return rewritten.strip()

        except Exception as exc:
            logger.warning(
                "Follow-up rewrite failed (%s); using original message.", exc
            )
            return message

    # -----------------------------------------------------------------------
    # Source construction
    # -----------------------------------------------------------------------

    @staticmethod
    def build_sources(chunks: list[RetrievedChunk]) -> list[Source]:
        sources = []
        seen = set()

        for chunk in chunks:
            filename = chunk.filename or "EUSDA Document"
            page = chunk.page
            citation_label = chunk.citation_label

            source_key = (filename, chunk.article, chunk.section, chunk.chapter, page)

            if source_key in seen:
                continue

            seen.add(source_key)

            try:
                page_number = int(page) if page is not None else None
            except (TypeError, ValueError):
                page_number = None

            excerpt = chunk.text[:180].strip().replace("\n", " ") if chunk.text else None

            sources.append(
                Source(
                    filename=filename,
                    document_title=chunk.document_title or filename,
                    article=chunk.article,
                    section=chunk.section,
                    chapter=chunk.chapter,
                    page=page_number,
                    citation_label=citation_label,
                    excerpt=excerpt,
                )
            )

        return sources