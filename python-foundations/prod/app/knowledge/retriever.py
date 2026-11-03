import logging
import re
from dataclasses import dataclass

from qdrant_client import QdrantClient
from qdrant_client.http import models

from app.config import (
    EMBEDDING_DIM,
    QDRANT_API_KEY,
    QDRANT_COLLECTION,
    QDRANT_URL,
)
from app.knowledge.embeddings import BaseEmbeddingProvider, get_embedding_provider

logger = logging.getLogger(__name__)

# Stop words excluded from keyword extraction — common question/filler words.
_STOP_WORDS: frozenset[str] = frozenset({
    "who", "what", "where", "when", "why", "how", "is", "are", "was",
    "were", "the", "a", "an", "of", "in", "for", "to", "and", "or",
    "do", "does", "can", "could", "tell", "me", "about", "please",
    "explain", "describe", "list", "give", "show", "find", "role",
    "his", "her", "he", "she", "it", "they", "their", "this", "that",
    "with", "from", "by", "on", "at", "be", "been", "being", "have",
    "has", "had", "not", "but", "if", "my", "our", "your",
})


# Role variants and abbreviations mapping to ensure user queries match
# both constitutional terms and directory/roster listings.
_ROLE_VARIANTS: dict[str, list[str]] = {
    "treasurer": ["treasury", "treasurer"],
    "treasury": ["treasurer", "treasury"],
    "deacon": ["deaconry", "deacon"],
    "deaconry": ["deacon", "deaconry"],
    "communication": ["communication", "publicity", "cp"],
    "publicity": ["communication", "publicity", "cp"],
    "director": ["head", "director"],
    "head": ["head", "director"],
    "music": ["music", "choir"],
    "choir": ["music", "choir"],
    "welfare": ["welfare"],
    "stewardship": ["stewardship"],
    "secretary": ["secretary"],
    "masterguide": ["masterguide"],
    "pastor": ["pastor"],
    "elder": ["elder", "elders"],
    "campus": ["pcm", "campus"],
    "pcm": ["pcm", "campus"],
    "missionary": ["mm", "medical", "missionary"],
    "vop": ["vop", "prophecy"],
    "prophecy": ["vop", "prophecy"],
    "development": ["cdc", "development"],
    "cdc": ["cdc", "development"],
    "address": ["pa", "address"],
    "pa": ["pa", "address"],
    "retention": ["nurture", "retention"],
    "nurture": ["nurture", "retention"],
    "coordination": ["interest", "coordination"],
    "interest": ["interest", "coordination"],
    "voyagers": ["heavenly", "voyagers"],
    "calvary": ["calvary"],
    "revelation": ["revelation", "rol"],
    "rol": ["revelation", "rol"],
}

_LEADERSHIP_ROLE_PATTERNS = re.compile(
    r"\b(who\s+is|who\s+are|who\s+leads|who\s+heads|head|director|leader|treasurer|treasury|deacon|deaconry|secretary|masterguide|elder|pastor|chair|chairman|coordinator|officer|official|representative|rep|minister|ministry|in\s+charge)\b",
    re.IGNORECASE,
)

_PAGE_PATTERN = re.compile(r"\b(?:page|p\.?)\s*(\d+)\b", re.IGNORECASE)
_SECTION_PATTERN = re.compile(r"\b(?:section|sec\.?)\s*([a-zA-Z0-9]+)\b", re.IGNORECASE)
_ARTICLE_PATTERN = re.compile(r"\b(?:article|art\.?)\s*([a-zA-Z0-9]+)\b", re.IGNORECASE)


def format_document_title(filename: str | None) -> str:
    """Format a user-friendly document name without raw file extensions."""
    if not filename:
        return "EUSDA Document"
    clean = filename
    # Strip extensions
    clean = re.sub(r"\.(pdf|txt|md)$", "", clean, flags=re.IGNORECASE)
    lower = clean.lower()
    if "constitution" in lower:
        return "EUSDA Constitution"
    if "church_manual" in lower or "church manual" in lower:
        return "SDA Church Manual"
    # General cleanup: replace underscores/dashes with spaces, title case
    clean = re.sub(r"[_\-]+", " ", clean).strip()
    return clean.title() if clean.islower() else clean


