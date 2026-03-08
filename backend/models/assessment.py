"""
Pydantic models for Assessment, Session and Risk data structures.
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from enum import Enum


class RiskLevel(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class RegionalLanguage(str, Enum):
    hindi = "hi-IN"
    english = "en-IN"
    kannada = "kn-IN"
    tamil = "ta-IN"
    telugu = "te-IN"
    bengali = "bn-IN"
    marathi = "mr-IN"
    malayalam = "ml-IN"


class StartSessionRequest(BaseModel):
    patient_id: str
    language: RegionalLanguage = RegionalLanguage.hindi
    assessment_type: str = "general"  # general | maternal


class SessionResponse(BaseModel):
    session_id: str
    patient_id: str
    asha_worker_id: str
    language: str
    message: str
    next_question: Optional[str]
    is_complete: bool = False
    emergency_detected: bool = False
    question_number: int = 0
    audio_response_url: Optional[str] = None


class TextInputRequest(BaseModel):
    session_id: str
    text_input: str
    language: RegionalLanguage = RegionalLanguage.hindi


class AudioInputRequest(BaseModel):
    session_id: str
    audio_base64: str              # Base64-encoded audio (WAV/MP3)
    source_language: RegionalLanguage = RegionalLanguage.hindi


class RiskFactor(BaseModel):
    factor: str
    severity: str  # low | medium | high
    description: str


class RiskAssessment(BaseModel):
    assessment_id: str
    patient_id: str
    session_id: str
    risk_level: RiskLevel
    risk_score: int = Field(..., ge=0, le=100)
    reasoning: List[str]
    recommendations: List[str]
    referral_required: bool
    guideline_references: List[str]
    emergency_detected: bool = False
    created_at: str


class MaternalRiskRequest(BaseModel):
    patient_id: str
    age: int
    gestational_age_weeks: int
    blood_pressure_systolic: int
    blood_pressure_diastolic: int
    hemoglobin_level: float
    weight_kg: Optional[float] = None
    previous_complications: List[str] = []
    current_symptoms: List[str] = []


class MaternalRiskResponse(BaseModel):
    patient_id: str
    overall_score: int
    risk_level: RiskLevel
    risk_factors: List[RiskFactor]
    recommendations: List[str]
    next_visit_days: int
    guideline_references: List[str]
    immediate_actions: List[str] = []


class EmergencyResponse(BaseModel):
    is_emergency: bool
    emergency_type: Optional[str] = None
    immediate_actions: List[str] = []
    nearest_facility_type: Optional[str] = None
    call_number: str = "108"
