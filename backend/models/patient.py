"""
Pydantic models for Patient and related data structures.
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum


class Gender(str, Enum):
    male = "male"
    female = "female"
    other = "other"


class PatientType(str, Enum):
    general = "general"
    pregnant = "pregnant"
    child = "child"


class CreatePatientRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    age: int = Field(..., ge=0, le=120)
    gender: Gender
    date_of_birth: str  # ISO 8601
    village: str
    contact_number: Optional[str] = None
    chronic_conditions: List[str] = []
    allergies: List[str] = []
    patient_type: PatientType = PatientType.general
    # Maternal specific
    gestational_age_weeks: Optional[int] = Field(None, ge=1, le=42)
    last_menstrual_period: Optional[str] = None


class Patient(BaseModel):
    patient_id: str
    name: str
    age: int
    gender: Gender
    date_of_birth: str
    village: str
    asha_worker_id: str
    contact_number: Optional[str] = None
    chronic_conditions: List[str] = []
    allergies: List[str] = []
    patient_type: PatientType = PatientType.general
    gestational_age_weeks: Optional[int] = None
    last_menstrual_period: Optional[str] = None
    created_at: str
    updated_at: str


class PatientSummary(BaseModel):
    patient_id: str
    name: str
    age: int
    gender: Gender
    village: str
    patient_type: PatientType
    last_visit: Optional[str] = None
    last_risk_level: Optional[str] = None


class UpdatePatientRequest(BaseModel):
    name: Optional[str] = None
    age: Optional[int] = None
    contact_number: Optional[str] = None
    chronic_conditions: Optional[List[str]] = None
    allergies: Optional[List[str]] = None
    gestational_age_weeks: Optional[int] = None
    last_menstrual_period: Optional[str] = None
