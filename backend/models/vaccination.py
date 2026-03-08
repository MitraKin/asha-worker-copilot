"""
Pydantic models for Vaccination entities.
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from enum import Enum


class PatientTypeVacc(str, Enum):
    child = "child"
    pregnant = "pregnant"


class ScheduledVaccination(BaseModel):
    vaccine_name: str
    due_date: str            # ISO 8601
    age_at_administration: str  # e.g., "6 weeks", "9 months"
    is_administered: bool = False
    administered_date: Optional[str] = None
    administered_by: Optional[str] = None


class VaccinationSchedule(BaseModel):
    patient_id: str
    patient_name: str
    schedule_type: PatientTypeVacc
    vaccinations: List[ScheduledVaccination]


class RecordVaccinationRequest(BaseModel):
    patient_id: str
    vaccine_name: str
    administered_date: str  # ISO 8601


class DueVaccination(BaseModel):
    patient_id: str
    patient_name: str
    vaccine_name: str
    due_date: str
    days_overdue: Optional[int] = None
    days_until_due: Optional[int] = None
    status: str  # "overdue" | "due_soon" | "due"


class VaccinationReminder(BaseModel):
    patient_id: str
    patient_name: str
    vaccine_name: str
    due_date: str
    days_until_due: int


class VaccinationSummary(BaseModel):
    patient_id: str
    total: int
    completed: int
    upcoming: int
    overdue: int
