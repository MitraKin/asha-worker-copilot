"""
Vaccination router — /api/vaccination/*
Schedule generation, recording, and reminders.
"""
import uuid
import logging
from datetime import datetime, timezone, date, timedelta
from fastapi import APIRouter, HTTPException, Depends
from typing import List

from models.vaccination import (
    VaccinationSchedule, RecordVaccinationRequest,
    DueVaccination, VaccinationReminder, VaccinationSummary,
)
from services import dynamo_service
from routers.auth import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/vaccination", tags=["vaccination"])

# ── Government of India Universal Immunization Programme (UIP) schedule ────

CHILD_SCHEDULE = [
    {"vaccine_name": "BCG",              "age_at_administration": "At birth",    "days_from_birth": 0},
    {"vaccine_name": "OPV-0",            "age_at_administration": "At birth",    "days_from_birth": 0},
    {"vaccine_name": "Hepatitis-B (Birth)","age_at_administration": "At birth",  "days_from_birth": 0},
    {"vaccine_name": "Pentavalent-1",    "age_at_administration": "6 weeks",     "days_from_birth": 42},
    {"vaccine_name": "OPV-1",            "age_at_administration": "6 weeks",     "days_from_birth": 42},
    {"vaccine_name": "Rotavirus-1",      "age_at_administration": "6 weeks",     "days_from_birth": 42},
    {"vaccine_name": "PCV-1",            "age_at_administration": "6 weeks",     "days_from_birth": 42},
    {"vaccine_name": "Pentavalent-2",    "age_at_administration": "10 weeks",    "days_from_birth": 70},
    {"vaccine_name": "OPV-2",            "age_at_administration": "10 weeks",    "days_from_birth": 70},
    {"vaccine_name": "Rotavirus-2",      "age_at_administration": "10 weeks",    "days_from_birth": 70},
    {"vaccine_name": "Pentavalent-3",    "age_at_administration": "14 weeks",    "days_from_birth": 98},
    {"vaccine_name": "OPV-3",            "age_at_administration": "14 weeks",    "days_from_birth": 98},
    {"vaccine_name": "Rotavirus-3",      "age_at_administration": "14 weeks",    "days_from_birth": 98},
    {"vaccine_name": "PCV-2",            "age_at_administration": "14 weeks",    "days_from_birth": 98},
    {"vaccine_name": "Measles-MR-1",     "age_at_administration": "9 months",    "days_from_birth": 270},
    {"vaccine_name": "Vitamin-A (1st)",  "age_at_administration": "9 months",    "days_from_birth": 270},
    {"vaccine_name": "PCV-Booster",      "age_at_administration": "9 months",    "days_from_birth": 270},
    {"vaccine_name": "DTP-Booster-1",    "age_at_administration": "16-24 months","days_from_birth": 548},
    {"vaccine_name": "OPV-Booster",      "age_at_administration": "16-24 months","days_from_birth": 548},
    {"vaccine_name": "Measles-MR-2",     "age_at_administration": "16-24 months","days_from_birth": 548},
    {"vaccine_name": "Vitamin-A (2nd)",  "age_at_administration": "16 months",   "days_from_birth": 487},
]

MATERNAL_SCHEDULE = [
    {"vaccine_name": "TT-1", "age_at_administration": "Early pregnancy",         "days_from_lmp": 84},
    {"vaccine_name": "TT-2", "age_at_administration": "4 weeks after TT-1",      "days_from_lmp": 112},
    {"vaccine_name": "IFA",  "age_at_administration": "Starting from 14th week", "days_from_lmp": 98},
]


def _date_from_str(date_str: str) -> date:
    return datetime.fromisoformat(date_str.replace("Z", "+00:00")).date()


