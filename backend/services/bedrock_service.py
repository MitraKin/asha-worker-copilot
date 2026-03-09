"""
LLM service — Google Gemini (primary) + Amazon Bedrock (fallback).
"""
import json
import re
import boto3
import logging
from pathlib import Path
from typing import Dict, Any, Optional
from botocore.exceptions import ClientError
from google import genai

from config import get_settings
from prompts.assessment_prompt import (
    ASSESSMENT_SYSTEM_PROMPT,
    MATERNAL_RISK_SYSTEM_PROMPT,
    EMERGENCY_DETECTION_PROMPT,
)

logger = logging.getLogger(__name__)
settings = get_settings()


class BedrockThrottlingError(Exception):
    """Raised when Bedrock returns a throttling/quota error."""
    pass


class LLMServiceError(Exception):
    """Raised when all LLM providers fail."""
    pass


# Load medical guidelines from local JSON files (no OpenSearch needed for prototype)
GUIDELINES_DIR = Path(__file__).parent.parent / "knowledge_base" / "guidelines"
_GUIDELINES_CACHE = None
_gemini_client = None


def _load_local_guidelines() -> str:
    """Load all medical guidelines from local JSON files into a formatted string."""
    global _GUIDELINES_CACHE
    if _GUIDELINES_CACHE:
        return _GUIDELINES_CACHE
    
    guidelines_text = []
    try:
        for json_file in GUIDELINES_DIR.glob("*.json"):
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                guidelines_text.append(f"## {data.get('topic', json_file.stem)}")
                guidelines_text.append(f"Source: {data.get('source', 'ICMR')}\n")
                
                # Format guidelines/diseases
                items = data.get('guidelines', data.get('diseases', []))
                for item in items:
                    guidelines_text.append(f"### {item.get('name', item.get('condition', 'Unknown'))}")
                    for key, value in item.items():
                        if key not in ['id', 'name', 'condition']:
                            guidelines_text.append(f"- {key}: {value}")
                    guidelines_text.append("")
        
        _GUIDELINES_CACHE = "\n".join(guidelines_text)
        logger.info(f"Loaded {len(list(GUIDELINES_DIR.glob('*.json')))} guideline files from local storage")
        return _GUIDELINES_CACHE
    except Exception as e:
        logger.error(f"Error loading local guidelines: {e}")
        return "Medical guidelines not available. Use general medical knowledge."


def _parse_llm_json(raw: str) -> Optional[dict]:
    """Robustly extract JSON from LLM response, handling common quirks.

    Handles:
    - Direct JSON
    - Markdown code blocks (```json ... ``` or ``` ... ```)
    - Leading/trailing text around JSON
    - Broken unicode escapes (e.g. \\u093र produced by Gemini for Hindi)
    """
    attempts = []

    # Strip markdown code fences
    text = raw
    if "```json" in text:
        text = text.split("```json", 1)[1].split("```", 1)[0].strip()
    elif "```" in text:
        parts = text.split("```")
        if len(parts) >= 3:
            text = parts[1].strip()

    attempts.append(text)

    # Also try extracting the outermost { ... }
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        attempts.append(text[start : end + 1])

    # Try each candidate, then retry with broken-unicode fix
    for candidate in list(attempts):
        try:
            return json.loads(candidate)
        except (json.JSONDecodeError, ValueError):
            pass

        # Fix broken unicode escapes: \u093र → र  (non-hex char after partial escape)
        fixed = re.sub(r"\\u[0-9a-fA-F]{0,3}(?=[^\x00-\x7F])", "", candidate)
        try:
            return json.loads(fixed)
        except (json.JSONDecodeError, ValueError):
            pass

    return None


# ── Gemini client ───────────────────────────────────────────────────────────

def _get_gemini_client() -> genai.Client:
    global _gemini_client
    if _gemini_client is None:
        _gemini_client = genai.Client(api_key=settings.gemini_api_key)
    return _gemini_client


