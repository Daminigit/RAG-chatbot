"""
src/query/intent_classifier.py — Phase 2.2: Intent Classifier

Classifies user queries as FACTUAL, ADVISORY, or UNKNOWN based on keyword heuristics.
"""

from typing import Literal
import logging

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Keyword lists for rule-based classification
# ---------------------------------------------------------------------------
ADVISORY_KEYWORDS = [
    "should i invest", "which fund is better", "recommend", "best fund", 
    "should i buy", "which is good", "should i sell", "future return", 
    "will it grow", "is it safe to invest", "where to invest", "good time to"
]

FACTUAL_KEYWORDS = [
    "expense ratio", "exit load", "minimum sip", "lock-in", "benchmark", 
    "riskometer", "nav", "elss", "aum", "fund manager", "category", 
    "returns", "factsheet", "portfolio", "sector", "holdings"
]

IntentType = Literal["FACTUAL", "ADVISORY", "UNKNOWN"]

def classify_intent(query: str) -> IntentType:
    """
    Classify a user query to determine if it is asking for facts or advice.
    
    Rule evaluation order:
    1. If ANY advisory keyword is found -> ADVISORY
    2. If ANY factual keyword is found -> FACTUAL
    3. Else -> UNKNOWN
    
    Args:
        query (str): The user's input string.
        
    Returns:
        IntentType: "FACTUAL", "ADVISORY", or "UNKNOWN"
    """
    if not query:
        return "UNKNOWN"
        
    query_lower = query.lower()

    # 1. Check for Advisory intent first (safety boundary)
    if any(keyword in query_lower for keyword in ADVISORY_KEYWORDS):
        logger.info("Intent classified: ADVISORY (Query: '%s...')", query[:30])
        return "ADVISORY"
        
    # 2. Check for Factual intent
    if any(keyword in query_lower for keyword in FACTUAL_KEYWORDS):
        logger.info("Intent classified: FACTUAL (Query: '%s...')", query[:30])
        return "FACTUAL"
        
    # 3. Default to UNKNOWN (which upstream components should treat as FACTUAL fallback)
    logger.info("Intent classified: UNKNOWN (Query: '%s...')", query[:30])
    return "UNKNOWN"