@router.post("/{patient_id}/generate-schedule", response_model=VaccinationSchedule)
def generate_schedule(patient_id: str, current_user: dict = Depends(get_current_user)):
    """Generate vaccination schedule based on patient DOB and type."""
    patient = dynamo_service.get_patient(patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    if patient.get("asha_worker_id") != current_user["username"]:
        raise HTTPException(status_code=403, detail="Access denied")

    patient_type = patient.get("patient_type", "general")
    asha_worker_id = current_user["username"]
    now = datetime.now(timezone.utc).isoformat()

    if patient_type == "child":
        dob = _date_from_str(patient.get("date_of_birth", datetime.now().isoformat()))
        vaccinations = []
        for v in CHILD_SCHEDULE:
            due_date = (dob + timedelta(days=v["days_from_birth"])).isoformat()
            item = {
                "patient_id": patient_id,
                "vaccine_name": v["vaccine_name"],
                "age_at_administration": v["age_at_administration"],
                "due_date": due_date,
                "is_administered": False,
                "administered_date": None,
                "administered_by": None,
                "asha_worker_id": asha_worker_id,
                "created_at": now,
            }
            dynamo_service.put_vaccination(item)
            vaccinations.append({
                "vaccine_name": v["vaccine_name"],
                "due_date": due_date,
                "age_at_administration": v["age_at_administration"],
                "is_administered": False,
            })
        return VaccinationSchedule(
            patient_id=patient_id,
            patient_name=patient["name"],
            schedule_type="child",
            vaccinations=vaccinations,
        )

    elif patient_type == "pregnant":
        lmp_str = patient.get("last_menstrual_period", datetime.now().isoformat())
        lmp = _date_from_str(lmp_str)
        vaccinations = []
        for v in MATERNAL_SCHEDULE:
            due_date = (lmp + timedelta(days=v["days_from_lmp"])).isoformat()
            item = {
                "patient_id": patient_id,
                "vaccine_name": v["vaccine_name"],
                "age_at_administration": v["age_at_administration"],
                "due_date": due_date,
                "is_administered": False,
                "administered_date": None,
                "administered_by": None,
                "asha_worker_id": asha_worker_id,
                "created_at": now,
            }
            dynamo_service.put_vaccination(item)
            vaccinations.append({
                "vaccine_name": v["vaccine_name"],
                "due_date": due_date,
                "age_at_administration": v["age_at_administration"],
                "is_administered": False,
            })
        return VaccinationSchedule(
            patient_id=patient_id,
            patient_name=patient["name"],
            schedule_type="pregnant",
            vaccinations=vaccinations,
        )
    else:
        raise HTTPException(status_code=400, detail="Patient type must be 'child' or 'pregnant' to generate schedule")


@router.get("/{patient_id}/schedule", response_model=VaccinationSchedule)
def get_schedule(patient_id: str, current_user: dict = Depends(get_current_user)):
    """Get existing vaccination schedule for a patient."""
    patient = dynamo_service.get_patient(patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    if patient.get("asha_worker_id") != current_user["username"]:
        raise HTTPException(status_code=403, detail="Access denied")

    records = dynamo_service.get_vaccinations_for_patient(patient_id)
    vaccinations = [
        {
            "vaccine_name": r["vaccine_name"],
            "due_date": r.get("due_date", ""),
            "age_at_administration": r.get("age_at_administration", ""),
            "is_administered": r.get("is_administered", False),
            "administered_date": r.get("administered_date"),
        }
        for r in records
    ]
    return VaccinationSchedule(
        patient_id=patient_id,
        patient_name=patient["name"],
        schedule_type=patient.get("patient_type", "child"),
        vaccinations=vaccinations,
    )


@router.post("/{patient_id}/record")
def record_vaccination(
    patient_id: str,
    req: RecordVaccinationRequest,
    current_user: dict = Depends(get_current_user),
):
    """Record an administered vaccination."""
    patient = dynamo_service.get_patient(patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    if patient.get("asha_worker_id") != current_user["username"]:
        raise HTTPException(status_code=403, detail="Access denied")

    dynamo_service.update_vaccination_record(
        patient_id=patient_id,
        vaccine_name=req.vaccine_name,
        updates={
            "is_administered": True,
            "administered_date": req.administered_date,
            "administered_by": current_user["username"],
        },
    )
    return {"success": True, "message": f"{req.vaccine_name} recorded as administered on {req.administered_date}"}


@router.get("/reminders/due", response_model=List[DueVaccination])
def get_due_vaccinations(days_ahead: int = 7, current_user: dict = Depends(get_current_user)):
    """Get vaccinations due within N days for this ASHA worker's patients."""
    records = dynamo_service.get_due_vaccinations_for_asha(current_user["username"])
    today = date.today()
    due = []
    for r in records:
        if r.get("is_administered"):
            continue
        due_date_str = r.get("due_date", "")
        if not due_date_str:
            continue
        try:
            due_date = date.fromisoformat(due_date_str[:10])
        except ValueError:
            continue

        delta = (due_date - today).days
        if delta < 0:
            status = "overdue"
        elif delta <= days_ahead:
            status = "due_soon"
        else:
            continue

        # Get patient name
        patient = dynamo_service.get_patient(r["patient_id"])
        due.append(DueVaccination(
            patient_id=r["patient_id"],
            patient_name=patient["name"] if patient else "Unknown",
            vaccine_name=r["vaccine_name"],
            due_date=due_date_str,
            days_overdue=abs(delta) if delta < 0 else None,
            days_until_due=delta if delta >= 0 else None,
            status=status,
        ))
    return due


@router.get("/{patient_id}/summary", response_model=VaccinationSummary)
def get_vaccination_summary(patient_id: str, current_user: dict = Depends(get_current_user)):
    records = dynamo_service.get_vaccinations_for_patient(patient_id)
    today = date.today()
    completed = overdue = upcoming = 0
    for r in records:
        if r.get("is_administered"):
            completed += 1
        else:
            try:
                due_date = date.fromisoformat(r.get("due_date", "")[:10])
                if due_date < today:
                    overdue += 1
                elif (due_date - today).days <= 7:
                    upcoming += 1
            except ValueError:
                pass
    return VaccinationSummary(
        patient_id=patient_id,
        total=len(records),
        completed=completed,
        upcoming=upcoming,
        overdue=overdue,
    )