def _invoke_gemini(system_prompt: str, messages: list, max_tokens: int = 1024) -> str:
    """Call Google Gemini and return the response text.
    
    Converts Bedrock message format [{role, content: [{text}]}] to Gemini format.
    Gemini 2.5 Flash is a thinking model — thinking tokens count against
    max_output_tokens, so we need a higher budget than Bedrock.
    """
    client = _get_gemini_client()

    # Convert Bedrock-style messages to Gemini contents
    contents = []
    for msg in messages:
        role = "user" if msg["role"] == "user" else "model"
        text_parts = []
        for part in msg.get("content", []):
            if isinstance(part, dict) and "text" in part:
                text_parts.append(part["text"])
            elif isinstance(part, str):
                text_parts.append(part)
        contents.append({"role": role, "parts": [{"text": t} for t in text_parts]})

    # Gemini thinking model needs extra budget for reasoning tokens
    gemini_max_tokens = max(max_tokens * 4, 4096)

    response = client.models.generate_content(
        model=settings.gemini_model_id,
        contents=contents,
        config={
            "system_instruction": system_prompt,
            "max_output_tokens": gemini_max_tokens,
            "temperature": 0.3,
            "top_p": 0.9,
        },
    )
    if response.text is None:
        raise RuntimeError("Gemini returned empty response (thinking tokens may have exhausted budget)")
    return response.text


# ── Bedrock client ──────────────────────────────────────────────────────────

def _get_bedrock_client():
    return boto3.client(
        "bedrock-runtime",
        region_name=settings.aws_region,
        aws_access_key_id=settings.aws_access_key_id or None,
        aws_secret_access_key=settings.aws_secret_access_key or None,
        aws_session_token=settings.aws_session_token or None,
    )


def _get_bedrock_agent_client():
    return boto3.client(
        "bedrock-agent-runtime",
        region_name=settings.aws_region,
        aws_access_key_id=settings.aws_access_key_id or None,
        aws_secret_access_key=settings.aws_secret_access_key or None,
        aws_session_token=settings.aws_session_token or None,
    )


def _invoke_bedrock(system_prompt: str, messages: list, max_tokens: int = 1024) -> str:
    """Call Amazon Bedrock Converse API and return the response text."""
    client = _get_bedrock_client()

    response = client.converse(
        modelId=settings.bedrock_model_id,
        system=[{"text": system_prompt}],
        messages=messages,
        inferenceConfig={
            "maxTokens": max_tokens,
            "temperature": 0.3,
            "topP": 0.9,
        },
    )
    return response["output"]["message"]["content"][0]["text"]


# ── Unified model invocation with fallback ──────────────────────────────────

def _invoke_model(system_prompt: str, messages: list, max_tokens: int = 1024) -> str:
    """Invoke the configured LLM provider with automatic fallback."""
    primary = settings.llm_provider.lower()

    if primary == "gemini":
        providers = [
            ("gemini", _invoke_gemini),
            ("bedrock", _invoke_bedrock),
        ]
    else:
        providers = [
            ("bedrock", _invoke_bedrock),
            ("gemini", _invoke_gemini),
        ]

    last_error = None
    for name, invoke_fn in providers:
        try:
            result = invoke_fn(system_prompt, messages, max_tokens)
            logger.info(f"LLM response from {name}")
            return result
        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            if error_code in ("ThrottlingException", "TooManyRequestsException", "ServiceQuotaExceededException"):
                logger.warning(f"{name} throttled: {e}")
                last_error = e
                continue
            logger.error(f"{name} ClientError: {e}")
            last_error = e
            continue
        except Exception as e:
            logger.warning(f"{name} failed: {e}")
            last_error = e
            continue

    # All providers failed
    raise LLMServiceError(
        "All AI providers are currently unavailable. Please try again later."
    ) from last_error


def retrieve_guidelines_from_rag(query: str, num_results: int = 5) -> str:
    """
    Retrieve relevant medical guidelines.
    For prototype: loads from local JSON files (no OpenSearch Serverless needed).
    For production: can be upgraded to use Bedrock Knowledge Base with vector search.
    """
    # PROTOTYPE MODE: Use local guidelines (saves ~$50-70/month)
    if not settings.bedrock_knowledge_base_id:
        logger.info("Using local guidelines (no Knowledge Base configured)")
        return _load_local_guidelines()
    
    # PRODUCTION MODE: Use Bedrock Knowledge Base with OpenSearch
    client = _get_bedrock_agent_client()
    try:
        response = client.retrieve(
            knowledgeBaseId=settings.bedrock_knowledge_base_id,
            retrievalQuery={"text": query},
            retrievalConfiguration={
                "vectorSearchConfiguration": {"numberOfResults": num_results}
            },
        )
        results = response.get("retrievalResults", [])
        if not results:
            logger.warning("No results from Knowledge Base, falling back to local guidelines")
            return _load_local_guidelines()

        formatted = []
        for r in results:
            content = r.get("content", {}).get("text", "")
            location = r.get("location", {}).get("s3Location", {}).get("uri", "")
            score = r.get("score", 0)
            if content:
                formatted.append(
                    f"[Source: {location} | Relevance: {score:.2f}]\n{content}"
                )
        return "\n\n---\n\n".join(formatted)

    except Exception as e:
        logger.error(f"RAG retrieval error: {e}, falling back to local guidelines")
        return _load_local_guidelines()


