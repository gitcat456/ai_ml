import difflib
import re
from typing import NamedTuple

# Canonical Leadership Roster from official EUSDA records
LEADERSHIP_ROSTER: list[dict[str, str]] = [
    {"name": "Akumu Akumu", "role": "Church Development Committee (CDC) Head", "department": "CDC"},
    {"name": "Chrispine Abuya", "role": "Treasury Department Head", "department": "Treasury"},
    {"name": "Derick Okoth", "role": "Public Address (PA) Department Head", "department": "PA"},
    {"name": "Eunice Osebe", "role": "Nurture and Retention Department Head", "department": "Nurture and Retention"},
    {"name": "Goretty Wendoh", "role": "Secretary of EUSDA", "department": "Secretary"},
    {"name": "Harmony Muwira", "role": "Voice of Prophecy (VOP) Department Head", "department": "VOP"},
    {"name": "Henry Odondi", "role": "Medical Missionary (MM) Department Head", "department": "MM"},
    {"name": "Jacob Juma", "role": "Master Guide of EUSDA", "department": "Master Guide"},
    {"name": "James Brendard", "role": "Public Campus Ministry (PCM) Department Head", "department": "PCM"},
    {"name": "Levin Ouma", "role": "Interest and Coordination Department Head", "department": "Interest and Coordination"},
    {"name": "Lilian Adhiambo", "role": "Adventist Ladies Organization (ALO) Department Head", "department": "ALO"},
    {"name": "Moi Collince", "role": "Adventist Muslim Relations (AMR) Department Head", "department": "AMR"},
    {"name": "Otieno Elbright", "role": "Communication and Publicity (CP) Department Head", "department": "Communication and Publicity"},
    {"name": "Owino Bravon", "role": "Head Deacon", "department": "Deaconry", "co_head_with": "Violah Moraa"},
    {"name": "Revonce Ochieng", "role": "Stewardship Department Head", "department": "Stewardship"},
    {"name": "Ruth Rambeka", "role": "Welfare Department Head", "department": "Welfare"},
    {"name": "Vincent Oloo", "role": "Music Director / Music Department Head", "department": "Music"},
    {"name": "Violah Moraa", "role": "Head Deaconess", "department": "Deaconry", "co_head_with": "Owino Bravon"},
    {"name": "Elkanah Marani", "role": "Auditing Department Head", "department": "Audit"},
    {"name": "Otieno Ivone", "role": "Sabbath School Department Head", "department": "Sabbath School"},
    {"name": "Davaren Magioki", "role": "Prayer and Fellowship Department Head", "department": "Prayer and Fellowship"},
    {"name": "Molline Akoth", "role": "Personal Ministry (PM) Department Head", "department": "Personal Ministry"},
    {"name": "Kelvin Mutwiri", "role": "Social, Health & Temperance (SHT) Department Head", "department": "SHT"},
    # Class Representatives
    {"name": "Alphonce Okello", "role": "Class of 2024 (/24) He Representative", "department": "Class 2024"},
    {"name": "Noril Flavian", "role": "Class of 2024 (/24) She Representative", "department": "Class 2024"},
    {"name": "Prisca Awino", "role": "Class of 2025 (/25) She Representative", "department": "Class 2025"},
    {"name": "Brandon Luke", "role": "Class of 2025 (/25) He Representative", "department": "Class 2025"},
    {"name": "Hulda Nyambate", "role": "Class of 2023 (/23) She Representative", "department": "Class 2023"},
    {"name": "Joab Kevine", "role": "Class of 2023 (/23) He Representative", "department": "Class 2023"},
    {"name": "Esther Samantha", "role": "Class of 2026 (/26) She Representative", "department": "Class 2026"},
    {"name": "Dancan Odero", "role": "Class of 2026 (/26) He Representative", "department": "Class 2026"},
    # Ministry Heads
    {"name": "Collins Odhiambo", "role": "ROL Ministry Head", "department": "Revelation of Love"},
    {"name": "Henry Otieno", "role": "Calvary Ministry Head", "department": "Calvary Ministers"},
    {"name": "Stephen Otieno", "role": "HV Ministry Head", "department": "Heavenly Voyagers"},
    # Elders
    {"name": "Silvance Odero", "role": "First (1st) Elder", "department": "Elders Council"},
    {"name": "Samuel Obunde", "role": "Second (2nd) Elder", "department": "Elders Council"},
    {"name": "Evans Jerom", "role": "Elder", "department": "Elders Council"},
    {"name": "Prince Abert", "role": "Elder", "department": "Elders Council"},
    {"name": "Silas Maina Chege", "role": "Elder", "department": "Elders Council"},
    {"name": "Gordon Okuku", "role": "Elder", "department": "Elders Council"},
    {"name": "Philip Michael", "role": "Elder", "department": "Elders Council"},
    # Pastoral
    {"name": "Denis Otieno", "role": "Pastor / Chaplain of EUSDA", "department": "Chaplaincy"},
]

