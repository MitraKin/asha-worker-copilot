"""
Application configuration — loads from environment variables (or .env file).
All AWS service settings, table names, and model IDs are centralised here.
"""
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # ── App ──────────────────────────────────────────────────────────────
    app_name: str = "ASHA Worker Copilot"
    environment: str = "development"
    debug: bool = False
    secret_key: str = "change-me-in-production"  # Used for JWT signing (add Cognito in prod)

    # ── AWS ───────────────────────────────────────────────────────────────
    aws_region: str = "us-east-1"
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    aws_session_token: str = ""

    # ── Amazon Bedrock ────────────────────────────────────────────────────
    bedrock_model_id: str = "amazon.nova-pro-v1:0"
    bedrock_embedding_model_id: str = "amazon.titan-embed-text-v2:0"
    bedrock_api_key: str = ""                  # Optional Bedrock API key (alternative to IAM creds)
    bedrock_knowledge_base_id: str = ""        # Set after KB is created
    bedrock_data_source_id: str = ""           # Set after KB data source is created

    # ── Amazon Transcribe ─────────────────────────────────────────────────
    transcribe_language_codes: list[str] = ["hi-IN", "en-IN", "ta-IN", "te-IN", "kn-IN", "ml-IN", "bn-IN", "mr-IN"]
    transcribe_default_language: str = "hi-IN"

    # ── Amazon Polly ──────────────────────────────────────────────────────
    polly_voice_hi: str = "Aditi"       # Hindi female
    polly_voice_en: str = "Raveena"     # Indian English female
    polly_engine: str = "standard"

    # ── Amazon Cognito ────────────────────────────────────────────────────
    cognito_user_pool_id: str = ""
    cognito_client_id: str = ""
    cognito_region: str = "us-east-1"

    # ── DynamoDB Tables ───────────────────────────────────────────────────
    dynamo_patients_table: str = "asha-patients"
    dynamo_assessments_table: str = "asha-assessments"
    dynamo_vaccinations_table: str = "asha-vaccinations"
    dynamo_sessions_table: str = "asha-sessions"

    # ── S3 ────────────────────────────────────────────────────────────────
    s3_guidelines_bucket: str = "asha-copilot-guidelines"
    s3_audio_bucket: str = "asha-copilot-audio"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
