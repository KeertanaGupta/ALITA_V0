from langchain_community.llms import Ollama
from langchain_core.prompts import PromptTemplate

# For now, we initialize our local LLM (ALITA Pro or Lite)
# Change "mistral" to "tinyllama" or "qwen2.5:1.5b" if your laptop has lower RAM!
LOCAL_LLM_MODEL = "mistral" 
local_llm = Ollama(model=LOCAL_LLM_MODEL, base_url="http://localhost:11434")

RAG_PROMPT_TEMPLATE = """
You are ALITA, an intelligent AI assistant. 
Use the following pieces of retrieved context to answer the question. 
If you don't know the answer, or if the context does not contain the answer, just say "I cannot find the answer in the provided documents." DO NOT make up an answer.

Context:
{context}

Question: {question}

Helpful Answer:"""

PROMPT = PromptTemplate(
    template=RAG_PROMPT_TEMPLATE, 
    input_variables=["context", "question"]
)

def generate_answer(question: str, context_chunks: list[str], execution_mode: str = "Pro") -> str:
    """
    Generates an answer using the specified ALITA execution tier.
    """
    formatted_context = "\n\n---\n\n".join(context_chunks)
    final_prompt = PROMPT.format(context=formatted_context, question=question)

    if execution_mode in ["Pro", "Lite"]:
        # 100% Offline Local Generation
        response = local_llm.invoke(final_prompt)
        return response.strip()
        
    elif execution_mode == "Hybrid":
        # TODO: Implement PII Stripper and secure Cloud API call here
        return "[Hybrid Mode Active] - Cloud API integration pending."
        
    else:
        raise ValueError(f"Unknown execution mode: {execution_mode}")