def extract_structural_context(
    text: str, filename: str | None, page: int | None
) -> tuple[str, str | None, str | None, str | None, str]:
    """Extract Article, Section, Chapter, and a clean citation label."""
    doc_title = format_document_title(filename)
    article = None
    section = None
    chapter = None

    art_match = re.search(
        r"\b(ARTICLE\s+[0-9IVXLCDM]+(?::\s*[^\n\r]+|\b[^\n\r]*))",
        text,
        re.IGNORECASE,
    )
    if art_match:
        article = re.sub(r"\s+", " ", art_match.group(1)).strip()

    sec_match = re.search(
        r"\b(Section\s+[A-Z0-9]+(?::\s*[^\n\r]+|\b[^\n\r]*))",
        text,
        re.IGNORECASE,
    )
    if sec_match:
        section = re.sub(r"\s+", " ", sec_match.group(1)).strip()

    chap_match = re.search(
        r"\b(Chapter\s+[0-9IVXLCDM]+(?::\s*[^\n\r]+|\b[^\n\r]*))",
        text,
        re.IGNORECASE,
    )
    if chap_match:
        chapter = re.sub(r"\s+", " ", chap_match.group(1)).strip()

    parts = [doc_title]
    if chapter:
        c_short = re.search(r"Chapter\s+([0-9IVXLCDM]+)", chapter, re.IGNORECASE)
        parts.append(f"Ch. {c_short.group(1)}" if c_short else chapter)
    if article:
        a_short = re.search(r"ARTICLE\s+([0-9IVXLCDM]+)", article, re.IGNORECASE)
        parts.append(f"Art. {a_short.group(1)}" if a_short else article)
    if section:
        s_short = re.search(r"Section\s+([A-Z0-9]+)", section, re.IGNORECASE)
        parts.append(f"Sec. {s_short.group(1)}" if s_short else section)
    if page is not None:
        parts.append(f"p. {page}")

    citation_label = ", ".join(parts)
    return doc_title, article, section, chapter, citation_label


@dataclass(frozen=True)
class RetrievedChunk:
    text: str
    filename: str | None = None
    document_title: str | None = None
    article: str | None = None
    section: str | None = None
    chapter: str | None = None
    page: int | None = None
    score: float | None = None
    citation_label: str | None = None
    doc_type: str = "reference"


