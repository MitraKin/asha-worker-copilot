"""
Amazon Translate service — regional language to/from English translation.
"""
import boto3
import logging
from typing import Optional

from config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# Translate language codes (ISO 639-1 or locale)
TRANSCRIBE_TO_TRANSLATE_MAP = {
    "hi-IN": "hi",
    "en-IN": "en",
    "ta-IN": "ta",
    "te-IN": "te",
    "kn-IN": "kn",
    "ml-IN": "ml",
    "bn-IN": "bn",
    "mr-IN": "mr",
}


def _get_translate_client():
    return boto3.client(
        "translate",
        region_name=settings.aws_region,
        aws_access_key_id=settings.aws_access_key_id or None,
        aws_secret_access_key=settings.aws_secret_access_key or None,
        aws_session_token=settings.aws_session_token or None,
    )


def translate_to_english(text: str, source_language_code: str = "hi-IN") -> str:
    """Translate regional language text to English."""
    if source_language_code == "en-IN" or not text.strip():
        return text

    client = _get_translate_client()
    source_lang = TRANSCRIBE_TO_TRANSLATE_MAP.get(source_language_code, "hi")

    try:
        response = client.translate_text(
            Text=text,
            SourceLanguageCode=source_lang,
            TargetLanguageCode="en",
            Settings={"Formality": "INFORMAL"},
        )
        return response["TranslatedText"]
    except Exception as e:
        logger.error(f"Translate to English error: {e}")
        return text   # fallback: return original


def translate_from_english(text: str, target_language_code: str = "hi-IN") -> str:
    """Translate English text to target regional language."""
    if target_language_code == "en-IN" or not text.strip():
        return text

    client = _get_translate_client()
    target_lang = TRANSCRIBE_TO_TRANSLATE_MAP.get(target_language_code, "hi")

    try:
        response = client.translate_text(
            Text=text,
            SourceLanguageCode="en",
            TargetLanguageCode=target_lang,
        )
        return response["TranslatedText"]
    except Exception as e:
        logger.error(f"Translate from English error: {e}")
        return text   # fallback: return English
