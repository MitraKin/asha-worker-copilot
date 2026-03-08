"""
DynamoDB service — all table operations for patients, assessments,
sessions, and vaccinations.
"""
import boto3
from boto3.dynamodb.conditions import Key, Attr
from botocore.exceptions import ClientError
from typing import Optional, List, Dict, Any
import logging

from config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


def _get_resource():
    return boto3.resource(
        "dynamodb",
        region_name=settings.aws_region,
        aws_access_key_id=settings.aws_access_key_id or None,
        aws_secret_access_key=settings.aws_secret_access_key or None,
        aws_session_token=settings.aws_session_token or None,
    )


# ── Patients ────────────────────────────────────────────────────────────────

def put_patient(item: Dict[str, Any]) -> None:
    db = _get_resource()
    table = db.Table(settings.dynamo_patients_table)
    table.put_item(Item=item)


def get_patient(patient_id: str) -> Optional[Dict[str, Any]]:
    db = _get_resource()
    table = db.Table(settings.dynamo_patients_table)
    resp = table.get_item(Key={"patient_id": patient_id})
    return resp.get("Item")


def update_patient(patient_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    db = _get_resource()
    table = db.Table(settings.dynamo_patients_table)

    update_expr_parts = []
    expr_attr_values = {}
    expr_attr_names = {}

    for k, v in updates.items():
        safe_key = f"#field_{k}"
        val_key = f":val_{k}"
        update_expr_parts.append(f"{safe_key} = {val_key}")
        expr_attr_names[safe_key] = k
        expr_attr_values[val_key] = v

    if not update_expr_parts:
        return get_patient(patient_id)

    update_expr = "SET " + ", ".join(update_expr_parts)
    resp = table.update_item(
        Key={"patient_id": patient_id},
        UpdateExpression=update_expr,
        ExpressionAttributeNames=expr_attr_names,
        ExpressionAttributeValues=expr_attr_values,
        ReturnValues="ALL_NEW",
    )
    return resp.get("Attributes")


def list_patients_by_asha(asha_worker_id: str) -> List[Dict[str, Any]]:
    db = _get_resource()
    table = db.Table(settings.dynamo_patients_table)
    resp = table.query(
        IndexName="asha_worker_index",
        KeyConditionExpression=Key("asha_worker_id").eq(asha_worker_id),
    )
    return resp.get("Items", [])


# ── Assessments ─────────────────────────────────────────────────────────────

def put_assessment(item: Dict[str, Any]) -> None:
    db = _get_resource()
    table = db.Table(settings.dynamo_assessments_table)
    table.put_item(Item=item)


def get_assessments_for_patient(patient_id: str, limit: int = 20) -> List[Dict[str, Any]]:
    db = _get_resource()
    table = db.Table(settings.dynamo_assessments_table)
    resp = table.query(
        KeyConditionExpression=Key("patient_id").eq(patient_id),
        ScanIndexForward=False,  # most recent first
        Limit=limit,
    )
    return resp.get("Items", [])


# ── Sessions ─────────────────────────────────────────────────────────────────

def put_session(item: Dict[str, Any]) -> None:
    db = _get_resource()
    table = db.Table(settings.dynamo_sessions_table)
    table.put_item(Item=item)


def get_session(session_id: str) -> Optional[Dict[str, Any]]:
    db = _get_resource()
    table = db.Table(settings.dynamo_sessions_table)
    resp = table.get_item(Key={"session_id": session_id})
    return resp.get("Item")


def update_session(session_id: str, updates: Dict[str, Any]) -> None:
    db = _get_resource()
    table = db.Table(settings.dynamo_sessions_table)

    update_expr_parts, expr_attr_values, expr_attr_names = [], {}, {}
    for k, v in updates.items():
        safe_key = f"#f_{k}"
        val_key = f":v_{k}"
        update_expr_parts.append(f"{safe_key} = {val_key}")
        expr_attr_names[safe_key] = k
        expr_attr_values[val_key] = v

    if update_expr_parts:
        table.update_item(
            Key={"session_id": session_id},
            UpdateExpression="SET " + ", ".join(update_expr_parts),
            ExpressionAttributeNames=expr_attr_names,
            ExpressionAttributeValues=expr_attr_values,
        )


# ── Vaccinations ──────────────────────────────────────────────────────────────

def put_vaccination(item: Dict[str, Any]) -> None:
    db = _get_resource()
    table = db.Table(settings.dynamo_vaccinations_table)
    table.put_item(Item=item)


def get_vaccinations_for_patient(patient_id: str) -> List[Dict[str, Any]]:
    db = _get_resource()
    table = db.Table(settings.dynamo_vaccinations_table)
    resp = table.query(
        KeyConditionExpression=Key("patient_id").eq(patient_id),
    )
    return resp.get("Items", [])


def update_vaccination_record(patient_id: str, vaccine_name: str, updates: Dict[str, Any]) -> None:
    db = _get_resource()
    table = db.Table(settings.dynamo_vaccinations_table)

    update_expr_parts, expr_attr_values, expr_attr_names = [], {}, {}
    for k, v in updates.items():
        safe_key = f"#f_{k}"
        val_key = f":v_{k}"
        update_expr_parts.append(f"{safe_key} = {val_key}")
        expr_attr_names[safe_key] = k
        expr_attr_values[val_key] = v

    if update_expr_parts:
        table.update_item(
            Key={"patient_id": patient_id, "vaccine_name": vaccine_name},
            UpdateExpression="SET " + ", ".join(update_expr_parts),
            ExpressionAttributeNames=expr_attr_names,
            ExpressionAttributeValues=expr_attr_values,
        )


def get_due_vaccinations_for_asha(asha_worker_id: str, days_ahead: int = 7) -> List[Dict[str, Any]]:
    """Query due vaccinations by ASHA worker ID via GSI."""
    db = _get_resource()
    table = db.Table(settings.dynamo_vaccinations_table)
    resp = table.query(
        IndexName="asha_due_index",
        KeyConditionExpression=Key("asha_worker_id").eq(asha_worker_id),
        FilterExpression=Attr("is_administered").eq(False),
    )
    return resp.get("Items", [])