class KnowledgeRetriever:
    """
    Retrieves relevant organizational document chunks from Qdrant Cloud
    using hybrid search: vector similarity + keyword text matching.

    This ensures that queries containing specific names or terms (e.g.
    "Who is Prisca Okoth?") find the right chunks even when embedding
    similarity is low for proper nouns.
    """

    def __init__(
        self,
        embedding_provider: BaseEmbeddingProvider | None = None,
        qdrant_client: QdrantClient | None = None,
        collection_name: str | None = None,
    ):
        self.embedding_provider = embedding_provider
        self.client = qdrant_client
        self.collection_name = collection_name or QDRANT_COLLECTION
        self._vector_name: str | None = None
        self._initialized = False

    def _load_index(self):
        """
        Initialize the embedding provider and Qdrant client connection.
        Verifies collection dimensions and vector naming.
        """
        if self._initialized:
            return

        if not self.embedding_provider:
            self.embedding_provider = get_embedding_provider()

        if not self.client:
            if not QDRANT_URL or not QDRANT_API_KEY:
                raise RuntimeError(
                    "QDRANT_URL and QDRANT_API_KEY must be set in environment."
                )
            self.client = QdrantClient(
                url=QDRANT_URL,
                api_key=QDRANT_API_KEY,
                timeout=20.0,
            )

        # Inspect collection configuration
        try:
            coll_info = self.client.get_collection(self.collection_name)
            vectors_config = coll_info.config.params.vectors

            # Check if vector configuration is a dict with named vectors or single VectorParams
            if isinstance(vectors_config, dict):
                # If there's an empty key '', it's the default unnamed vector
                if "" not in vectors_config and len(vectors_config) > 0:
                    self._vector_name = list(vectors_config.keys())[0]
                    v_params = vectors_config[self._vector_name]
                else:
                    v_params = vectors_config.get("")
            else:
                v_params = vectors_config

            if v_params and hasattr(v_params, "size"):
                if v_params.size != EMBEDDING_DIM:
                    logger.warning(
                        "Qdrant collection '%s' vector dimension (%d) does not match EMBEDDING_DIM (%d).",
                        self.collection_name,
                        v_params.size,
                        EMBEDDING_DIM,
                    )
            logger.info(
                "Connected to Qdrant Cloud collection '%s' (points: %d, vector_name: %s)",
                self.collection_name,
                coll_info.points_count or 0,
                self._vector_name or "<default>",
            )

            # Ensure full-text payload index exists on 'text' field for keyword/hybrid search
            schema = getattr(coll_info, "payload_schema", {}) or {}
            if "text" not in schema:
                try:
                    self.client.create_payload_index(
                        collection_name=self.collection_name,
                        field_name="text",
                        field_schema=models.TextIndexParams(
                            type="text",
                            tokenizer=models.TokenizerType.WORD,
                            lowercase=True,
                        ),
                    )
                    logger.info("Ensured full-text payload index on 'text' in '%s'.", self.collection_name)
                except Exception as idx_exc:
                    logger.warning("Could not auto-create payload index on 'text': %s", idx_exc)

            # Ensure integer payload index exists on 'page' field
            if "page" not in schema:
                try:
                    self.client.create_payload_index(
                        collection_name=self.collection_name,
                        field_name="page",
                        field_schema=models.PayloadSchemaType.INTEGER,
                    )
                    logger.info("Ensured integer payload index on 'page' in '%s'.", self.collection_name)
                except Exception as idx_exc:
                    logger.warning("Could not auto-create payload index on 'page': %s", idx_exc)
        except Exception as exc:
            logger.warning(
                "Could not verify Qdrant collection '%s' at startup (%s). Will attempt retrieval on demand.",
                self.collection_name,
                exc,
            )

        self._initialized = True

    # -------------------------------------------------------------------
    # Keyword extraction
    # -------------------------------------------------------------------

    @staticmethod
    def _extract_meaningful_terms(query: str) -> list[str]:
        """Extract meaningful (non-stop-word) terms from a query string."""
        words = re.findall(r"[a-zA-Z]{2,}", query)
        return [w for w in words if w.lower() not in _STOP_WORDS]

    @staticmethod
    def _terms_found_in_points(terms: list[str], points: list) -> bool:
        """Check whether the meaningful query terms appear in any of the
        retrieved point payloads."""
        if not terms:
            return True  # nothing to check

        combined_text = " ".join(
            (p.payload or {}).get("text", "").lower() for p in points
        )

        # Check bigrams (multi-word names like "Prisca Okoth")
        lower_terms = [t.lower() for t in terms]
        if len(lower_terms) >= 2:
            for i in range(len(lower_terms) - 1):
                bigram = f"{lower_terms[i]} {lower_terms[i + 1]}"
                if bigram in combined_text:
                    return True

        # Check majority of individual terms
        matched = sum(1 for t in lower_terms if t in combined_text)
        return matched >= max(len(lower_terms) * 0.6, 1)

    # -------------------------------------------------------------------
    # Vector search
    # -------------------------------------------------------------------

    def _vector_search(self, query_vector: list[float], limit: int) -> list:
        """Run a pure vector similarity search against Qdrant."""
        if hasattr(self.client, "query_points"):
            response = self.client.query_points(
                collection_name=self.collection_name,
                query=query_vector,
                using=self._vector_name,
                limit=limit,
            )
            return response.points
        else:
            return self.client.search(
                collection_name=self.collection_name,
                query_vector=(
                    (self._vector_name, query_vector)
                    if self._vector_name
                    else query_vector
                ),
                limit=limit,
            )

    # -------------------------------------------------------------------
    # Keyword (text-match) search
    # -------------------------------------------------------------------

    def _keyword_search(
        self,
        terms: list[str],
        limit: int,
        exclude_ids: set | None = None,
        doc_type_filter: str | None = None,
    ) -> list:
        """
        Search for chunks whose text payload contains the given terms
        using Qdrant's MatchText filter (substring match via scroll).

        This is the fallback for proper-noun / name queries where vector
        similarity fails. For small collections this is fast (linear scan).
        """
        if not terms:
            return []

        # Build filter: any term should match (OR / "should" logic)
        should_conditions = []
        for term in terms:
            should_conditions.append(
                models.FieldCondition(
                    key="text",
                    match=models.MatchText(text=term),
                )
            )

        must_conditions = []
        if doc_type_filter:
            must_conditions.append(
                models.FieldCondition(
                    key="doc_type",
                    match=models.MatchValue(value=doc_type_filter),
                )
            )

        scroll_filter = models.Filter(
            should=should_conditions,
            must=must_conditions or None,
        )

        try:
            results, _ = self.client.scroll(
                collection_name=self.collection_name,
                scroll_filter=scroll_filter,
                limit=limit * 3,  # fetch extra, we'll filter and trim
                with_payload=True,
                with_vectors=False,
            )

            # Exclude points already found by vector search
            if exclude_ids:
                results = [r for r in results if str(r.id) not in exclude_ids]

            # Score by how many terms match (more matches = more relevant)
            def _term_match_count(point):
                text_lower = ((point.payload or {}).get("text", "")).lower()
                return sum(1 for t in terms if t.lower() in text_lower)

            results.sort(key=_term_match_count, reverse=True)
            return results[:limit]

        except Exception as exc:
            logger.warning(
                "Keyword search failed (MatchText may need a text index): %s. "
                "Falling back to vector-only results.",
                exc,
            )
            return []

    # -------------------------------------------------------------------
    # Main retrieval entry point — hybrid search
    # -------------------------------------------------------------------

    def retrieve(self, query: str, top_k: int = 8) -> list[RetrievedChunk]:
        """
        Retrieve top-k relevant chunks using hybrid search:
          1. Vector similarity search (semantic)
          2. Keyword text-match search (exact terms, especially names and roles)
          3. Merge with keyword matches prioritized, deduplicated
        """
        self._load_index()

        if not query or not query.strip():
            return []

        # 1. Generate query embedding via Gemini
        query_vector = self.embedding_provider.embed_query(query)

        # 2. Vector search
        try:
            vector_points = self._vector_search(query_vector, top_k)
        except Exception as exc:
            logger.error("Qdrant vector retrieval error: %s", exc)
            raise RuntimeError(f"Vector search failed: {exc}") from exc

        # 3. Hybrid search enhancements:
        meaningful_terms = self._extract_meaningful_terms(query)
        keyword_points = []

        is_leadership = bool(_LEADERSHIP_ROLE_PATTERNS.search(query))
        has_general_knowledge = any(
            (p.payload or {}).get("doc_type") == "general_knowledge"
            for p in vector_points
        )
        terms_missing = bool(
            meaningful_terms
            and not self._terms_found_in_points(meaningful_terms, vector_points)
        )

        # Expand terms with role synonyms / abbreviations (e.g., treasurer -> treasury)
        expanded_terms = set(meaningful_terms)
        for term in meaningful_terms:
            t_low = term.lower()
            if t_low in _ROLE_VARIANTS:
                expanded_terms.update(_ROLE_VARIANTS[t_low])

        vector_ids = {str(p.id) for p in vector_points}

        # Case A: If user is asking about leadership/roles/heads and vector results
        # contain only reference documents (which lack current holder names),
        # pull matching general_knowledge roster chunks directly.
        if is_leadership and not has_general_knowledge:
            search_terms = list(expanded_terms) if expanded_terms else ["leadership", "head", "director", "chair", "chairman"]
            gk_points = self._keyword_search(
                search_terms,
                limit=3,
                exclude_ids=vector_ids,
                doc_type_filter="general_knowledge",
            )
            if gk_points:
                logger.info(
                    "Leadership query detected without roster chunks; pulled %d general_knowledge chunks.",
                    len(gk_points),
                )
                keyword_points.extend(gk_points)

        # Case B: If specific terms (like names or specific words) are missing from vector results
        if terms_missing:
            logger.info(
                "Query terms %s not found in vector results; running keyword search.",
                meaningful_terms,
            )
            kw_points = self._keyword_search(
                list(expanded_terms),
                top_k,
                exclude_ids=vector_ids.union({str(p.id) for p in keyword_points}),
            )
            keyword_points.extend(kw_points)

        # Case C: Structural citations (e.g. "page 32", "section H", "article 6")
        structural_points = []
        page_match = _PAGE_PATTERN.search(query)
        section_match = _SECTION_PATTERN.search(query)
        article_match = _ARTICLE_PATTERN.search(query)

        if page_match or (section_match and article_match):
            must_filters = []
            if page_match:
                must_filters.append(
                    models.FieldCondition(
                        key="page",
                        match=models.MatchValue(value=int(page_match.group(1))),
                    )
                )

            should_filters = []
            if section_match:
                should_filters.append(
                    models.FieldCondition(
                        key="text",
                        match=models.MatchText(text=f"Section {section_match.group(1)}"),
                    )
                )
            if article_match:
                should_filters.append(
                    models.FieldCondition(
                        key="text",
                        match=models.MatchText(text=f"Article {article_match.group(1)}"),
                    )
                )

            try:
                s_filter = models.Filter(
                    must=must_filters or None,
                    should=should_filters or None,
                )
                res, _ = self.client.scroll(
                    collection_name=self.collection_name,
                    scroll_filter=s_filter,
                    limit=5,
                    with_payload=True,
                    with_vectors=False,
                )
                if res:
                    sec_term = f"section {section_match.group(1).lower()}" if section_match else ""
                    art_term = f"article {article_match.group(1).lower()}" if article_match else ""
                    def _struct_score(p):
                        t = ((p.payload or {}).get("text", "")).lower()
                        score = 0
                        if sec_term and sec_term in t:
                            score += 2
                        if art_term and art_term in t:
                            score += 1
                        return score
                    res.sort(key=_struct_score, reverse=True)
                    structural_points = res
                    logger.info("Structural query matched %d points in Qdrant.", len(structural_points))
            except Exception as s_exc:
                logger.warning("Structural scroll failed: %s", s_exc)

        # 4. Merge: structural matches first, keyword matches next,
        #    then vector results, deduplicated, limited to top_k.
        seen_ids: set[str] = set()
        merged_points = []

        for point in structural_points + keyword_points + list(vector_points):
            pid = str(point.id)
            if pid not in seen_ids:
                seen_ids.add(pid)
                merged_points.append(point)

        merged_points = merged_points[:top_k]

        # 5. Parse retrieved points into RetrievedChunk objects
        return self._parse_points(merged_points)

    # -------------------------------------------------------------------
    # Point → RetrievedChunk parsing
    # -------------------------------------------------------------------

    def _parse_points(self, points: list) -> list[RetrievedChunk]:
        """Convert raw Qdrant point objects into RetrievedChunk instances."""
        results = []
        for point in points:
            payload = point.payload or {}
            content = payload.get("text") or ""
            raw_filename = payload.get("source") or payload.get("filename")
            raw_page = payload.get("page")

            try:
                page_num = int(raw_page) if raw_page is not None else None
            except (ValueError, TypeError):
                page_num = None

            # Fallback metadata extraction if not stored in payload
            doc_title = payload.get("document_title")
            article = payload.get("article")
            section = payload.get("section")
            chapter = payload.get("chapter")
            citation_label = payload.get("citation_label")
            doc_type = payload.get("doc_type")
            if not doc_type:
                # Fallback: .txt or .md files are general knowledge, .pdf are reference
                doc_type = (
                    "general_knowledge"
                    if (raw_filename and raw_filename.lower().endswith((".txt", ".md")))
                    else "reference"
                )

            if not doc_title or not citation_label:
                (
                    extracted_doc_title,
                    extracted_art,
                    extracted_sec,
                    extracted_chap,
                    extracted_label,
                ) = extract_structural_context(content, raw_filename, page_num)
                doc_title = doc_title or extracted_doc_title
                article = article or extracted_art
                section = section or extracted_sec
                chapter = chapter or extracted_chap
                citation_label = citation_label or extracted_label

            clean_filename = format_document_title(raw_filename)

            results.append(
                RetrievedChunk(
                    text=content,
                    filename=clean_filename,
                    document_title=doc_title,
                    article=article,
                    section=section,
                    chapter=chapter,
                    page=page_num,
                    score=float(point.score) if hasattr(point, "score") and point.score is not None else None,
                    citation_label=citation_label,
                    doc_type=doc_type,
                )
            )

        return results
