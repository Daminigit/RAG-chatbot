"""
tests/test_pipeline.py — Phase 6 Integration Tests

Tests the end-to-end pipeline wiring. Mocks external dependencies 
(ChromaDB, Embedder, LLM API) to ensure deterministic, fast CI testing.
"""

from unittest.mock import patch, MagicMock
from src.pipeline import answer_query

@patch("src.pipeline.retrieve")
@patch("src.pipeline.call_groq")
def test_answer_query_factual_flow(mock_call_groq, mock_retrieve):
    # Setup mocks
    mock_retrieve.return_value = [
        {"text": "Expense ratio is 0.85%.", "metadata": {"source_url": "http://groww.in/test", "scraped_at": "2024-01-01"}}
    ]
    mock_call_groq.return_value = "The expense ratio is 0.85%."
    
    # Execute
    query = "What is the expense ratio?"
    result = answer_query(query)
    
    # Assert pipeline components were called correctly
    mock_retrieve.assert_called_once_with("What is the expense ratio?", k=5, fetch_k=20)
    mock_call_groq.assert_called_once()
    
    # Assert validation constraints applied to final output
    assert "The expense ratio is 0.85%." in result["answer"]
    assert result["citation"] == "http://groww.in/test"
    assert "Facts-only." in result["footer"]
    assert "2024-01-01" in result["footer"]


@patch("src.pipeline.retrieve")
@patch("src.pipeline.call_groq")
def test_answer_query_advisory_short_circuit(mock_call_groq, mock_retrieve):
    # Execute an advisory query
    query = "Should I invest in this fund?"
    result = answer_query(query)
    
    # Assert pipeline components were skipped!
    mock_retrieve.assert_not_called()
    mock_call_groq.assert_not_called()
    
    # Assert refusal response was returned
    assert "Facts-only." in result["answer"] or "facts-only" in result["answer"].lower()
    assert "cannot offer investment advice" in result["answer"]
    assert "amfiindia.com" in result["citation"]


@patch("src.pipeline.retrieve")
@patch("src.pipeline.call_groq")
def test_answer_query_pii_scrubbing_flow(mock_call_groq, mock_retrieve):
    # Setup mocks
    mock_retrieve.return_value = [
        {"text": "Some text.", "metadata": {"source_url": "url", "scraped_at": "date"}}
    ]
    mock_call_groq.return_value = "Answer."
    
    # Execute query with a PAN
    query = "What is the NAV? My PAN is ABCDE1234F"
    result = answer_query(query)
    
    # Assert PII scrubber cleaned the input BEFORE retrieval
    args, kwargs = mock_retrieve.call_args
    cleaned_query_sent_to_retriever = args[0]
    
    assert "ABCDE1234F" not in cleaned_query_sent_to_retriever
    assert "[REDACTED]" in cleaned_query_sent_to_retriever


@patch("src.pipeline.retrieve")
@patch("src.pipeline.call_groq")
def test_answer_query_hallucination_override_flow(mock_call_groq, mock_retrieve):
    # Setup mocks
    mock_retrieve.return_value = [
        {"text": "Some text.", "metadata": {"source_url": "url", "scraped_at": "date"}}
    ]
    # LLM hallucinates advice
    mock_call_groq.return_value = "The fund is good. I recommend you should buy this fund."
    
    # Execute
    query = "What is the fund category?"
    result = answer_query(query)
    
    # Assert validator caught the hallucination and overrode the answer
    assert "I recommend" not in result["answer"]
    assert "cannot offer investment advice" in result["answer"]
