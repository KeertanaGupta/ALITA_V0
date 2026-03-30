from langchain_ollama import OllamaLLM
from langchain_core.prompts import PromptTemplate
import json
import re

ACTIVE_MODEL = "mistral"


def set_active_model(model_name: str):
    global ACTIVE_MODEL
    ACTIVE_MODEL = model_name


def get_active_model_name() -> str:
    return ACTIVE_MODEL


def get_active_llm():
    return OllamaLLM(model=ACTIVE_MODEL, base_url="http://localhost:11434")


# ==========================================
# QUESTION TYPE DETECTION
# ==========================================
EXPLANATORY_TRIGGERS = {
    "explain", "discuss", "describe", "elaborate", "write",
    "what are", "list", "mention", "state all", "give detail",
    "tell me about", "how does", "how do", "what is the process",
    "what happens", "outline", "summarize", "summary", "working"
}


def is_explanatory(question: str) -> bool:
    q_lower = question.lower()
    return any(trigger in q_lower for trigger in EXPLANATORY_TRIGGERS)


# ==========================================
# PROMPT TEMPLATES
# Single JSON object only — no arrays, no multiple
# objects. Mistral sometimes outputs multiple JSON
# blocks when schema is too complex. Keep it flat.
# ==========================================

FACTUAL_TEMPLATE = """You are ALITA, an expert academic assistant.

Respond ONLY in a single raw JSON object. No markdown. No code fences. No extra text.

Schema:
{{
  "definition": "Clear definition from context",
  "key_point": "Important formula, relation, or key fact — or Not found in context",
  "explanation": "2-3 sentence explanation",
  "examples": "Units, examples, or conversions — or Not found in context"
}}

Rules:
- Use ONLY the provided context.
- Write Not found in context for missing fields.
- ONE JSON object only. No arrays of objects.

Context:
{context}

Question: {question}

JSON:"""


EXPLANATORY_TEMPLATE = """You are ALITA, an expert academic assistant.

Respond ONLY in a single raw JSON object. No markdown. No code fences. No extra text.

Schema:
{{
  "introduction": "What this topic is about",
  "working_principle": "How it works — step by step if available",
  "types_or_classification": "Types or classification if present — or Not found in context",
  "tools_or_components": "Key components or tools if present — or Not found in context",
  "applications": "Real world applications or examples — or Not found in context"
}}

Rules:
- Use ONLY the provided context.
- Write Not found in context for missing fields.
- ONE JSON object only. No arrays of objects.
- Be thorough — cover ALL relevant information.

Context:
{context}

Question: {question}

JSON:"""


# ==========================================
# JSON PARSER
# Finds ALL JSON objects in LLM output and
# merges them into one. This handles the case
# where Mistral returns multiple JSON blocks.
# ==========================================

def parse_and_merge_json(raw_text: str) -> dict:
    """
    Extracts all JSON objects from LLM output and merges them.
    If Mistral returns 2 objects, we merge their keys together
    so no information is lost.
    """
    # Find all JSON objects in the response
    matches = re.findall(r'\{[^{}]*\}', raw_text, re.DOTALL)

    if not matches:
        # Try broader match for nested objects
        match = re.search(r'\{.*\}', raw_text, re.DOTALL)
        if not match:
            raise ValueError("No JSON found in LLM response")
        matches = [match.group(0)]

    merged = {}
    for match in matches:
        try:
            obj = json.loads(match)
            # Merge — later keys overwrite only if earlier value was empty
            for k, v in obj.items():
                if k not in merged or merged[k] in ("", "Not found in context", None):
                    merged[k] = v
        except json.JSONDecodeError:
            continue

    if not merged:
        raise ValueError("Could not parse any valid JSON from LLM response")

    return merged


# ==========================================
# CONFIDENCE SCORING
# Based on retrieval quality, not LLM self-report.
# ==========================================

def compute_confidence(context_texts: list[str]) -> str:
    if len(context_texts) >= 4:
        return "high"
    elif len(context_texts) >= 2:
        return "medium"
    else:
        return "low"


# ==========================================
# RESPONSE FORMATTERS
# Clean markdown output — never raw JSON.
# Skips "Not found in context" fields silently.
# ==========================================

def _is_empty(value) -> bool:
    """Check if a field has no useful content."""
    if not value:
        return True
    if isinstance(value, str) and value.strip().lower() in (
        "not found in context", "n/a", "none", ""
    ):
        return True
    return False


def format_factual_answer(data: dict, confidence: str) -> str:
    sections = []

    if not _is_empty(data.get("definition")):
        sections.append(f"**Definition**\n{data['definition']}")

    if not _is_empty(data.get("key_point")):
        sections.append(f"**Key Point / Formula**\n{data['key_point']}")

    if not _is_empty(data.get("explanation")):
        sections.append(f"**Explanation**\n{data['explanation']}")

    if not _is_empty(data.get("examples")):
        sections.append(f"**Units / Examples**\n{data['examples']}")

    confidence_label = {"high": "✅ High", "medium": "⚠️ Medium", "low": "❌ Low"}.get(confidence, confidence)
    sections.append(f"*Confidence: {confidence_label}*")

    return "\n\n".join(sections)


def format_explanatory_answer(data: dict, confidence: str, question: str) -> str:
    sections = []

    # Title derived from question
    title = question.strip().rstrip("?").title()
    sections.append(f"# {title}")

    if not _is_empty(data.get("introduction")):
        sections.append(f"## Introduction\n{data['introduction']}")

    if not _is_empty(data.get("working_principle")):
        sections.append(f"## Working Principle\n{data['working_principle']}")

    if not _is_empty(data.get("types_or_classification")):
        sections.append(f"## Types / Classification\n{data['types_or_classification']}")

    if not _is_empty(data.get("tools_or_components")):
        sections.append(f"## Components / Tools\n{data['tools_or_components']}")

    if not _is_empty(data.get("applications")):
        sections.append(f"## Applications\n{data['applications']}")

    confidence_label = {"high": "✅ High", "medium": "⚠️ Medium", "low": "❌ Low"}.get(confidence, confidence)
    sections.append(f"*Confidence: {confidence_label}*")

    return "\n\n".join(sections)


# ==========================================
# MAIN GENERATE FUNCTION
# ==========================================

def generate_answer(question: str, context_texts: list[str]) -> str:
    """
    Full pipeline:
    1. Detect question type
    2. Build prompt
    3. Call LLM
    4. Parse + merge JSON (handles multiple objects)
    5. Inject confidence score
    6. Format to clean markdown
    7. Fallback to raw text if JSON fails
    """
    local_llm = get_active_llm()
    context_str = "\n\n---\n\n".join(context_texts)
    confidence = compute_confidence(context_texts)
    explanatory = is_explanatory(question)

    template = EXPLANATORY_TEMPLATE if explanatory else FACTUAL_TEMPLATE

    prompt = PromptTemplate(
        template=template,
        input_variables=["context", "question"]
    )

    chain = prompt | local_llm
    raw_response = chain.invoke({"context": context_str, "question": question})

    print(f"[ALITA] Raw LLM response:\n{raw_response[:300]}")

    try:
        data = parse_and_merge_json(raw_response)

        if explanatory:
            return format_explanatory_answer(data, confidence, question)
        else:
            return format_factual_answer(data, confidence)

    except (ValueError, json.JSONDecodeError) as e:
        print(f"[ALITA] JSON parse failed ({e}), returning formatted fallback")
        # Even on failure, don't return raw JSON — clean it up
        cleaned = re.sub(r'\{.*?\}', '', raw_response, flags=re.DOTALL).strip()
        return cleaned if cleaned else raw_response