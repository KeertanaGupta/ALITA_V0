from langchain_ollama import OllamaLLM
from langchain_core.prompts import PromptTemplate

# We store the active model here to avoid circular imports!
ACTIVE_MODEL = "mistral"

def set_active_model(model_name: str):
    """Updates the active model variable."""
    global ACTIVE_MODEL
    ACTIVE_MODEL = model_name

def get_active_model_name() -> str:
    """Returns the current active model."""
    return ACTIVE_MODEL

def get_active_llm():
    """Dynamically connects to Ollama using whatever model the UI selected."""
    return OllamaLLM(model=ACTIVE_MODEL, base_url="http://localhost:11434")

def generate_answer(question: str, context_texts: list[str]) -> str:
    """Generates an answer using the currently active LLM with strict context rules."""
    local_llm = get_active_llm()
    context_str = "\n\n".join(context_texts)
    
    # --- THE STRICT PROMPT FIX ---
    template = """You are ALITA, an expert AI assistant for analyzing documents.
    You must answer the user's question using ONLY the context provided below. 
    If the answer is not contained in the context, you must clearly state: "I cannot find the answer in the provided documents."
    DO NOT use your general knowledge. DO NOT make up examples.

    Context:
    {context}
    
    Question: {question}
    
    Answer:"""
    
    prompt = PromptTemplate(
        template=template,
        input_variables=["context", "question"]
    )
    
    chain = prompt | local_llm
    
    return chain.invoke({"context": context_str, "question": question})