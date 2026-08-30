"""
src/validation/pii_scrubber.py — Phase 2.1: PII Scrubber

Detects and redacts Personally Identifiable Information (PII) using regex.
Must be applied to incoming user queries and outgoing LLM responses.
"""

import re
import logging

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# PII Regex Patterns
# ---------------------------------------------------------------------------
PII_PATTERNS = {
    # 5 letters, 4 digits, 1 letter (e.g. ABCDE1234F)
    "PAN": re.compile(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b", re.IGNORECASE),
    
    # 12 digits starting with 2-9, optional spaces/dashes (e.g. 2345 6789 0123)
    "Aadhaar": re.compile(r"\b[2-9]{1}[0-9]{3}[\s\-]?[0-9]{4}[\s\-]?[0-9]{4}\b"),
    
    # 10 digits starting with 6-9, optional +91 prefix
    "Phone": re.compile(r"(?:\+91[\-\s]?)?[6-9]\d{2}[\-\s]?\d{3}[\-\s]?\d{4}\b"),
    
    # Standard email format
    "Email": re.compile(r"\b[\w\.-]+@[\w\.-]+\.\w+\b", re.IGNORECASE),
    
    # 4 to 8 digit numbers bounded by word boundaries, often used as OTPs/PINs
    # Note: This is aggressive and might catch generic numbers, but safer for financial contexts
    "OTP_PIN": re.compile(r"\b\d{4,8}\b"),
}


def scrub_pii(text: str) -> str:
    """
    Scrub PII from the input text, replacing matches with [REDACTED].
    
    Args:
        text (str): The raw text (user query or LLM response)
        
    Returns:
        str: The redacted text
    """
    if not text:
        return text

    scrubbed_text = text
    matches_found = []

    for pii_type, pattern in PII_PATTERNS.items():
        # Find matches for logging purposes (without logging the actual PII!)
        num_matches = len(pattern.findall(scrubbed_text))
        if num_matches > 0:
            matches_found.append(f"{pii_type}:{num_matches}")
            
        # Redact
        scrubbed_text = pattern.sub("[REDACTED]", scrubbed_text)

    if matches_found:
        logger.info("PII scrubbed: %s", ", ".join(matches_found))

    return scrubbed_text
