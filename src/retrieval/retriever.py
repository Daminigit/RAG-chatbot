"""
src/retrieval/retriever.py — Phase 3.1 & 3.2: Vector Retriever with MMR

Extracts query intent to apply metadata pre-filtering, then retrieves
documents using Maximal Marginal Relevance (MMR) to ensure diversity.
"""

import logging
from typing import Any

from src.ingestion.embedder import get_chroma_collection, get_embedding_model

logger = logging.getLogger(__name__)

# Dictionary for mapping natural language fund mentions to exact chunk fund_keys
FUND_KEYWORD_MAPPING = {
    "mid cap": "hdfc_mid_cap",
    "small cap": "hdfc_small_cap",
    "gold": "hdfc_gold_etf_fof",
    "large cap": "hdfc_large_cap",
    "elss": "hdfc_elss",
    "tax saver": "hdfc_elss",
    "tax saving": "hdfc_elss",
}

def extract_fund_filter(query: str) -> dict[str, str] | None:
    """
    Lightweight keyword extractor to detect if the query is about a specific fund.
    
    Args:
        query (str): The user's query.
        
    Returns:
        dict: A metadata filter dict e.g., {"fund_key": "hdfc_mid_cap"} or None.
    """
    query_lower = query.lower()
    
    for keyword, fund_key in FUND_KEYWORD_MAPPING.items():
        if keyword in query_lower:
            logger.info("Metadata pre-filter applied: fund_key='%s'", fund_key)
            return {"fund_key": fund_key}
            
    return None

def retrieve(query: str, k: int = 5, fetch_k: int = 20, lambda_mult: float = 0.5) -> list[dict[str, Any]]:
    """
    Retrieve documents relevant to the query using MMR.
    
    Args:
        query (str): The user's query.
        k (int): Final number of diverse chunks to return.
        fetch_k (int): Number of initial candidates to fetch before MMR.
        lambda_mult (float): MMR diversity factor (0=diverse, 1=relevant).
        
    Returns:
        list[dict]: A list of chunks, each dict containing "text" and "metadata".
    """
    collection = get_chroma_collection()
    model = get_embedding_model()
    
    # 1. Metadata pre-filtering
    where_filter = extract_fund_filter(query)
    
    # 2. Embed the query
    logger.info("Embedding query for retrieval...")
    query_embedding = model.encode([query])[0].tolist()
    
    # 3. Retrieve using Chroma's built-in functionality
    # Note: If there are fewer than fetch_k documents (e.g. empty DB), handle gracefully
    try:
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=fetch_k,
            where=where_filter,
            include=["documents", "metadatas", "distances", "embeddings"]
        )
    except Exception as e:
        logger.error("ChromaDB query failed: %s", e)
        return []

    if not results or not results["documents"] or not results["documents"][0]:
        logger.warning("No documents found for query.")
        return []

    docs = results["documents"][0]
    metadatas = results["metadatas"][0]
    embeddings = results["embeddings"][0]
    
    # 4. Maximal Marginal Relevance (MMR) Re-ranking
    # We use langchain_community's utility function for this
    try:
        from langchain_community.vectorstores.utils import maximal_marginal_relevance
        import numpy as np
        
        # maximal_marginal_relevance expects numpy arrays
        query_emb_np = np.array(query_embedding)
        doc_embs_np = [np.array(emb) for emb in embeddings]
        
        # Returns indices of the selected documents
        selected_indices = maximal_marginal_relevance(
            query_emb_np, doc_embs_np, lambda_mult=lambda_mult, k=min(k, len(docs))
        )
    except ImportError:
        logger.warning("langchain_community not found, falling back to top-k without MMR.")
        selected_indices = list(range(min(k, len(docs))))

    formatted_results = []
    for i in selected_indices:
        formatted_results.append({
            "text": docs[i],
            "metadata": metadatas[i],
        })
        
    logger.info("Retrieved %d diverse chunks for query.", len(formatted_results))
    return formatted_results
