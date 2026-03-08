"""
Amazon Bedrock service — LLM for medical assessments and RAG retrieval.
"""
import json
import boto3
import logging
import os
from pathlib import Path
from typing import Optional, Dict, Any
from botocore.exceptions import ClientError

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

# Load medical guidelines from local JSON files (no OpenSearch needed for prototype)
GUIDELINES_DIR = Path(__file__).parent.parent / "knowledge_base" / "guidelines"
_GUIDELINES_CACHE = None


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


def _invoke_model(system_prompt: str, messages: list, max_tokens: int = 1024) -> str:
    """Call Amazon Nova Pro via Bedrock Converse API and return the response text."""
    client = _get_bedrock_client()

    try:
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
    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        if error_code in ("ThrottlingException", "TooManyRequestsException", "ServiceQuotaExceededException"):
            logger.warning(f"Bedrock throttled: {e}")
            raise BedrockThrottlingError(
                "Daily usage limit reached for AI service. Please try again later or contact your administrator."
            ) from e
        logger.error(f"Bedrock ClientError: {e}")
        raise


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

    # Parse JSON from Claude's response
    try:
        # Claude sometimes wraps JSON in ```json ... ```
        if "```json" in raw:
            raw = raw.split("```json")[1].split("```")[0].strip()
        elif "```" in raw:
            raw = raw.split("```")[1].split("```")[0].strip()
        return json.loads(raw)
    except json.JSONDecodeError:
        logger.error(f"Failed to parse Claude response as JSON: {raw[:500]}")
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

    try:
        if "```json" in raw:
            raw = raw.split("```json")[1].split("```")[0].strip()
        return json.loads(raw)
    except json.JSONDecodeError:
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

    try:
        if "```json" in raw:
            raw = raw.split("```json")[1].split("```")[0].strip()
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"is_emergency": False, "emergency_type": None, "immediate_actions": [], "facility_needed": "PHC"}
