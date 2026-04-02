"""ALITA LLM Service
=================
A production-oriented local LLM formatter for document QA.

Architecture:
Rule Engine -> Entity Binding -> Prompt -> JSON/Markdown Formatting
"""

from __future__ import annotations

import json
import re
from typing import Optional

from langchain_core.prompts import PromptTemplate
from langchain_ollama import OllamaLLM

from services.entity_service import (
    build_entity_context_map,
    clean_line,
    extract_candidate_entities,
    score_context,
    UNATTRIBUTED_KEY,
)

ACTIVE_MODEL = "mistral"


def set_active_model(model_name: str):
    global ACTIVE_MODEL
    ACTIVE_MODEL = model_name


def get_active_model_name() -> str:
    return ACTIVE_MODEL


def get_active_llm():
    return OllamaLLM(model=ACTIVE_MODEL, base_url="http://localhost:11434")


SYSTEM_PROMPT = """
You are ALITA, a precision document-analysis assistant.

Follow these rules:
- Use only the provided context.
- Do not invent facts, names, dates, ranks, or achievements.
- Do not mix facts across people or documents.
- Be direct, structured, and concise.
- If the answer is incomplete, say what is missing.
- If conversation history is given, use it only for pronouns and follow-ups.
- Never output raw Python list syntax like ['a', 'b'].
"""


CONVERSATIONAL_TRIGGERS = {
    "who is", "tell me about", "something about", "introduce", "background",
    "profile", "experience", "skills", "education", "qualification",
    "achievement", "career", "internship", "resume", "cv", "about this person",
}

EXPLANATORY_TRIGGERS = {
    "explain", "discuss", "describe", "elaborate", "how does", "how do",
    "what is the process", "what happens", "outline", "working of",
    "working principle", "write a note", "give detail", "state all", "why does",
}

EXTRACTION_TRIGGERS = {
    "list", "show all", "extract", "find all", "mention all", "give all",
    "all the", "names of", "projects", "skills", "certifications",
    "achievements", "publications", "subjects", "tools used", "components",
}

STYLE_MAP = {
    "in short": "short",
    "in brief": "short",
    "briefly": "short",
    "short": "short",
    "brief": "short",
    "concise": "short",
    "quick": "short",
    "in detail": "detailed",
    "in details": "detailed",
    "detailed": "detailed",
    "complete": "detailed",
    "full": "detailed",
    "elaborate": "detailed",
    "thoroughly": "detailed",
    "comprehensive": "detailed",
}

MODE_MATRIX = {
    ("comparison", "short"): "decision_short",
    ("comparison", "normal"): "decision_detailed",
    ("comparison", "detailed"): "decision_detailed",
    ("extraction", "short"): "extract_short",
    ("extraction", "normal"): "extract_detailed",
    ("extraction", "detailed"): "extract_detailed",
    ("explanatory", "short"): "explain_short",
    ("explanatory", "normal"): "explain_detailed",
    ("explanatory", "detailed"): "explain_detailed",
    ("conversational", "short"): "bio_short",
    ("conversational", "normal"): "bio_detailed",
    ("conversational", "detailed"): "bio_detailed",
    ("factual", "short"): "fact_short",
    ("factual", "normal"): "fact_detailed",
    ("factual", "detailed"): "fact_detailed",
}

CRITERION_PATTERNS = [
    r"who (?:has|have|cleared|won|secured|achieved|got|completed|done|passed|qualified for|participated in|ranked in)\s+(.+)",
    r"which .* (?:has|have|cleared|won|secured|achieved|got|completed)\s+(.+)",
    r"who (?:is|are) (?:the )?(?:best|top|highest|strongest|weakest|most)\s+(.+)",
    r"who (?:has|have) (?:experience|knowledge|skills?) (?:in|with|of)\s+(.+)",
    r"who (?:worked|works|interned|studied) (?:at|in|on)\s+(.+)",
]


# ------------------------------------------------------------------
# Intent, style, and routing
# ------------------------------------------------------------------

