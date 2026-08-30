"""
src/validation/response_validator.py — Phase 5.1: Response Validator

Enforces output constraints on the LLM's generated response:
1. Max 3 sentences.
2. Ensure source URL is cited.
3. Replace with refusal if advisory language hallucinated.
4. Scrub PII from output.
5. Append standard footer.
"""

import re
import logging
from src.validation.pii_scrubber import scrub_pii
from src.query.refusal_handler import get_refusal_response

logger = logging.getLogger(__name__)

ADVISORY_PHRASES = [
    "i recommend", "you should", "i suggest", "best choice", 
    "better option", "good investment", "bad investment", "buy this", "sell this"
]

def _limit_to_three_sentences(text: str) -> str:
    """Splits text into sentences and returns at most the first 3."""
    # Simple regex split on sentence boundaries (. ! ?) followed by whitespace or end of string
    # We keep the punctuation attached to the sentence
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    
    # Filter out empty strings
    sentences = [s for s in sentences if s.strip()]
    
    if len(sentences) > 3:
        logger.info("Truncating LLM response from %d to 3 sentences.", len(sentences))
        sentences = sentences[:3]
        
    return " ".join(sentences).strip()


def validate_response(raw_text: str, source_url: str, scraped_at: str) -> dict:
    """
    Validates and formats the raw LLM output.
    
    Args:
        raw_text (str): The raw text from the LLM.
        source_url (str): The primary URL from the context.
        scraped_at (str): The primary timestamp from the context.
        
    Returns:
        dict: A structured response with answer, citation, and footer.
    """
    text_lower = raw_text.lower()
    
    # 1. Advisory Phrase Checker (Hallucination catch)
    if any(phrase in text_lower for phrase in ADVISORY_PHRASES):
        logger.warning("LLM hallucinated advisory language. Overriding with refusal handler.")
        return get_refusal_response("")
        
    # 2. PII Scrubber (Safety catch)
    safe_text = scrub_pii(raw_text)
    
    # 3. Sentence Limiter
    limited_text = _limit_to_three_sentences(safe_text)
    
    # 4. Source Injector
    # The LLM is instructed to append the URL, but if it forgets, we ensure it's in the citation.
    # We will strip the URL from the end of the text if the LLM appended it directly, 
    # to keep the "answer" clean, but either way it goes into "citation".
    clean_answer = limited_text
    if source_url and source_url != "N/A" and source_url in limited_text:
        # Optionally remove the raw URL from the text body to make it cleaner
        clean_answer = clean_answer.replace(source_url, "").strip()
        
    # Remove trailing colons or "Source:" prefixes the LLM might have left
    clean_answer = re.sub(r'(?i)\nsource:\s*$', '', clean_answer).strip()

    # 5. Footer Appender
    footer = f"Facts-only. No investment advice. | Last updated from sources: {scraped_at}"

    return {
        "answer": clean_answer,
        "citation": source_url,
        "footer": footer
    }