# Stop words to ignore during name matching
_NAME_STOP_WORDS = frozenset({
    "who", "is", "are", "the", "head", "of", "department", "what",
    "tell", "me", "about", "he", "she", "they", "eusda", "church",
    "leader", "director", "in", "and", "or", "to", "for"
})

# Acronym and synonym mappings for query expansion (BUG-03)
ACRONYM_SYNONYM_MAP: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\bpaybill\b", re.IGNORECASE), "M-Pesa Paybill 4072615 tithe offering"),
    (re.compile(r"\bsop\b", re.IGNORECASE), "Spirit of Prophecy"),
    (re.compile(r"\belders?\b", re.IGNORECASE), "Elders Council First Elder Second Elder"),
    (re.compile(r"\bvop\b", re.IGNORECASE), "Voice of Prophecy"),
    (re.compile(r"\bpa\b", re.IGNORECASE), "Public Address"),
    (re.compile(r"\brol\b", re.IGNORECASE), "Revelation of Love"),
    (re.compile(r"\bpcm\b", re.IGNORECASE), "Public Campus Ministry"),
    (re.compile(r"\bamr\b", re.IGNORECASE), "Adventist Muslim Relations"),
    (re.compile(r"\bsht\b", re.IGNORECASE), "Social Health Temperance"),
    (re.compile(r"\b(alo|amo)\b", re.IGNORECASE), "Adventist Ladies/Men Organization"),
    (re.compile(r"\bcdc\b", re.IGNORECASE), "Church Development Committee"),
]


def normalize_query(query: str) -> str:
    """
    Normalizes a query string:
    - Inserts a space at lower->upper boundaries (e.g. 'Who isAkumu' -> 'Who is Akumu')
    - Collapses repeated whitespace
    - Strips leading and trailing whitespace
    """
    if not query:
        return ""
    # Insert space at lower->upper boundary (CamelCase / concatenated names)
    res = re.sub(r"([a-z])([A-Z])", r"\1 \2", query)
    # Collapse multiple whitespace
    res = re.sub(r"[ \t]+", " ", res)
    return res.strip()


def candidate_names(query: str) -> list[str]:
    """
    Extract candidate full names from the leadership roster matching the query tokens.
    Handles partial names, reversed names (e.g. 'Rambeka Ruth' -> 'Ruth Rambeka'),
    and fuzzy token matches (e.g. 'Viola' -> 'Violah Moraa').
    """
    normalized = normalize_query(query)
    tokens = [
        t.lower() for t in re.findall(r"[a-zA-Z]{3,}", normalized)
        if t.lower() not in _NAME_STOP_WORDS
    ]
    if not tokens:
        return []

    matched: list[str] = []
    seen: set[str] = set()

    for entry in LEADERSHIP_ROSTER:
        full_name = entry["name"]
        roster_tokens = [t.lower() for t in full_name.split()]

        # Exact token match (any token in full name)
        match_found = False
        for q_tok in tokens:
            for r_tok in roster_tokens:
                if q_tok == r_tok:
                    match_found = True
                    break
                # Fuzzy match (e.g. Viola -> Violah, ratio > 0.8)
                if len(q_tok) >= 4 and len(r_tok) >= 4:
                    ratio = difflib.SequenceMatcher(None, q_tok, r_tok).ratio()
                    if ratio >= 0.82:
                        match_found = True
                        break
            if match_found:
                break

        if match_found and full_name not in seen:
            seen.add(full_name)
            matched.append(full_name)

    return matched


def expand_query(query: str) -> str:
    """
    Applies query expansion using acronym/synonym mapping and canonical roster names.
    Ensures short/ambiguous queries match relevant documentation chunks.
    """
    norm = normalize_query(query)
    expanded = norm

    for pattern, expansion in ACRONYM_SYNONYM_MAP:
        if pattern.search(expanded):
            # Replace or append expansion while keeping original intent
            expanded = f"{expanded} {expansion}"

    # Also add candidate roster names if matched
    cands = candidate_names(norm)
    for cand in cands:
        if cand.lower() not in expanded.lower():
            expanded = f"{expanded} {cand}"

    return normalize_query(expanded)