def normalize_text(text: str) -> str:
    text = str(text).lower()
    text = text.replace("+", " plus ").replace("&", " and ")
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def detect_question_type(question: str) -> str:
    q = normalize_text(question)

    if re.search(r"\bwho\s+is\b", q):
        return "conversational"
    if re.search(r"\bwho\s+(has|have|cleared|won|secured|achieved|got|completed|passed|ranked|qualified)\b", q):
        return "comparison"
    if re.search(r"\bcompare\b|\bbetween\b|\bamong\b|\bdifference\b", q):
        return "comparison"

    if any(t in q for t in EXTRACTION_TRIGGERS):
        return "extraction"
    if any(t in q for t in CONVERSATIONAL_TRIGGERS):
        return "conversational"
    if any(t in q for t in EXPLANATORY_TRIGGERS):
        return "explanatory"
    return "factual"


def is_explanatory(question: str) -> bool:
    return detect_question_type(question) in ("explanatory", "conversational", "comparison", "extraction")


def detect_style(question: str) -> str:
    q = question.lower()
    for key, val in STYLE_MAP.items():
        if key in q:
            return val
    return "normal"


def get_mode(q_type: str, style: str) -> str:
    return MODE_MATRIX.get((q_type, style), "fact_detailed")


def extract_criterion(question: str) -> str:
    q = question.lower().rstrip("?").strip()

    for pattern in CRITERION_PATTERNS:
        match = re.search(pattern, q)
        if match:
            criterion = match.group(match.lastindex).strip()
            criterion = re.sub(r"\b(the|a|an|that|this|it)\b$", "", criterion).strip()
            return criterion

    stopwords = {
        "who", "which", "what", "have", "has", "the", "a", "an",
        "is", "are", "cleared", "won", "achieved", "got", "done",
        "been", "did", "do", "does", "of", "in", "on", "at",
    }
    words = [w for w in q.split() if w not in stopwords and len(w) > 2]
    return " ".join(words[:5]) if words else ""


# ------------------------------------------------------------------
# History / follow-ups
# ------------------------------------------------------------------

def format_conversation_history(conversation_history: Optional[list[dict]] = None) -> str:
    if not conversation_history:
        return ""

    turns = []
    for msg in conversation_history[-6:]:
        role = str(msg.get("role", "")).strip().lower()
        content = str(msg.get("content", "")).strip()
        if not content:
            continue

        if role == "assistant":
            label = "Assistant"
        elif role == "user":
            label = "User"
        else:
            label = role.title() or "Message"
        turns.append(f"{label}: {content}")

    return "\n".join(turns)


def suggest_followups(question: str, q_type: str, entities: Optional[list[str]] = None) -> list[str]:
    entities = entities or []
    if q_type == "comparison":
        if len(entities) >= 2:
            return [
                f"Compare {entities[0]} and {entities[1]} on projects or certifications.",
                "Show a side-by-side summary.",
            ]
        return [
            "Compare their projects and certifications.",
            "Show me the strongest candidate overall.",
        ]

    if q_type == "conversational":
        return [
            "Summarize this person’s skills in one line.",
            "List the top projects and certifications.",
        ]

    if q_type == "explanatory":
        return [
            "Give me the short version.",
            "List the key components or steps again.",
        ]

    if q_type == "extraction":
        return [
            "Sort these items by importance.",
            "Show only the strongest matches.",
        ]

    return ["Give a shorter answer.", "Explain it with one example."]


def append_followups(answer: str, followups: list[str], enabled: bool = True, short_mode: bool = False) -> str:
    if not enabled or short_mode or not followups:
        return answer
    block = "\n\n**Next questions you can ask**\n" + "\n".join(f"• {q}" for q in followups[:2])
    return answer.rstrip() + block


# ------------------------------------------------------------------
# Prompt templates
# ------------------------------------------------------------------

BIO_SHORT = SYSTEM_PROMPT + """
You are writing a concise profile summary for one person.

Return ONLY this JSON:
{{
  "summary": "2-3 sentence natural summary"
}}

Rules:
- Use only the context.
- Write naturally, like a strong professional profile.
- Do not output Python list syntax.
- Do not invent missing facts.

Context:
{context}

Question: {question}
JSON:
"""

