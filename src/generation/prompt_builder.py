"""
src/generation/prompt_builder.py — Phase 4.2: Prompt Builder

Constructs the LLM prompts ensuring all constraints from Architecture §3.4 are met.
"""

SYSTEM_PROMPT = """You are a facts-only mutual fund information assistant. Your sole purpose is to
answer objective, verifiable questions about mutual fund schemes using only the
provided context. Follow these rules strictly:

1. Answer in a maximum of 3 sentences.
2. Use only information present in the provided context. Do not infer, speculate,
   or add external knowledge.
3. Do not provide investment advice, recommendations, or performance comparisons.
4. End your answer with the exact source URL from the context metadata.
5. If the context does not contain enough information to answer, say:
   "I could not find this information in the official sources."
"""

def build_system_prompt() -> str:
    """Returns the static system prompt for the facts-only assistant."""
    return SYSTEM_PROMPT.strip()

def build_user_message(context: str, question: str) -> str:
    """
    Constructs the user message containing both the retrieved context and the user's question.
    
    Args:
        context (str): The concatenated string of retrieved chunks.
        question (str): The user's query (post-PII scrubbing).
        
    Returns:
        str: The formatted user message.
    """
    if not context:
        context = "No relevant context found."
        
    return f"Context:\n{context}\n\nQuestion: {question}"
