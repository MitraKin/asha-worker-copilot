"""
Amazon Polly service — text-to-speech for regional Indian languages.
"""
import boto3
import base64
import logging
from typing import Optional

from config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# Voice mappings per language
VOICE_MAP = {
    "hi-IN": ("Aditi", "standard"),
    "en-IN": ("Raveena", "standard"),
    # For languages without dedicated Polly voices, use Hindi as fallback
    "ta-IN": ("Aditi", "standard"),
    "te-IN": ("Aditi", "standard"),
    "kn-IN": ("Aditi", "standard"),
    "ml-IN": ("Aditi", "standard"),
    "bn-IN": ("Aditi", "standard"),
    "mr-IN": ("Aditi", "standard"),
}


def _get_polly_client():
    return boto3.client(
        "polly",
        region_name=settings.aws_region,
        aws_access_key_id=settings.aws_access_key_id or None,
        aws_secret_access_key=settings.aws_secret_access_key or None,
        aws_session_token=settings.aws_session_token or None,
    )


def synthesize_speech(text: str, language_code: str = "hi-IN") -> Optional[str]:
    """
    Synthesize text to speech using Amazon Polly.
    Returns base64-encoded MP3 audio.
    """
    if not text.strip():
        return None

    client = _get_polly_client()
    voice_id, engine = VOICE_MAP.get(language_code, ("Aditi", "standard"))

    # Truncate to Polly limit (3000 chars per request)
    text_truncated = text[:2900] if len(text) > 2900 else text

    try:
        response = client.synthesize_speech(
            Text=text_truncated,
            OutputFormat="mp3",
            VoiceId=voice_id,
            Engine=engine,
            SampleRate="22050",
        )
        audio_bytes = response["AudioStream"].read()
        return base64.b64encode(audio_bytes).decode("utf-8")
    except Exception as e:
        logger.error(f"Polly synthesis error: {e}")
        return None
