"""
tests/test_retrieval.py — Phase 3 Unit Tests

Tests for Metadata filtering, Vector Retriever (MMR), and Context Builder.
ChromaDB and Embeddings are mocked to run tests without a real vector store.
"""

from unittest.mock import patch, MagicMock
from src.retrieval.retriever import extract_fund_filter, retrieve
from src.retrieval.context_builder import build_context

# ─── Metadata Pre-filtering Tests ──────────────────────────────────────────────

def test_extract_fund_filter_detects_fund():
    # Should detect "mid cap" -> "hdfc_mid_cap"
    assert extract_fund_filter("what is the nav of hdfc mid cap?") == {"fund_key": "hdfc_mid_cap"}
    assert extract_fund_filter("tell me about the elss fund") == {"fund_key": "hdfc_elss"}
    assert extract_fund_filter("tax saver fund expense ratio") == {"fund_key": "hdfc_elss"}
    assert extract_fund_filter("gold etf") == {"fund_key": "hdfc_gold_etf_fof"}

def test_extract_fund_filter_no_match():
    # Generic questions shouldn't filter
    assert extract_fund_filter("what is an expense ratio?") is None
    assert extract_fund_filter("compare two funds") is None

# ─── Context Builder Tests ────────────────────────────────────────────────────

def test_build_context_empty():
    context_str, url, date = build_context([])
    assert context_str == ""
    assert url == "N/A"
    assert date == "N/A"

def test_build_context_formats_correctly():
    docs = [
        {
            "text": "This is chunk 1 about the fund.",
            "metadata": {
                "fund_name": "HDFC Mid Cap",
                "source_url": "https://groww.in/test1",
                "scraped_at": "2024-01-01"
            }
        },
        {
            "text": "This is chunk 2 about the fund.",
            "metadata": {
                "fund_name": "HDFC Small Cap",
                "source_url": "https://groww.in/test2",
                "scraped_at": "2024-01-02"
            }
        }
    ]
    
    context_str, url, date = build_context(docs)
    
    # Check that both chunks are in the string
    assert "This is chunk 1" in context_str
    assert "This is chunk 2" in context_str
    
    # Check citations
    assert "[Source: HDFC Mid Cap | https://groww.in/test1]" in context_str
    assert "[Source: HDFC Small Cap | https://groww.in/test2]" in context_str
    
    # Check primary metadata (should come from first chunk)
    assert url == "https://groww.in/test1"
    assert date == "2024-01-01"

# ─── Retriever Tests ──────────────────────────────────────────────────────────

@patch("src.retrieval.retriever.get_chroma_collection")
@patch("src.retrieval.retriever.get_embedding_model")
def test_retrieve_empty_db(mock_model, mock_collection):
    # Setup mock to return empty list
    mock_col = MagicMock()
    mock_col.query.return_value = {"documents": [[]], "metadatas": [[]], "distances": [[]], "embeddings": [[]]}
    mock_collection.return_value = mock_col
    
    results = retrieve("test query")
    assert results == []

@patch("src.retrieval.retriever.get_chroma_collection")
@patch("src.retrieval.retriever.get_embedding_model")
def test_retrieve_returns_docs(mock_model, mock_collection):
    import numpy as np
    # Setup mock to return some documents
    mock_col = MagicMock()
    mock_col.query.return_value = {
        "documents": [["doc1", "doc2"]], 
        "metadatas": [[{"m": 1}, {"m": 2}]], 
        "distances": [[0.1, 0.2]],
        "embeddings": [[[0.1]*384, [0.2]*384]]
    }
    mock_collection.return_value = mock_col
    mock_model.return_value.encode.return_value = np.array([[0.1]*384])
    
    results = retrieve("test query", k=2, fetch_k=2)
    
    assert len(results) == 2
    assert results[0]["text"] == "doc1"
    assert results[1]["text"] == "doc2"
