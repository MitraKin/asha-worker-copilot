"""
Assessment router — /api/assessment/*
Voice + text-based health assessment with Bedrock AI and RAG.
"""
import uuid
import json
import logging
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Depends
from typing import Optional

from models.assessment import (
    StartSessionRequest, SessionResponse, TextInputRequest,
    AudioInputRequest, MaternalRiskRequest, MaternalRiskResponse,
)
from services import bedrock_service, dynamo_service, transcribe_service, translate_service, polly_service
from routers.auth import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/assessment", tags=["assessment"])

EMERGENCY_KEYWORDS = [
    "bleeding", "khoon", "behoshi", "unconscious", "seizure", "fit", "dauraa",
    "sans", "breathing", "chest pain", "severe", "emergency", "critical"
]


def _emergency_keyword_check(text: str) -> bool:
    """Fast local emergency keyword check before calling Bedrock."""
    lower = text.lower()
    return any(kw in lower for kw in EMERGENCY_KEYWORDS)


@router.post("/start", response_model=SessionResponse)
def start_session(req: StartSessionRequest, current_user: dict = Depends(get_current_user)):
    """Start a new assessment session for a patient."""
    patient = dynamo_service.get_patient(req.patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    if patient.get("asha_worker_id") != current_user["username"]:
        raise HTTPException(status_code=403, detail="Access denied")

    session_id = f"S{uuid.uuid4().hex[:14].upper()}"
    now = datetime.now(timezone.utc).isoformat()

    # Initial greeting in target language
    greeting_en = (
        f"Hello! I am your ASHA Copilot. I am here to help you assess {patient['name']}'s health. "
        f"Please tell me: what symptoms is {patient['name']} experiencing today?"
    )
    greeting = translate_service.translate_from_english(greeting_en, req.language)
    audio = polly_service.synthesize_speech(greeting, req.language)

    session_item = {
        "session_id": session_id,
        "patient_id": req.patient_id,
        "asha_worker_id": current_user["username"],
        "language": req.language,
        "assessment_type": req.assessment_type,
        "conversation_history": json.dumps([]),
        "collected_symptoms": json.dumps([]),
        "question_count": 0,
        "is_complete": False,
        "created_at": now,
        "last_activity": now,
    }
    dynamo_service.put_session(session_item)

    return SessionResponse(
        session_id=session_id,
        patient_id=req.patient_id,
        asha_worker_id=current_user["username"],
        language=req.language,
        message=greeting,
        next_question=None,
        is_complete=False,
        emergency_detected=False,
        question_number=0,
        audio_response_url=audio,
    )


@router.post("/text", response_model=SessionResponse)
def process_text_input(req: TextInputRequest, current_user: dict = Depends(get_current_user)):
    """Process a text input turn in the assessment conversation."""
    session = dynamo_service.get_session(req.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.get("asha_worker_id") != current_user["username"]:
        raise HTTPException(status_code=403, detail="Access denied")
    if session.get("is_complete"):
        raise HTTPException(status_code=400, detail="Assessment already completed")

    patient = dynamo_service.get_patient(session["patient_id"])
    language = session.get("language", "hi-IN")
    question_count = session.get("question_count", 0)

    # Fast emergency keyword check
    if _emergency_keyword_check(req.text_input):
        emergency_info = bedrock_service.detect_emergency(req.text_input)
        if emergency_info.get("is_emergency"):
            return _handle_emergency(session, emergency_info, language, current_user)

    # Max questions guard
    if question_count >= 10:
        return _finalize_assessment(session, patient, language, current_user)

    # Translate input to English for LLM processing
    english_input = translate_service.translate_to_english(req.text_input, language)

    # Load conversation history
    history = json.loads(session.get("conversation_history", "[]"))

    # Call Bedrock
    ai_resp = bedrock_service.process_assessment_turn(
        conversation_history=history,
        user_message=english_input,
        patient_context=patient,
        language=language,
    )

    # Update conversation history
    history.append({"role": "user", "content": [{"text": english_input}]})
    history.append({"role": "assistant", "content": [{"text": json.dumps(ai_resp)}]})

    is_complete = ai_resp.get("is_complete", False) or (question_count + 1) >= 10
    emergency_detected = ai_resp.get("emergency_detected", False)

    # Build response message
    response_message = ai_resp.get("message", "")
    if ai_resp.get("next_question") and not is_complete:
        response_message = ai_resp["next_question"]

    # Synthesize voice response
    audio = polly_service.synthesize_speech(response_message, language)

    # Save session state
    dynamo_service.update_session(session["session_id"], {
        "conversation_history": json.dumps(history[-20:]),  # keep last 20 turns
        "question_count": question_count + 1,
        "is_complete": is_complete,
        "last_activity": datetime.now(timezone.utc).isoformat(),
    })

    # If complete, save assessment
    if is_complete and not emergency_detected:
        _save_assessment(ai_resp, session, patient, current_user)

    return SessionResponse(
        session_id=session["session_id"],
        patient_id=session["patient_id"],
        asha_worker_id=current_user["username"],
        language=language,
        message=response_message,
        next_question=ai_resp.get("next_question") if not is_complete else None,
        is_complete=is_complete,
        emergency_detected=emergency_detected,
        question_number=question_count + 1,
        audio_response_url=audio,
    )


@router.post("/audio", response_model=SessionResponse)
def process_audio_input(req: AudioInputRequest, current_user: dict = Depends(get_current_user)):
    """Process voice input — transcribe audio then run assessment turn."""
    session = dynamo_service.get_session(req.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Transcribe audio → text
    transcribed = transcribe_service.transcribe_audio(req.audio_base64, req.source_language)
    if not transcribed:
        raise HTTPException(status_code=422, detail="Could not transcribe audio. Please speak clearly and try again.")

    # Delegate to text handler
    text_req = TextInputRequest(
        session_id=req.session_id,
        text_input=transcribed,
        language=req.source_language,
    )
    return process_text_input(text_req, current_user)


@router.post("/maternal-risk", response_model=MaternalRiskResponse)
def assess_maternal_risk(
    req: MaternalRiskRequest, current_user: dict = Depends(get_current_user)
):
    """Standalone maternal health risk assessment using Bedrock."""
    patient = dynamo_service.get_patient(req.patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    if patient.get("asha_worker_id") != current_user["username"]:
        raise HTTPException(status_code=403, detail="Access denied")

    result = bedrock_service.assess_maternal_risk(req.model_dump())
    assessment_id = f"A{uuid.uuid4().hex[:12].upper()}"
    now = datetime.now(timezone.utc).isoformat()

    assessment_item = {
        "patient_id": req.patient_id,
        "assessment_id": assessment_id,
        "session_id": "MATERNAL_DIRECT",
        "assessment_type": "maternal",
        "risk_level": result.get("risk_level", "medium"),
        "risk_score": result.get("overall_score", 50),
        "reasoning": result.get("risk_factors", []),
        "recommendations": result.get("recommendations", []),
        "referral_required": result.get("risk_level") in ["high", "critical"],
        "guideline_references": result.get("guideline_references", []),
        "emergency_detected": False,
        "asha_worker_id": current_user["username"],
        "created_at": now,
    }
    dynamo_service.put_assessment(assessment_item)

    return {
        "patient_id": req.patient_id,
        "overall_score": result.get("overall_score", 50),
        "risk_level": result.get("risk_level", "medium"),
        "risk_factors": result.get("risk_factors", []),
        "recommendations": result.get("recommendations", []),
        "next_visit_days": result.get("next_visit_days", 7),
        "guideline_references": result.get("guideline_references", []),
        "immediate_actions": result.get("immediate_actions", []),
    }


@router.get("/session/{session_id}")
def get_session_status(session_id: str, current_user: dict = Depends(get_current_user)):
    """Get current session state."""
    session = dynamo_service.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.get("asha_worker_id") != current_user["username"]:
        raise HTTPException(status_code=403, detail="Access denied")
    return session


# ── Internal helpers ────────────────────────────────────────────────────────

def _handle_emergency(session: dict, emergency_info: dict, language: str, current_user: dict) -> SessionResponse:
    """Mark session as emergency and generate emergency response."""
    emergency_type = emergency_info.get("emergency_type", "EMERGENCY")
    actions = emergency_info.get("immediate_actions", ["Call 108 immediately"])

    msg_en = (
        f"⚠️ EMERGENCY DETECTED: {emergency_type}. "
        f"IMMEDIATE ACTIONS: {'. '.join(actions)}. "
        f"CALL 108 NOW."
    )
    msg = translate_service.translate_from_english(msg_en, language)
    audio = polly_service.synthesize_speech(msg, language)

    dynamo_service.update_session(session["session_id"], {
        "is_complete": True,
        "emergency_detected": True,
        "last_activity": datetime.now(timezone.utc).isoformat(),
    })

    # Log emergency assessment
    assessment_id = f"E{uuid.uuid4().hex[:12].upper()}"
    dynamo_service.put_assessment({
        "patient_id": session["patient_id"],
        "assessment_id": assessment_id,
        "session_id": session["session_id"],
        "assessment_type": "emergency",
        "risk_level": "critical",
        "risk_score": 100,
        "reasoning": [f"Emergency: {emergency_type}"],
        "recommendations": emergency_info.get("immediate_actions", []),
        "referral_required": True,
        "guideline_references": [],
        "emergency_detected": True,
        "asha_worker_id": current_user["username"],
        "created_at": datetime.now(timezone.utc).isoformat(),
    })

    return SessionResponse(
        session_id=session["session_id"],
        patient_id=session["patient_id"],
        asha_worker_id=current_user["username"],
        language=language,
        message=msg,
        next_question=None,
        is_complete=True,
        emergency_detected=True,
        question_number=session.get("question_count", 0),
        audio_response_url=audio,
    )


def _finalize_assessment(session: dict, patient: dict, language: str, current_user: dict) -> SessionResponse:
    """Force-complete an assessment when question limit is reached."""
    history = json.loads(session.get("conversation_history", "[]"))

    summary_prompt = "Based on the conversation so far, generate a complete risk assessment."
    ai_resp = bedrock_service.process_assessment_turn(
        conversation_history=history,
        user_message=summary_prompt,
        patient_context=patient,
        language=language,
    )
    ai_resp["is_complete"] = True
    _save_assessment(ai_resp, session, patient, current_user)

    msg = ai_resp.get("message", "Assessment complete.")
    audio = polly_service.synthesize_speech(msg, language)

    return SessionResponse(
        session_id=session["session_id"],
        patient_id=session["patient_id"],
        asha_worker_id=current_user["username"],
        language=language,
        message=msg,
        next_question=None,
        is_complete=True,
        emergency_detected=False,
        question_number=10,
        audio_response_url=audio,
    )


def _save_assessment(ai_resp: dict, session: dict, patient: dict, current_user: dict) -> None:
    """Persist completed assessment to DynamoDB."""
    assessment_id = f"A{uuid.uuid4().hex[:12].upper()}"
    dynamo_service.put_assessment({
        "patient_id": session["patient_id"],
        "assessment_id": assessment_id,
        "session_id": session["session_id"],
        "assessment_type": session.get("assessment_type", "general"),
        "risk_level": ai_resp.get("risk_level", "medium"),
        "risk_score": ai_resp.get("risk_score", 50),
        "reasoning": ai_resp.get("reasoning", []),
        "recommendations": ai_resp.get("recommendations", []),
        "referral_required": ai_resp.get("referral_required", False),
        "guideline_references": ai_resp.get("guideline_references", []),
        "emergency_detected": ai_resp.get("emergency_detected", False),
        "asha_worker_id": current_user["username"],
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
