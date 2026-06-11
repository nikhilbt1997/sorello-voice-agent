"""
Voice handling module.
Generates TwiML responses for Twilio and parses order transcriptions.
"""

import re
from twilio.twiml.voice_response import VoiceResponse, Gather


# --- Restaurant config (loaded from env in production) ---
RESTAURANT_NAME = "Bella Italia"
GREETING = (
    f"Hello, thank you for calling {RESTAURANT_NAME}. "
    "I am your AI ordering assistant. "
    "Please tell me your order after the beep, and I will send it straight to our kitchen."
)
CONFIRM_MSG = (
    "Thank you! Your order has been received and sent to our team. "
    "You will receive a confirmation message shortly. Goodbye!"
)
FALLBACK_MSG = (
    "I am sorry, I did not catch that. Please call back and speak clearly after the beep. Goodbye!"
)

# Single consistent voice across all interactions — Twilio Polly Amy (UK English)
VOICE = "Polly.Amy"


def handle_incoming_call() -> str:
    """
    Returns TwiML to greet the caller and record their order.
    Uses Twilio's built-in transcription to keep the stack minimal.
    """
    response = VoiceResponse()

    # Greet with consistent brand voice
    response.say(GREETING, voice=VOICE)

    # Record the order with transcription enabled
    # transcriptionCallback fires once Twilio finishes transcribing
    response.record(
        action="/voice/transcription",
        transcribe=True,
        transcribeCallback="/voice/transcription",
        max_length=60,       # max 60 seconds per order
        timeout=5,           # stop recording after 5s silence
        play_beep=True,
        finish_on_key="#",   # caller can press # to finish early
    )

    # Fallback if no recording received
    response.say(FALLBACK_MSG, voice=VOICE)

    return str(response)


async def handle_transcription(
    transcription: str,
    call_sid: str,
    caller: str,
) -> dict:
    """
    Parses the transcription and extracts the order.
    Returns a dict with the cleaned order text.
    """
    if not transcription or len(transcription.strip()) < 3:
        return {"order": None, "error": "empty_transcription"}

    # Clean up transcription
    order = transcription.strip()

    # Basic spam / junk call detection
    if is_spam(order):
        return {"order": None, "error": "spam_detected"}

    return {
        "order": order,
        "call_sid": call_sid,
        "caller": caller,
    }


def is_spam(text: str) -> bool:
    """
    Lightweight rule-based spam detection.
    Filters out robocalls, silence, and non-order content.
    """
    text_lower = text.lower().strip()

    # Too short to be a real order
    if len(text_lower) < 5:
        return True

    # Common robocall / non-order patterns
    spam_patterns = [
        r"^\s*$",               # empty / whitespace
        r"^[0-9\s\-\+]+$",     # only numbers (robocall DTMF)
        r"press \d",            # robocall instruction
        r"this is a recording", # robocall marker
    ]

    for pattern in spam_patterns:
        if re.search(pattern, text_lower):
            return True

    return False