BIO_DETAILED = SYSTEM_PROMPT + """
You are writing a polished, resume-style profile for one person.

Return ONLY this JSON:
{{
  "summary": "2-3 sentence introduction",
  "education": ["Education fact 1", "Education fact 2"],
  "technical_profile": ["Skill or tool 1", "Skill or tool 2"],
  "projects": ["Project 1", "Project 2"],
  "achievements": ["Achievement 1", "Achievement 2"],
  "additional_info": ["Any other important detail"]
}}

Rules:
- Use only the context.
- Be polished and human-readable.
- Keep only facts supported by the context.
- Do not copy raw chunk text verbatim.
- Do not use Python list syntax in the final answer; the formatter will convert it.
- If a section has no evidence, return an empty list.

Context:
{context}

Question: {question}
JSON:
"""

FACT_SHORT = SYSTEM_PROMPT + """
You are answering a factual question.

Return ONLY this JSON:
{{
  "definition": "Direct 1-2 line answer"
}}

Rules:
- Use only the context.
- No extra text.

Context:
{context}

Question: {question}
JSON:
"""

FACT_DETAILED = SYSTEM_PROMPT + """
You are answering a factual question.

Return ONLY this JSON:
{{
  "definition": "Clear definition from context",
  "key_point": "Key fact or formula — or Not found in context",
  "explanation": "2-3 sentence explanation",
  "examples": "Units, examples, or applications — or Not found in context"
}}

Rules:
- Use only the context.
- If something is missing, say "Not found in context".
- Stay grounded.

Context:
{context}

Question: {question}
JSON:
"""

EXPLAIN_SHORT = SYSTEM_PROMPT + """
You are an expert assistant.

Return ONLY this JSON:
{{
  "summary": "Concise answer in 3-4 lines"
}}

Rules:
- Use only the context.
- Be clear and direct.

Context:
{context}

Question: {question}
JSON:
"""

EXPLAIN_DETAILED = SYSTEM_PROMPT + """
You are an expert academic assistant.

Return ONLY this JSON:
{{
  "introduction": "What this topic is about",
  "working_principle": "How it works step by step — or Not found in context",
  "types_or_classification": "Types or classification if present — or Not found in context",
  "tools_or_components": "Key components or tools if present — or Not found in context",
  "applications": "Applications or examples if present — or Not found in context"
}}

Rules:
- Use only the context.
- Cover all relevant points present.

Context:
{context}

Question: {question}
JSON:
"""

EXTRACT_SHORT = SYSTEM_PROMPT + """
You are an information extraction assistant.

Return ONLY this JSON:
{{
  "items": ["Item 1", "Item 2", "Item 3"]
}}

Rules:
- Extract only the most relevant items.
- Deduplicate.
- Keep it short.

Context:
{context}

Question: {question}
JSON:
"""

EXTRACT_DETAILED = SYSTEM_PROMPT + """
You are an information extraction assistant.

Return ONLY this JSON:
{{
  "summary": "Short summary of what was extracted",
  "items": ["Item 1", "Item 2", "Item 3"],
  "grouped_by_entity": [
    {{
      "entity": "Name or document label",
      "items": ["Relevant item 1", "Relevant item 2"]
    }}
  ]
}}

Rules:
- Use only the context.
- If entities are present, group items under the correct entity.
- If nothing is found, return empty arrays.

Context:
{context}

Question: {question}
JSON:
"""

DECISION_SHORT = SYSTEM_PROMPT + """
You are answering a comparison / decision question.
The rule engine has already evaluated each person.
Use the pre-evaluated results only.

{pre_evaluated}

Return ONLY this JSON:
{{
  "final_answer": "Full name(s) who match",
  "reason": "One line with exact evidence"
}}

Question: {question}
JSON:
"""

DECISION_DETAILED = SYSTEM_PROMPT + """
You are answering a comparison / decision question.
The rule engine has already evaluated each person against the criterion.
Your job is to format the result clearly.

Do NOT re-evaluate.
Do NOT contradict the pre-evaluated results.

{pre_evaluated}

Entity context for evidence extraction:
{entity_context}

Return ONLY this JSON:
{{
  "final_answer": "Full name(s) who match, or None of the above",
  "evaluation": [
    {{
      "entity": "Full Name",
      "status": "Match or No Match",
      "evidence": "Exact quote from the person’s section above, or No mention found"
    }}
  ],
  "conclusion": "1-2 sentence direct explanation. Mention both who matched and who did not."
}}

Rules:
- Use the pre-evaluated results as ground truth.
- Extract exact evidence quotes from the entity context sections.
- Name both matched and unmatched entities explicitly.

Question: {question}
JSON:
"""

