"""
tests/test_generation.py — Phase 4 Unit Tests

Tests for Prompt Builder and Groq LLM Client.
"""

from unittest.mock import patch, MagicMock
from src.generation.prompt_builder import build_system_prompt, build_user_message
from src.generation.groq_client import call_groq

# ─── Prompt Builder Tests ──────────────────────────────────────────────────────

def test_build_system_prompt():
    prompt = build_system_prompt()
    assert "facts-only mutual fund information assistant" in prompt
    assert "maximum of 3 sentences" in prompt
    assert "Do not provide investment advice" in prompt

def test_build_user_message():
    context = "HDFC Mid Cap has an expense ratio of 0.85%."
    question = "What is the expense ratio?"
    
    message = build_user_message(context, question)
    
    assert "Context:" in message
    assert "HDFC Mid Cap has an expense ratio of 0.85%." in message
    assert "Question: What is the expense ratio?" in message

def test_build_user_message_empty_context():
    message = build_user_message("", "What is the expense ratio?")
    assert "No relevant context found." in message

# ─── Groq Client Tests ────────────────────────────────────────────────────────

@patch("src.generation.groq_client._get_client")
def test_call_groq_primary_success(mock_get_client):
    # Setup mock
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "The expense ratio is 0.85%."
    mock_client.chat.completions.create.return_value = mock_response
    mock_get_client.return_value = mock_client
    
    # Execute
    result = call_groq("System Rules", "Context Text", "Question Text")
    
    # Assert
    assert result == "The expense ratio is 0.85%."
    # Verify primary model was used
    mock_client.chat.completions.create.assert_called_once()
    args, kwargs = mock_client.chat.completions.create.call_args
    assert "qwen" in kwargs["model"].lower()

@patch("src.generation.groq_client._get_client")
def test_call_groq_fallback_success(mock_get_client):
    # Setup mock to fail on first call, succeed on second
    mock_client = MagicMock()
    
    mock_success_response = MagicMock()
    mock_success_response.choices = [MagicMock()]
    mock_success_response.choices[0].message.content = "Fallback answered."
    
    # First call raises Exception, second call returns mock_success_response
    mock_client.chat.completions.create.side_effect = [Exception("API Error"), mock_success_response]
    mock_get_client.return_value = mock_client
    
    # Execute
    result = call_groq("System Rules", "Context Text", "Question Text")
    
    # Assert
    assert result == "Fallback answered."
    assert mock_client.chat.completions.create.call_count == 2
    args, kwargs = mock_client.chat.completions.create.call_args
    assert "gpt-oss" in kwargs["model"].lower()

@patch("src.generation.groq_client._get_client")
def test_call_groq_total_failure(mock_get_client):
    # Setup mock to fail on both calls
    mock_client = MagicMock()
    mock_client.chat.completions.create.side_effect = Exception("API Error")
    mock_get_client.return_value = mock_client
    
    # Execute
    result = call_groq("System Rules", "Context Text", "Question Text")
    
    # Assert
    assert "technical difficulties" in result
