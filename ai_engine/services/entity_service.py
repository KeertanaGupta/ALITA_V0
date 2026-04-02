# ai_engine/services/entity_service.py

from __future__ import annotations
import re
from collections import OrderedDict
from typing import Dict, List, Optional, Tuple

UNATTRIBUTED_KEY = "__UNATTRIBUTED__"

# ================================
# NOISE FILTER (STRICT)
# ================================
NOISE_TOKENS = {
    "github", "linkedin", "email", "phone", "contact", "address",
    "www", ".com", "http", "https", "resume", "cv", "profile",
    "objective", "summary", "education", "skills", "projects",
    "internship", "experience", "certifications", "achievements",
    "responsibility", "tech stack", "about", "objective:",
    "software", "engineer", "developer", "manager", "student",
    "b.tech", "btech", "analysis", "data", "system", "project"
}

# ================================
# NAME DETECTION
# ================================
NAME_LINE_RE = re.compile(r"^[A-Z][A-Za-z.'-]*(?:\s+[A-Z][A-Za-z.'-]*){1,3}$")

EXPLICIT_PATTERNS = [
    r"(?i)(?:name|full name|candidate name|student name)\s*[:\-]\s*(.+)",
    r"(?i)(?:mr|mrs|ms|miss|dr)\.?\s+(.+)",
]

QUESTION_PATTERNS = [
    r"who is ([a-z]+(?: [a-z]+){1,3})",
    r"about ([a-z]+(?: [a-z]+){1,3})",
    r"profile of ([a-z]+(?: [a-z]+){1,3})",
    r"tell me about ([a-z]+(?: [a-z]+){1,3})",
]


# ================================
# BASIC CLEANING
# ================================
def clean_line(text: str) -> str:
    return re.sub(r"\s+", " ", str(text)).strip()


def normalize(text: str) -> str:
    return clean_line(text).lower()


# ================================
# VALIDATION
# ================================
def is_noise(text: str) -> bool:
    t = text.lower()
    return any(n in t for n in NOISE_TOKENS)


def looks_like_name(text: str) -> bool:
    text = clean_line(text)

    if not text or is_noise(text):
        return False

    words = text.split()

    if len(words) < 2 or len(words) > 4:
        return False

    if any(char.isdigit() for char in text):
        return False

    if "@" in text or "http" in text:
        return False

    return bool(NAME_LINE_RE.match(text))


# ================================
# 🔥 STEP 1: EXTRACT ENTITY FROM QUESTION
# ================================
def extract_entity_from_question(question: str) -> Optional[str]:
    q = normalize(question)

    for pattern in QUESTION_PATTERNS:
        match = re.search(pattern, q)
        if match:
            return match.group(1).title()

    return None


# ================================
# 🔥 STEP 2: EXTRACT ENTITIES FROM DOCS
# ================================
def extract_candidate_entities(context_texts: List[str]) -> List[str]:
    entities = OrderedDict()

    for text in context_texts:
        lines = [clean_line(l) for l in text.splitlines() if clean_line(l)]

        for line in lines[:8]:  # only top section
            if is_noise(line):
                continue

            # Explicit label match
            for pat in EXPLICIT_PATTERNS:
                m = re.match(pat, line)
                if m:
                    name = clean_line(m.group(1))
                    if looks_like_name(name):
                        entities[name.title()] = None

            # Direct name match
            if looks_like_name(line):
                entities[line.title()] = None

    return list(entities.keys())


# ================================
# 🔥 STEP 3: ENTITY SCORING (SMART)
# ================================
def score_entity_match(question: str, entity: str) -> int:
    q = normalize(question)
    e = normalize(entity)

    score = 0

    if e in q:
        score += 5

    parts = e.split()
    if parts:
        if parts[0] in q:
            score += 2
        if parts[-1] in q:
            score += 2

    return score


# ================================
# 🔥 STEP 4: SELECT TARGET ENTITY (CRITICAL FIX)
# ================================
def select_target_entity(question: str, entities: List[str]) -> Optional[str]:
    # PRIORITY 1: explicit from question
    explicit = extract_entity_from_question(question)
    if explicit:
        return explicit

    if not entities:
        return None

    scored = [(score_entity_match(question, e), e) for e in entities]
    scored = [x for x in scored if x[0] > 0]

    if scored:
        scored.sort(reverse=True)
        return scored[0][1]

    # If only one entity exists → safe fallback
    if len(entities) == 1:
        return entities[0]

    return None


# ================================
# 🔥 STEP 5: STRICT FILTERING (MAIN FIX)
# ================================
def filter_docs_by_entity(docs, entity: str):
    if not entity:
        return []

    entity_norm = normalize(entity)
    entity_first = entity_norm.split()[0]

    filtered = []

    for doc in docs:
        owner = normalize(doc.metadata.get("owner_name", ""))
        doc_name = normalize(doc.metadata.get("document_name", ""))

        if (
            entity_norm in owner or
            entity_norm in doc_name or
            entity_first in owner or
            entity_first in doc_name
        ):
            filtered.append(doc)

    return filtered


# ================================
# 🔥 STEP 6: GROUP BY ENTITY (FOR COMPARISON)
# ================================
def build_entity_context_map(
    entities: List[str],
    context_texts: List[str]
) -> Dict[str, List[str]]:

    entity_map: Dict[str, List[str]] = {e: [] for e in entities}
    unattributed: List[str] = []

    for text in context_texts:
        assigned = False

        for entity in entities:
            if normalize(entity) in normalize(text):
                entity_map[entity].append(text)
                assigned = True

        if not assigned:
            unattributed.append(text)

    if unattributed:
        entity_map[UNATTRIBUTED_KEY] = unattributed

    return entity_map


# ================================
# 🔥 STEP 7: CONTEXT SCORING
# ================================
def score_context(question: str, text: str) -> int:
    q = normalize(question)
    t = normalize(text)

    words = re.findall(r"[a-z0-9]+", q)
    words = [w for w in words if len(w) >= 3]

    score = 0

    # unigram match
    for w in words:
        if w in t:
            score += 2

    # bigram match
    for i in range(len(words) - 1):
        phrase = f"{words[i]} {words[i+1]}"
        if phrase in t:
            score += 5

    return score


# ================================
# 🔥 STEP 8: CONFIDENCE CHECK
# ================================
def entity_confidence(entity: str, docs: list) -> float:
    if not entity or not docs:
        return 0.0

    match_count = 0

    for doc in docs:
        owner = normalize(doc.metadata.get("owner_name", ""))
        if entity.lower() in owner:
            match_count += 1

    return match_count / max(1, len(docs))