TEMPLATE_MAP = {
    "decision_short": DECISION_SHORT,
    "decision_detailed": DECISION_DETAILED,
    "extract_short": EXTRACT_SHORT,
    "extract_detailed": EXTRACT_DETAILED,
    "explain_short": EXPLAIN_SHORT,
    "explain_detailed": EXPLAIN_DETAILED,
    "bio_short": BIO_SHORT,
    "bio_detailed": BIO_DETAILED,
    "fact_short": FACT_SHORT,
    "fact_detailed": FACT_DETAILED,
}


# ------------------------------------------------------------------
# JSON parser and formatters
# ------------------------------------------------------------------

def _strip_code_fences(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


def parse_json(raw_text: str) -> dict:
    raw_text = _strip_code_fences(raw_text)
    try:
        return json.loads(raw_text)
    except Exception:
        pass

    match = re.search(r"\{.*\}", raw_text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except Exception:
            pass

    matches = re.findall(r"\{[^{}]*\}", raw_text, re.DOTALL)
    merged = {}
    for m in matches:
        try:
            obj = json.loads(m)
            for k, v in obj.items():
                if k not in merged or merged[k] in ("", None, "Not found in context"):
                    merged[k] = v
        except json.JSONDecodeError:
            continue

    if merged:
        return merged

    raise ValueError("No valid JSON in LLM response")


def _empty(val) -> bool:
    if not val:
        return True
    if isinstance(val, str) and val.strip().lower() in (
        "not found in context", "n/a", "none", "", "not mentioned",
        "not available", "none of the above", "no match",
    ):
        return True
    return False


def _as_lines(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return []
        if text.startswith("[") and text.endswith("]"):
            try:
                parsed = json.loads(text.replace("'", '"'))
                if isinstance(parsed, list):
                    return [str(v).strip() for v in parsed if str(v).strip()]
            except Exception:
                pass
        return [text]
    return [str(value).strip()]


def fmt_decision_short(data: dict) -> str:
    final = data.get("final_answer", "")
    reason = data.get("reason", "")
    lines = [f"🎯 **Final Answer**\n👉 {final if not _empty(final) else 'No match found in documents'}"]
    if not _empty(reason):
        lines.append(f"\n**Reason**\n{reason}")
    return "\n".join(lines)


def fmt_decision_detailed(data: dict) -> str:
    lines = []
    final = data.get("final_answer", "")
    if not _empty(final):
        lines.append(f"🎯 **Final Answer**\n👉 {final}\n")
    else:
        lines.append("🎯 **Final Answer**\n👉 No match found in the provided documents.\n")

    for item in data.get("evaluation", []):
        entity = item.get("entity", "Unknown")
        status = item.get("status", "")
        evidence = item.get("evidence", "No mention found")
        is_match = "match" in status.lower() and "no" not in status.lower()
        sym = "✅" if is_match else "❌"
        lines.append(f"{sym} **{entity}**\n   {evidence}\n")

    conclusion = data.get("conclusion", "")
    if not _empty(conclusion):
        lines.append(f"💡 **Conclusion**\n{conclusion}")
    return "\n".join(lines)


def fmt_extract_short(data: dict) -> str:
    items = _as_lines(data.get("items", []))
    if not items:
        return "No items found in the provided documents."
    return "\n".join([f"• {i}" for i in items])


def fmt_extract_detailed(data: dict) -> str:
    lines = []
    summary = data.get("summary", "")
    items = _as_lines(data.get("items", []))
    grouped = data.get("grouped_by_entity", [])

    if not _empty(summary):
        lines.append(f"**Summary**\n{summary}")

    if items:
        lines.append("\n**Items**")
        for i in items:
            lines.append(f"• {i}")

    if grouped:
        lines.append("\n**Grouped by Entity**")
        for group in grouped:
            entity = group.get("entity", "Unknown")
            group_items = _as_lines(group.get("items", []))
            lines.append(f"\n**{entity}**")
            for gi in group_items:
                lines.append(f"• {gi}")

    return "\n".join(lines).strip() if lines else "No items found in the provided documents."


def fmt_explain_short(data: dict) -> str:
    return data.get("summary", "")


def fmt_explain_detailed(data: dict, question: str) -> str:
    s = [f"# {question.strip().rstrip('?').title()}"]
    for key, label in [
        ("introduction", "Introduction"),
        ("working_principle", "Working Principle"),
        ("types_or_classification", "Types / Classification"),
        ("tools_or_components", "Components / Tools"),
        ("applications", "Applications"),
    ]:
        if not _empty(data.get(key)):
            s.append(f"## {label}\n{data[key]}")
    return "\n\n".join(s)


def fmt_bio_short(data: dict) -> str:
    return data.get("summary", "")


def fmt_bio_detailed(data: dict) -> str:
    s = []
    if not _empty(data.get("summary")):
        s.append(data["summary"])

    section_map = [
        ("education", "Education"),
        ("technical_profile", "Technical Profile"),
        ("projects", "Projects"),
        ("achievements", "Achievements"),
        ("additional_info", "Additional Information"),
    ]

    for key, label in section_map:
        items = _as_lines(data.get(key, []))
        if items:
            s.append(f"\n**{label}**")
            for item in items:
                s.append(f"• {item}")

    return "\n".join(s).strip()


def fmt_fact_short(data: dict) -> str:
    return data.get("definition", "")


def fmt_fact_detailed(data: dict) -> str:
    s = []
    for key, label in [
        ("definition", "**Definition**"),
        ("key_point", "**Key Point / Formula**"),
        ("explanation", "**Explanation**"),
        ("examples", "**Units / Examples**"),
    ]:
        if not _empty(data.get(key)):
            s.append(f"{label}\n{data[key]}")
    return "\n\n".join(s)


def clean_output(text: str) -> str:
    text = text.replace("°C/", "°Cl").replace("°C)", "°Cl)")
    text = text.replace("Ib", "lb")
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = "\n".join(line.rstrip() for line in text.split("\n"))
    return text.strip()


def validate_answer(answer: str, question: str, entities: list | None = None) -> bool:
    q = question.lower()
    a = answer.lower()

    if re.search(r"\bwho\b", q):
        if entities and len(entities) > 1:
            mentions = sum(1 for e in entities if e.split()[0].lower() in a)
            if mentions < 1:
                return False
    return True


def compute_confidence(context_texts: list[str]) -> str:
    n = len(context_texts)
    if n >= 4:
        return "high"
    if n >= 2:
        return "medium"
    return "low"

def build_entity_context_string(entity_map: dict, context_texts: list[str], history_block: str = "") -> str:
    """
    Builds structured context grouped by entity for comparison prompts.
    """

    sections = []

    if history_block:
        sections.append(f"Conversation history:\n{history_block}\n")

    for entity, texts in entity_map.items():
        if not texts:
            continue

        # Limit chunk size per entity
        joined = "\n---\n".join(texts[:4])
        sections.append(f"=== {entity} ===\n{joined}")

    # Fallback (rare case)
    if not sections and context_texts:
        return "\n\n---\n\n".join(context_texts[:6])

    return "\n\n".join(sections)
# ------------------------------------------------------------------
# Main generation
# ------------------------------------------------------------------

def generate_answer(
    question: str,
    context_texts: list[str],
    entities: list[str] | None = None,
    conversation_history: Optional[list[dict]] = None,
    include_followups: bool = True,
) -> str:
    local_llm = get_active_llm()
    q_type = detect_question_type(question)
    style = detect_style(question)
    mode = get_mode(q_type, style)

    print(f"[ALITA] Type:{q_type} | Style:{style} | Mode:{mode}")

    context_texts = sorted(context_texts, key=lambda x: score_context(question, x), reverse=True)
    history_block = format_conversation_history(conversation_history)

    resolved_entities = entities or []
    resolved_entities = [
        e for e in resolved_entities
        if len(e.split()) >= 2
        and "github" not in e.lower()
        and "linkedin" not in e.lower()
        and "email" not in e.lower()
        and "www" not in e.lower()
    ]

    if q_type == "comparison":
        if not resolved_entities:
            resolved_entities = extract_candidate_entities(context_texts)
        resolved_entities = [
            e for e in resolved_entities
            if len(e.split()) >= 2
            and "github" not in e.lower()
            and "linkedin" not in e.lower()
            and "email" not in e.lower()
            and "www" not in e.lower()
        ][:6]

        if not resolved_entities:
            return "I could not identify distinct individuals in the provided documents to compare."

        criterion = extract_criterion(question)
        entity_map = build_entity_context_map(resolved_entities, context_texts)
        pre_evaluated = []
        criterion_norm = normalize_text(criterion)
        criterion_words = [w for w in criterion_norm.split() if len(w) > 2]

        for entity in resolved_entities:
            texts = entity_map.get(entity, [])
            combined = normalize_text(" ".join(texts))
            matched = False
            evidence = "No mention found"

            if criterion_norm and criterion_norm in combined:
                matched = True
                evidence = f"Criterion '{criterion}' found in document"
            elif criterion_words:
                hit_count = sum(1 for w in criterion_words if w in combined)
                if hit_count >= max(1, len(criterion_words) // 2):
                    matched = True
                    evidence = f"Criterion '{criterion}' found in document"

            pre_evaluated.append((entity, matched, evidence))

        entity_context_str = build_entity_context_string(entity_map, context_texts, history_block=history_block)
        pre_eval_text = "\n".join(
            [
                f"CRITERION: {criterion}",
                "PRE-EVALUATED RESULTS:",
                *[
                    f"- {entity}: {'MATCH' if matched else 'NO MATCH'}\n  Evidence: {evidence}"
                    for entity, matched, evidence in pre_evaluated
                ],
            ]
        )

        prompt = PromptTemplate(
            template=DECISION_DETAILED if mode != "decision_short" else DECISION_SHORT,
            input_variables=["pre_evaluated", "entity_context", "question"] if mode != "decision_short" else ["pre_evaluated", "question"],
        )
        chain = prompt | local_llm
        raw = str(chain.invoke({
            "pre_evaluated": pre_eval_text,
            "entity_context": entity_context_str,
            "question": question,
        } if mode != "decision_short" else {
            "pre_evaluated": pre_eval_text,
            "question": question,
        }))

        try:
            data = parse_json(raw)
            candidate = fmt_decision_short(data) if mode == "decision_short" else fmt_decision_detailed(data)
            candidate = clean_output(candidate)
            if validate_answer(candidate, question, resolved_entities):
                answer = candidate
            else:
                answer = clean_output(raw)
        except Exception:
            answer = clean_output(raw)

        followups = suggest_followups(question, q_type, resolved_entities)
        return append_followups(answer, followups, enabled=include_followups, short_mode=(style == "short"))

    # Non-comparison path
    history_prefix = f"Conversation history:\n{history_block}\n\n" if history_block else ""
    context_str = history_prefix + "\n\n---\n\n".join(context_texts[:8])

    template_map = {
        "extract_short": EXTRACT_SHORT,
        "extract_detailed": EXTRACT_DETAILED,
        "explain_short": EXPLAIN_SHORT,
        "explain_detailed": EXPLAIN_DETAILED,
        "bio_short": BIO_SHORT,
        "bio_detailed": BIO_DETAILED,
        "fact_short": FACT_SHORT,
        "fact_detailed": FACT_DETAILED,
    }
    template = template_map.get(mode, FACT_DETAILED)

    prompt = PromptTemplate(template=template, input_variables=["context", "question"])
    chain = prompt | local_llm
    raw = str(chain.invoke({"context": context_str, "question": question}))

    answer = None
    try:
        data = parse_json(raw)
        if mode == "extract_short":
            candidate = fmt_extract_short(data)
        elif mode == "extract_detailed":
            candidate = fmt_extract_detailed(data)
        elif mode == "explain_short":
            candidate = fmt_explain_short(data)
        elif mode == "explain_detailed":
            candidate = fmt_explain_detailed(data, question)
        elif mode == "bio_short":
            candidate = fmt_bio_short(data)
        elif mode == "bio_detailed":
            candidate = fmt_bio_detailed(data)
        elif mode == "fact_short":
            candidate = fmt_fact_short(data)
        else:
            candidate = fmt_fact_detailed(data)

        candidate = clean_output(candidate)
        if candidate.strip():
            answer = candidate
    except Exception:
        cleaned = re.sub(r"\{.*?\}", "", raw, flags=re.DOTALL).strip()
        if cleaned:
            answer = clean_output(cleaned)

    answer = answer or "I couldn't find a confident answer in the provided documents."
    followups = suggest_followups(question, q_type, resolved_entities if resolved_entities else entities)
    return append_followups(answer, followups, enabled=include_followups, short_mode=(style == "short"))
