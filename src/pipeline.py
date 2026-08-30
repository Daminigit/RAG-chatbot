"""
src/pipeline.py — Phase 6: End-to-End Pipeline Integration

Orchestrates all layers (Query Processing, Retrieval, Generation, Validation)
into a single `answer_query()` entrypoint function.
"""

import logging
from src.validation.pii_scrubber import scrub_pii
from src.query.intent_classifier import classify_intent
from src.query.refusal_handler import get_refusal_response
from src.retrieval.retriever import retrieve
from src.retrieval.context_builder import build_context
from src.generation.prompt_builder import build_system_prompt, build_user_message
from src.generation.groq_client import call_groq
from src.validation.response_validator import validate_response

logger = logging.getLogger(__name__)

def answer_query(user_query: str) -> dict:
    """
    End-to-end processing of a user query through the RAG pipeline.
    
    Args:
        user_query (str): The raw input from the user.
        
    Returns:
        dict: A validated response dictionary containing "answer", "citation", and "footer".
    """
    logger.info("--- Starting Pipeline for Query: '%s...' ---", user_query[:30])
    
    # ---------------------------------------------------------
    # 1. Query Processing Layer
    # ---------------------------------------------------------
    # 1a. Scrub PII from incoming query
    clean_query = scrub_pii(user_query)
    
    # 1b. Intent classification
    intent = classify_intent(clean_query)
    if intent == "ADVISORY":
        logger.info("Pipeline short-circuited: ADVISORY query detected.")
        return get_refusal_response(clean_query)
        
    # ---------------------------------------------------------
    # 2. Retrieval Layer
    # ---------------------------------------------------------
    # Retrieve top 5 diverse chunks using MMR
    chunks = retrieve(clean_query, k=5, fetch_k=20)
    
    # Build context string and extract primary metadata
    context, source_url, scraped_at = build_context(chunks)
    
    # ---------------------------------------------------------
    # 3. Generation Layer
    # ---------------------------------------------------------
    system_prompt = build_system_prompt()
    # We do NOT use build_user_message string formatting manually before passing to call_groq,
    # because call_groq handles the formatting natively. 
    # Actually, looking at groq_client.py, it expects (system_prompt, context, question).
    
    logger.info("Calling LLM generation layer...")
    raw_answer = call_groq(system_prompt, context, clean_query)
    
    # ---------------------------------------------------------
    # 4. Validation Layer
    # ---------------------------------------------------------
    logger.info("Validating LLM response...")
    result = validate_response(raw_answer, source_url, scraped_at)
    
    logger.info("--- Pipeline Execution Complete ---")
    return result
