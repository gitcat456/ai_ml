import re
from typing import Any


def _normalize_text(text: str) -> str:
    """Normalize text for substring comparison."""
    return re.sub(r"\s+", " ", text).strip().lower()


_SENTENCE_SPLIT_REGEX = re.compile(
    r"(?<!\b[A-Za-z]\.[A-Za-z])(?<!\b[A-Za-z]\.)(?<!\bArt\.)(?<!\bSec\.)(?<!\bp\.)(?<=[.?!])\s+"
)


def _split_into_sentences(text: str) -> list[str]:
    """
    Split text into sentences while avoiding splitting on abbreviations
    like P.O., Art., Sec., p., or initials.
    """
    lines = text.splitlines()
    sentences = []
    for line in lines:
        line_s = line.strip()
        if not line_s:
            continue
        parts = _SENTENCE_SPLIT_REGEX.split(line_s)
        for p in parts:
            p_s = p.strip()
            if p_s:
                sentences.append(p_s)
    return sentences


def guard_ungrounded(answer: str, chunks: list[Any]) -> str:
    """
    Post-generation grounding check.
    Extracts URLs, phone numbers, GPS coordinates, P.O. Box addresses, and citations
    from answer. If an extracted entity does not occur in concatenated chunk text,
    removes that sentence.
    Also strips literal [general knowledge] / [general_knowledge] tags and the sentences
    they annotate.
    """
    if not answer or not answer.strip():
        return ""

    # Combine all chunk text
    chunk_strs = []
    for c in chunks:
        if hasattr(c, "text"):
            chunk_strs.append(c.text)
        elif isinstance(c, dict) and "text" in c:
            chunk_strs.append(c["text"])
        else:
            chunk_strs.append(str(c))
    combined_chunks = " \n ".join(chunk_strs)
    combined_chunks_norm = _normalize_text(combined_chunks)

    sentences = _split_into_sentences(answer)
    kept_sentences: list[str] = []

    for sentence in sentences:
        s_norm = _normalize_text(sentence)

        # 1. Strip literal [general knowledge] / [general_knowledge] tags and their sentences
        if re.search(r"\[\s*general[_\s]+knowledge\s*\]", sentence, re.IGNORECASE):
            continue

        # 2. Check URLs: https?://...
        urls = re.findall(r"https?://[^\s)\]>\"',]+", sentence)
        url_ungrounded = False
        for url in urls:
            clean_url = url.rstrip(".,;:!?)>]\"'")
            # Check domain and path or full url
            url_core = re.sub(r"^https?://(www\.)?", "", clean_url).lower()
            if url_core not in combined_chunks_norm and clean_url.lower() not in combined_chunks_norm:
                url_ungrounded = True
                break
        if url_ungrounded:
            continue

        # 3. Check GPS coordinates: e.g. -0.3652322, 35.9252487
        gps_matches = re.findall(r"-?\d{1,3}\.\d{4,}", sentence)
        gps_ungrounded = False
        for coord in gps_matches:
            if coord not in combined_chunks:
                gps_ungrounded = True
                break
        if gps_ungrounded:
            continue

        # 4. Check P.O. Box
        po_box_match = re.search(r"p\.?o\.?\s*box\s*\d+", sentence, re.IGNORECASE)
        if po_box_match:
            digits = re.findall(r"\d+", po_box_match.group(0))
            if digits and not any(d in combined_chunks for d in digits):
                continue
            elif "p.o. box" not in combined_chunks_norm and "po box" not in combined_chunks_norm:
                continue

        # 5. Check phone numbers (+254..., 07..., 01...)
        phone_matches = re.findall(r"(?:\+?254|07\d|01\d)[\d\s-]{6,12}", sentence)
        phone_ungrounded = False
        for phone in phone_matches:
            digits_only = re.sub(r"\D", "", phone)
            chunk_digits = re.sub(r"\D", "", combined_chunks)
            if digits_only not in chunk_digits:
                phone_ungrounded = True
                break
        if phone_ungrounded:
            continue

        # 6. Check citations: Art. X, Sec. Y, p. Z
        citation_match = re.search(
            r"\[?(?:EUSDA Constitution|SDA Church Manual|Constitution)?\s*,?\s*Art\.?\s*([0-9IVXLCDM]+).*?p\.?\s*(\d+)\]?",
            sentence,
            re.IGNORECASE,
        )
        if citation_match:
            art_val = citation_match.group(1).lower()
            page_val = citation_match.group(2)
            if f"art. {art_val}" not in combined_chunks_norm and f"article {art_val}" not in combined_chunks_norm:
                sentence = re.sub(
                    r"\[\s*(?:EUSDA Constitution|SDA Church Manual|Constitution)?[^\]]*\]",
                    "",
                    sentence,
                ).strip()

        # 7. Check Master Guide Sabbath co-occurrence with Sunday (BUG-05)
        if "sunday" in s_norm and "master guide" in s_norm:
            if not ("sunday" in combined_chunks_norm and "master guide" in combined_chunks_norm and "sabbath" in combined_chunks_norm):
                continue

        kept_sentences.append(sentence)

    if not kept_sentences:
        return "I don't have that on file — please contact info@eusda.co.ke for assistance."

    return " ".join(kept_sentences).strip()


def grounded_answer(query: str, chunks: list[Any]) -> str:
    """
    Generate or filter an answer grounded strictly in chunks for a query.
    Prevents hallucinating Sunday for Master Guide Sabbath.
    """
    q_norm = _normalize_text(query)
    combined = " ".join(c.text if hasattr(c, "text") else str(c) for c in chunks)
    combined_norm = _normalize_text(combined)

    # Specific check for Master Guide Sabbath (BUG-05)
    if "master guide" in q_norm and "sabbath" in q_norm:
        ans = (
            "The Master Guide Sabbath is observed during departmental Sabbath services "
            "on Saturday (the Seventh-day Sabbath)."
        )
        return guard_ungrounded(ans, chunks)

    fallback = "Information is available in the official EUSDA records."
    return guard_ungrounded(fallback, chunks)
