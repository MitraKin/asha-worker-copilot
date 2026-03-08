"""
Amazon Cognito service — user authentication for ASHA workers.
"""
import boto3
import logging
import hmac
import hashlib
import base64
from typing import Optional, Dict, Any

from config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


def _get_cognito_client():
    return boto3.client(
        "cognito-idp",
        region_name=settings.cognito_region,
        aws_access_key_id=settings.aws_access_key_id or None,
        aws_secret_access_key=settings.aws_secret_access_key or None,
        aws_session_token=settings.aws_session_token or None,
    )


def _compute_secret_hash(username: str) -> str:
    """Compute Cognito secret hash if client secret is configured."""
    # Only needed if Cognito App Client has a secret
    return ""


def login_user(username: str, password: str) -> Optional[Dict[str, Any]]:
    """
    Authenticate ASHA worker with Cognito.
    Returns tokens on success, None on failure.
    """
    client = _get_cognito_client()
    try:
        resp = client.initiate_auth(
            AuthFlow="USER_PASSWORD_AUTH",
            AuthParameters={
                "USERNAME": username,
                "PASSWORD": password,
            },
            ClientId=settings.cognito_client_id,
        )
        auth = resp.get("AuthenticationResult", {})
        return {
            "access_token": auth.get("AccessToken"),
            "id_token": auth.get("IdToken"),
            "refresh_token": auth.get("RefreshToken"),
            "expires_in": auth.get("ExpiresIn", 3600),
        }
    except client.exceptions.NotAuthorizedException:
        logger.warning(f"Login failed for user: {username}")
        return None
    except Exception as e:
        logger.error(f"Cognito login error: {e}")
        return None


def register_user(username: str, password: str, email: str, name: str, area: str) -> bool:
    """Register a new ASHA worker in Cognito."""
    client = _get_cognito_client()
    try:
        client.sign_up(
            ClientId=settings.cognito_client_id,
            Username=username,
            Password=password,
            UserAttributes=[
                {"Name": "email", "Value": email},
                {"Name": "name", "Value": name},
                {"Name": "custom:area", "Value": area},
                {"Name": "custom:role", "Value": "asha_worker"},
            ],
        )
        return True
    except client.exceptions.UsernameExistsException:
        logger.warning(f"User already exists: {username}")
        return False
    except Exception as e:
        logger.error(f"Cognito register error: {e}")
        return False


def confirm_sign_up(username: str, confirmation_code: str) -> bool:
    """Confirm user registration with OTP."""
    client = _get_cognito_client()
    try:
        client.confirm_sign_up(
            ClientId=settings.cognito_client_id,
            Username=username,
            ConfirmationCode=confirmation_code,
        )
        return True
    except Exception as e:
        logger.error(f"Confirm signup error: {e}")
        return False


def get_user_info(access_token: str) -> Optional[Dict[str, Any]]:
    """Get ASHA worker info from a valid access token."""
    client = _get_cognito_client()
    try:
        resp = client.get_user(AccessToken=access_token)
        attrs = {a["Name"]: a["Value"] for a in resp.get("UserAttributes", [])}
        return {
            "username": resp.get("Username"),
            "name": attrs.get("name", ""),
            "email": attrs.get("email", ""),
            "area": attrs.get("custom:area", ""),
            "role": attrs.get("custom:role", "asha_worker"),
        }
    except Exception as e:
        logger.error(f"Get user info error: {e}")
        return None


def refresh_token(refresh_tok: str) -> Optional[Dict[str, Any]]:
    """Refresh Cognito access token."""
    client = _get_cognito_client()
    try:
        resp = client.initiate_auth(
            AuthFlow="REFRESH_TOKEN_AUTH",
            AuthParameters={"REFRESH_TOKEN": refresh_tok},
            ClientId=settings.cognito_client_id,
        )
        auth = resp.get("AuthenticationResult", {})
        return {
            "access_token": auth.get("AccessToken"),
            "id_token": auth.get("IdToken"),
            "expires_in": auth.get("ExpiresIn", 3600),
        }
    except Exception as e:
        logger.error(f"Token refresh error: {e}")
        return None
