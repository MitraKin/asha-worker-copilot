"""
Authentication router — /api/auth/*
Handles ASHA worker login, registration, token refresh.
"""
from fastapi import APIRouter, HTTPException, Depends, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import Optional
import logging

from services import cognito_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/auth", tags=["auth"])
security = HTTPBearer(auto_error=False)


# ── Request/Response models ────────────────────────────────────────────────

class LoginRequest(BaseModel):
    username: str
    password: str


class RegisterRequest(BaseModel):
    username: str
    password: str
    email: str
    name: str
    area: str  # e.g., "Gram Panchayat Raipur, Block Sadar"


class ConfirmRequest(BaseModel):
    username: str
    code: str


class RefreshRequest(BaseModel):
    refresh_token: str


# ── Routes ────────────────────────────────────────────────────────────────

@router.post("/login")
def login(req: LoginRequest):
    result = cognito_service.login_user(req.username, req.password)
    if not result:
        raise HTTPException(status_code=401, detail="Invalid username or password")
    return {
        "success": True,
        "access_token": result["access_token"],
        "id_token": result["id_token"],
        "refresh_token": result["refresh_token"],
        "expires_in": result["expires_in"],
    }


@router.post("/register")
def register(req: RegisterRequest):
    success = cognito_service.register_user(
        req.username, req.password, req.email, req.name, req.area
    )
    if not success:
        raise HTTPException(status_code=409, detail="User already exists or registration failed")
    return {
        "success": True,
        "message": "Registration successful. Please check your email for verification code.",
    }


@router.post("/confirm")
def confirm(req: ConfirmRequest):
    success = cognito_service.confirm_sign_up(req.username, req.code)
    if not success:
        raise HTTPException(status_code=400, detail="Invalid confirmation code")
    return {"success": True, "message": "Account verified. You may now log in."}


@router.post("/refresh")
def refresh(req: RefreshRequest):
    result = cognito_service.refresh_token(req.refresh_token)
    if not result:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")
    return result


@router.get("/me")
def get_me(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)):
    if not credentials:
        raise HTTPException(status_code=401, detail="Missing authorization token")
    user = cognito_service.get_user_info(credentials.credentials)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return user


# ── Dependency ── use in other routers ────────────────────────────────────

def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
):
    if not credentials:
        raise HTTPException(status_code=401, detail="Missing authorization token")
    user = cognito_service.get_user_info(credentials.credentials)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return user