def process_assessment_turn(
    conversation_history: list,
    user_message: str,
    patient_context: Dict[str, Any],
    language: str = "hi-IN",
) -> Dict[str, Any]:
    """
    Process one turn of the medical assessment conversation.
    Returns parsed JSON response from Claude.
    """
    # Retrieve relevant guidelines based on the current message
    rag_context = retrieve_guidelines_from_rag(user_message)

    # Build context-aware system prompt
    context_block = f"""
## Current Patient Context
- Patient: {patient_context.get('name', 'Unknown')}, Age: {patient_context.get('age', 'Unknown')}
- Gender: {patient_context.get('gender', 'Unknown')}
- Type: {patient_context.get('patient_type', 'general')}
- Chronic conditions: {', '.join(patient_context.get('chronic_conditions', [])) or 'None'}
- Response language: {language} (use this language for all messages and questions)

## Retrieved Medical Guidelines
{rag_context if rag_context else 'No specific guidelines retrieved for this query.'}
"""
    full_system_prompt = ASSESSMENT_SYSTEM_PROMPT + context_block

    # Append new user message
    messages = conversation_history + [{"role": "user", "content": [{"text": user_message}]}]

    raw = _invoke_model(full_system_prompt, messages, max_tokens=1024)

    parsed = _parse_llm_json(raw)
    if parsed is not None:
        return parsed

    logger.error(f"Failed to parse LLM response as JSON: {raw[:500]}")
    return {
        "message": raw,
        "next_question": None,
        "is_complete": False,
        "emergency_detected": False,
        "question_number": len(conversation_history) + 1,
    }


def assess_maternal_risk(maternal_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate maternal health risk assessment using Bedrock Claude.
    """
    rag_context = retrieve_guidelines_from_rag(
        f"maternal health risk assessment blood pressure {maternal_data.get('blood_pressure_systolic')}/{maternal_data.get('blood_pressure_diastolic')} hemoglobin {maternal_data.get('hemoglobin_level')} gestational age {maternal_data.get('gestational_age_weeks')} weeks"
    )

    user_message = f"""
Please assess the maternal health risk for this patient:
- Age: {maternal_data.get('age')} years
- Gestational Age: {maternal_data.get('gestational_age_weeks')} weeks
- Blood Pressure: {maternal_data.get('blood_pressure_systolic')}/{maternal_data.get('blood_pressure_diastolic')} mmHg
- Hemoglobin: {maternal_data.get('hemoglobin_level')} g/dL
- Weight: {maternal_data.get('weight_kg', 'Not recorded')} kg
- Previous Complications: {', '.join(maternal_data.get('previous_complications', [])) or 'None'}
- Current Symptoms: {', '.join(maternal_data.get('current_symptoms', [])) or 'None'}

Relevant Guidelines:
{rag_context or 'Use standard ICMR maternal health guidelines.'}
"""

    messages = [{"role": "user", "content": [{"text": user_message}]}]
    raw = _invoke_model(MATERNAL_RISK_SYSTEM_PROMPT, messages, max_tokens=1024)

    parsed = _parse_llm_json(raw)
    if parsed is not None:
        return parsed

    logger.error(f"Maternal risk parse error: {raw[:500]}")
    return {
            "overall_score": 50,
            "risk_level": "medium",
            "risk_factors": [],
            "recommendations": ["Please consult a doctor for detailed assessment"],
            "next_visit_days": 7,
            "guideline_references": [],
            "immediate_actions": [],
        }


def detect_emergency(symptoms_text: str) -> Dict[str, Any]:
    """
    Fast emergency detection — called before full assessment.
    """
    messages = [{"role": "user", "content": [{"text": f"Patient symptoms: {symptoms_text}"}]}]
    raw = _invoke_model(EMERGENCY_DETECTION_PROMPT, messages, max_tokens=512)

    parsed = _parse_llm_json(raw)
    if parsed is not None:
        return parsed

    return {"is_emergency": False, "emergency_type": None, "immediate_actions": [], "facility_needed": "PHC"}
