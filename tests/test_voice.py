"""
Unit tests for Sorello voice agent.
Run with: pytest tests/ -v
"""

import pytest
from app.voice import handle_incoming_call, handle_transcription, is_spam


# --- Spam detection tests ---

def test_spam_empty_string():
    assert is_spam("") is True

def test_spam_whitespace():
    assert is_spam("   ") is True

def test_spam_only_numbers():
    assert is_spam("1234567890") is True

def test_spam_press_digit():
    assert is_spam("press 1 to continue") is True

def test_spam_recording_marker():
    assert is_spam("this is a recording") is True

def test_spam_real_order():
    assert is_spam("I'd like a large pepperoni pizza please") is False

def test_spam_short_but_valid():
    assert is_spam("Pizza") is False  # 5 chars — just passes threshold


# --- Transcription handling tests ---

@pytest.mark.asyncio
async def test_transcription_valid_order():
    result = await handle_transcription(
        transcription="I would like a large pepperoni pizza and two Cokes",
        call_sid="CA123456",
        caller="+447911123456",
    )
    assert result["order"] == "I would like a large pepperoni pizza and two Cokes"
    assert result["call_sid"] == "CA123456"


@pytest.mark.asyncio
async def test_transcription_empty():
    result = await handle_transcription(
        transcription="",
        call_sid="CA123456",
        caller="+447911123456",
    )
    assert result["order"] is None
    assert result["error"] == "empty_transcription"


@pytest.mark.asyncio
async def test_transcription_spam():
    result = await handle_transcription(
        transcription="press 1 for more options",
        call_sid="CA999",
        caller="+447911123456",
    )
    assert result["order"] is None
    assert result["error"] == "spam_detected"


# --- TwiML generation test ---

def test_handle_incoming_call_returns_twiml():
    twiml = handle_incoming_call()
    assert "<?xml" in twiml or "<Response>" in twiml
    assert "Record" in twiml
    assert "/voice/transcription" in twiml
