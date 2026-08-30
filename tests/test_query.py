"""
tests/test_query.py — Phase 2 Unit Tests

Tests for PII Scrubber, Intent Classifier, and Refusal Handler.
"""

from src.validation.pii_scrubber import scrub_pii
from src.query.intent_classifier import classify_intent
from src.query.refusal_handler import get_refusal_response

# ─── PII Scrubber Tests ───────────────────────────────────────────────────────

def test_scrub_pan():
    query = "My PAN is ABCDE1234F, what is the expense ratio?"
    scrubbed = scrub_pii(query)
    assert "ABCDE1234F" not in scrubbed
    assert "[REDACTED]" in scrubbed

def test_scrub_aadhaar():
    query = "Here is my Aadhaar 1234 5678 9012 for verification."
    # The Aadhaar regex expects the first digit to be 2-9
    query2 = "Here is my Aadhaar 2345 6789 0123 for verification."
    scrubbed = scrub_pii(query2)
    assert "2345 6789 0123" not in scrubbed
    assert "[REDACTED]" in scrubbed

def test_scrub_phone():
    query = "Call me at +91 9876543210 if needed."
    scrubbed = scrub_pii(query)
    assert "+91 9876543210" not in scrubbed
    assert "[REDACTED]" in scrubbed

def test_scrub_email():
    query = "Email me the factsheet at user@example.com."
    scrubbed = scrub_pii(query)
    assert "user@example.com" not in scrubbed
    assert "[REDACTED]" in scrubbed

def test_scrub_otp():
    query = "My OTP is 456789. Also my PIN is 1234."
    scrubbed = scrub_pii(query)
    assert "456789" not in scrubbed
    assert "1234" not in scrubbed
    assert "[REDACTED]" in scrubbed

def test_scrub_no_pii():
    query = "What is the exit load for HDFC Mid Cap?"
    scrubbed = scrub_pii(query)
    assert scrubbed == query

# ─── Intent Classifier Tests ──────────────────────────────────────────────────

def test_intent_advisory():
    # Matches 'should i invest'
    assert classify_intent("Should I invest in HDFC Mid Cap?") == "ADVISORY"
    # Matches 'which fund is better'
    assert classify_intent("Which fund is better: HDFC Mid Cap or Small Cap?") == "ADVISORY"

def test_intent_factual():
    # Matches 'expense ratio'
    assert classify_intent("What is the expense ratio of this fund?") == "FACTUAL"
    # Matches 'fund manager'
    assert classify_intent("Who is the fund manager?") == "FACTUAL"

def test_intent_unknown():
    # Matches none
    assert classify_intent("Tell me a joke") == "UNKNOWN"
    assert classify_intent("Hello") == "UNKNOWN"

def test_intent_advisory_precedence():
    # Matches both 'should i invest' (advisory) and 'expense ratio' (factual)
    # Advisory should take precedence for safety.
    assert classify_intent("Should I invest in this if the expense ratio is high?") == "ADVISORY"

# ─── Refusal Handler Tests ────────────────────────────────────────────────────

def test_refusal_handler():
    response = get_refusal_response("Should I buy this fund?")
    assert "answer" in response
    assert "citation" in response
    assert "footer" in response
    assert "facts-only" in response["answer"].lower()
    assert "amfiindia.com" in response["citation"]
