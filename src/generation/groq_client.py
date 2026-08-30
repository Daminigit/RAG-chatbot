"""
src/generation/groq_client.py — Phase 4.1: Groq LLM Client

Handles interactions with the Groq API for generating facts-only answers.
Includes fallback logic from the primary model to the secondary model on failure.
"""

import os
import logging
from groq import Groq

logger = logging.getLogger(__name__)

# Constants
PRIMARY_MODEL = os.environ.get("GROQ_MODEL", "qwen/qwen3.8-27b")
FALLBACK_MODEL = os.environ.get("GROQ_FALLBACK_MODEL", "openai/gpt-oss-20b")
MAX_TOKENS = 256
TEMPERATURE = 0.0

# Initialise client lazily so tests don't immediately fail if API key is missing
_client = None

def _get_client() -> Groq:
    global _client
    if _client is None:
        api_key = os.environ.get("GROQ_API_KEY")
        if not api_key:
            logger.warning("GROQ_API_KEY is not set. API calls will fail.")
        _client = Groq(api_key=api_key)
    return _client

def call_groq(system_prompt: str, context: str, question: str) -> str:
    """
    Calls the Groq API to generate an answer based on the provided context.
    Attempts to use the PRIMARY_MODEL; if it fails, falls back to FALLBACK_MODEL.
    
    Args:
        system_prompt (str): The rules the LLM must follow.
        context (str): The retrieved documents string.
        question (str): The user's query.
        
    Returns:
        str: The LLM's generated response.
    """
    client = _get_client()
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {question}"}
    ]
    
    # Attempt Primary Model
    try:
        logger.info("Calling Groq API with primary model: %s", PRIMARY_MODEL)
        response = client.chat.completions.create(
            model=PRIMARY_MODEL,
            messages=messages,
            max_tokens=MAX_TOKENS,
            temperature=TEMPERATURE,
            top_p=1.0,
        )
        return response.choices[0].message.content
        
    except Exception as e:
        logger.error("Primary model %s failed: %s. Attempting fallback.", PRIMARY_MODEL, e)
        
    # Attempt Fallback Model
    try:
        logger.info("Calling Groq API with fallback model: %s", FALLBACK_MODEL)
        response = client.chat.completions.create(
            model=FALLBACK_MODEL,
            messages=messages,
            max_tokens=MAX_TOKENS,
            temperature=TEMPERATURE,
            top_p=1.0,
        )
        return response.choices[0].message.content
        
    except Exception as e:
        logger.error("Fallback model %s failed: %s", FALLBACK_MODEL, e)
        return "I'm sorry, I am currently experiencing technical difficulties and cannot generate an answer."
