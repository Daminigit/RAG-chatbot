"""
src/query/refusal_handler.py — Phase 2.3: Refusal Handler

Provides a standard response structure for queries classified as ADVISORY,
refusing to provide investment advice and redirecting the user to educational resources.
"""

def get_refusal_response(query: str) -> dict:
    """
    Returns a standard hardcoded JSON-like response for advisory queries,
    ensuring the bot does not provide financial advice.
    
    Args:
        query (str): The user's input string (currently unused, but allows for future logging or contextual refusals)
        
    Returns:
        dict: A structured dictionary with answer, citation, and footer.
    """
    return {
        "answer": "I'm sorry, this assistant provides facts-only information about mutual fund schemes and cannot offer investment advice or recommendations.",
        "citation": "https://www.amfiindia.com/investor-corner/knowledge-center",
        "footer": "Facts-only. No investment advice. | Last updated from sources: N/A"
    }
