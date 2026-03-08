"""
Amazon Transcribe service — speech-to-text for Indian regional languages.
"""
import boto3
import base64
import time
import uuid
import logging
from typing import Optional
import json

from config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# Language code mappings for Transcribe
LANGUAGE_MAP = {
    "hi-IN": "hi-IN",
    "en-IN": "en-IN",
    "ta-IN": "ta-IN",
    "te-IN": "te-IN",
    "kn-IN": "kn-IN",
    "ml-IN": "ml-IN",
    "bn-IN": "bn-IN",
    "mr-IN": "mr-IN",
}


def _get_transcribe_client():
    return boto3.client(
        "transcribe",
        region_name=settings.aws_region,
        aws_access_key_id=settings.aws_access_key_id or None,
        aws_secret_access_key=settings.aws_secret_access_key or None,
        aws_session_token=settings.aws_session_token or None,
    )


def _get_s3_client():
    return boto3.client(
        "s3",
        region_name=settings.aws_region,
        aws_access_key_id=settings.aws_access_key_id or None,
        aws_secret_access_key=settings.aws_secret_access_key or None,
        aws_session_token=settings.aws_session_token or None,
    )


def transcribe_audio(audio_base64: str, language_code: str = "hi-IN") -> Optional[str]:
    """
    Transcribe base64-encoded audio to text using Amazon Transcribe.
    Audio is temporarily uploaded to S3 for Transcribe to process.

    Returns the transcribed text or None on failure.
    """
    s3 = _get_s3_client()
    transcribe = _get_transcribe_client()

    # Decode audio
    audio_bytes = base64.b64decode(audio_base64)
    job_name = f"asha-{uuid.uuid4().hex[:12]}"
    s3_key = f"audio-temp/{job_name}.wav"

    # Upload to S3
    try:
        s3.put_object(
            Bucket=settings.s3_audio_bucket,
            Key=s3_key,
            Body=audio_bytes,
            ContentType="audio/wav",
        )
    except Exception as e:
        logger.error(f"S3 upload for Transcribe failed: {e}")
        return None

    s3_uri = f"s3://{settings.s3_audio_bucket}/{s3_key}"
    lang = LANGUAGE_MAP.get(language_code, "hi-IN")

    # Start transcription job
    try:
        transcribe.start_transcription_job(
            TranscriptionJobName=job_name,
            Media={"MediaFileUri": s3_uri},
            MediaFormat="wav",
            LanguageCode=lang,
            Settings={
                "ShowSpeakerLabels": False,
                "ChannelIdentification": False,
            },
            OutputBucketName=settings.s3_audio_bucket,
            OutputKey=f"transcripts/{job_name}.json",
        )
    except Exception as e:
        logger.error(f"Transcribe job start failed: {e}")
        return None

    # Poll for completion (max 30s for prototype)
    for _ in range(30):
        time.sleep(1)
        try:
            resp = transcribe.get_transcription_job(TranscriptionJobName=job_name)
            status = resp["TranscriptionJob"]["TranscriptionJobStatus"]
            if status == "COMPLETED":
                break
            elif status == "FAILED":
                logger.error("Transcribe job FAILED")
                return None
        except Exception as e:
            logger.error(f"Polling error: {e}")
            return None

    # Read transcript from S3
    try:
        obj = s3.get_object(Bucket=settings.s3_audio_bucket, Key=f"transcripts/{job_name}.json")
        transcript_data = json.loads(obj["Body"].read())
        transcript_text = transcript_data["results"]["transcripts"][0]["transcript"]
        return transcript_text
    except Exception as e:
        logger.error(f"Transcript read error: {e}")
        return None
    finally:
        # Cleanup temp audio from S3
        try:
            s3.delete_object(Bucket=settings.s3_audio_bucket, Key=s3_key)
        except Exception:
            pass
