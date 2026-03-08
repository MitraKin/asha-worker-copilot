"""
Patients router — /api/patients/*
Full CRUD for patient records.
"""
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Depends
from typing import List

from models.patient import (
    Patient, CreatePatientRequest, PatientSummary, UpdatePatientRequest
)
from services import dynamo_service
from routers.auth import get_current_user

router = APIRouter(prefix="/api/patients", tags=["patients"])


@router.post("", response_model=Patient)
def create_patient(req: CreatePatientRequest, current_user: dict = Depends(get_current_user)):
    patient_id = f"P{uuid.uuid4().hex[:12].upper()}"
    now = datetime.now(timezone.utc).isoformat()

    item = {
        "patient_id": patient_id,
        "name": req.name,
        "age": req.age,
        "gender": req.gender,
        "date_of_birth": req.date_of_birth,
        "village": req.village,
        "asha_worker_id": current_user["username"],
        "contact_number": req.contact_number,
        "chronic_conditions": req.chronic_conditions,
        "allergies": req.allergies,
        "patient_type": req.patient_type,
        "gestational_age_weeks": req.gestational_age_weeks,
        "last_menstrual_period": req.last_menstrual_period,
        "created_at": now,
        "updated_at": now,
    }
    dynamo_service.put_patient(item)
    return item


@router.get("", response_model=List[PatientSummary])
def list_patients(current_user: dict = Depends(get_current_user)):
    items = dynamo_service.list_patients_by_asha(current_user["username"])
    return [
        PatientSummary(
            patient_id=p["patient_id"],
            name=p["name"],
            age=p["age"],
            gender=p["gender"],
            village=p["village"],
            patient_type=p.get("patient_type", "general"),
            last_visit=None,
            last_risk_level=None,
        )
        for p in items
    ]


@router.get("/{patient_id}", response_model=Patient)
def get_patient(patient_id: str, current_user: dict = Depends(get_current_user)):
    patient = dynamo_service.get_patient(patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    # Access control: ASHA worker can only see their patients
    if patient.get("asha_worker_id") != current_user["username"]:
        raise HTTPException(status_code=403, detail="Access denied")
    return patient


@router.put("/{patient_id}", response_model=Patient)
def update_patient(
    patient_id: str,
    req: UpdatePatientRequest,
    current_user: dict = Depends(get_current_user),
):
    existing = dynamo_service.get_patient(patient_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Patient not found")
    if existing.get("asha_worker_id") != current_user["username"]:
        raise HTTPException(status_code=403, detail="Access denied")

    updates = {k: v for k, v in req.model_dump().items() if v is not None}
    updates["updated_at"] = datetime.now(timezone.utc).isoformat()
    updated = dynamo_service.update_patient(patient_id, updates)
    return updated


@router.get("/{patient_id}/history")
def get_patient_history(patient_id: str, current_user: dict = Depends(get_current_user)):
    patient = dynamo_service.get_patient(patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    if patient.get("asha_worker_id") != current_user["username"]:
        raise HTTPException(status_code=403, detail="Access denied")

    assessments = dynamo_service.get_assessments_for_patient(patient_id)
    vaccinations = dynamo_service.get_vaccinations_for_patient(patient_id)
    return {
        "patient": patient,
        "assessments": assessments,
        "vaccinations": vaccinations,
    }


@router.get("/stats/summary")
def get_stats(current_user: dict = Depends(get_current_user)):
    """Dashboard stats for the current ASHA worker."""
    patients = dynamo_service.list_patients_by_asha(current_user["username"])
    total = len(patients)
    pregnant = sum(1 for p in patients if p.get("patient_type") == "pregnant")
    children = sum(1 for p in patients if p.get("patient_type") == "child")

    due_vaccines = dynamo_service.get_due_vaccinations_for_asha(current_user["username"])

    return {
        "total_patients": total,
        "pregnant_patients": pregnant,
        "child_patients": children,
        "due_vaccinations": len(due_vaccines),
        "asha_worker_name": current_user.get("name", ""),
        "area": current_user.get("area", ""),
    }
