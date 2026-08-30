"""
tests/test_validation.py — Phase 5 Unit Tests

Tests for the Response Validator constraints.
"""

from src.validation.response_validator import validate_response

# ─── Response Validator Tests ──────────────────────────────────────────────────

def test_validate_response_under_limit():
    raw = "The expense ratio is 0.85%. It is a direct plan."
    url = "https://groww.in/test"
    date = "2024-01-01"
    
    res = validate_response(raw, url, date)
    
    assert res["answer"] == raw
    assert res["citation"] == url
    assert date in res["footer"]

def test_validate_response_truncates_at_3_sentences():
    raw = "Sentence one. Sentence two! Sentence three? Sentence four."
    url = "https://groww.in/test"
    date = "2024-01-01"
    
    res = validate_response(raw, url, date)
    
    assert "Sentence one." in res["answer"]
    assert "Sentence two!" in res["answer"]
    assert "Sentence three?" in res["answer"]
    assert "Sentence four." not in res["answer"]

def test_validate_response_advisory_override():
    # LLM hallucinates advice
    raw = "The expense ratio is low. I recommend you should buy this fund."
    url = "https://groww.in/test"
    date = "2024-01-01"
    
    res = validate_response(raw, url, date)
    
    # Should be entirely overridden by refusal handler
    assert "I recommend" not in res["answer"]
    assert "facts-only" in res["answer"]
    assert "amfiindia" in res["citation"]

def test_validate_response_scrubs_pii():
    # LLM accidentally outputs PII
    raw = "Contact the manager at 9876543210 for details."
    url = "https://groww.in/test"
    date = "2024-01-01"
    
    res = validate_response(raw, url, date)
    
    assert "9876543210" not in res["answer"]
    assert "[REDACTED]" in res["answer"]

def test_validate_response_removes_url_from_body():
    # LLM follows prompt and appends URL, we should remove it from the body to keep the answer clean
    url = "https://groww.in/test"
    raw = f"The exit load is 1%. Source: {url}"
    date = "2024-01-01"
    
    res = validate_response(raw, url, date)
    
    assert url not in res["answer"]
    assert "The exit load is 1%." in res["answer"]
    assert res["citation"] == url
