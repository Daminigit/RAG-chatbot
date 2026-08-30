"""
src/retrieval/context_builder.py — Phase 3.3: Context Builder

Formats retrieved document chunks into a single, cohesive context string
for the LLM, complete with source citations.
"""

def build_context(retrieved_docs: list[dict]) -> tuple[str, str, str]:
    """
    Concatenate chunks into a single context string.
    
    Args:
        retrieved_docs: List of dicts, each with "text" and "metadata"
        
    Returns:
        tuple containing:
            - context_string (str): The formatted context for the LLM.
            - primary_source_url (str): The URL of the highest-ranked chunk.
            - primary_scraped_at (str): The timestamp of the primary chunk.
    """
    if not retrieved_docs:
        return "", "N/A", "N/A"

    context_parts = []
    
    for doc in retrieved_docs:
        meta = doc.get("metadata", {})
        fund_name = meta.get("fund_name", "Unknown Fund")
        url = meta.get("source_url", "N/A")
        text = doc.get("text", "")
        
        # Build the block for this chunk
        block = f"[Source: {fund_name} | {url}]\n{text}"
        context_parts.append(block)

    # Join blocks with double newlines
    context_string = "\n\n".join(context_parts)
    
    # Extract primary metadata from the first (highest-ranked) chunk
    primary_meta = retrieved_docs[0].get("metadata", {})
    primary_url = primary_meta.get("source_url", "N/A")
    primary_scraped_at = primary_meta.get("scraped_at", "N/A")
    
    return context_string, primary_url, primary_scraped_at
