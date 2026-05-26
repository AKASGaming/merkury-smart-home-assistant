"""Parse Pepper OS authentication responses."""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from typing import Any

from .exceptions import PepperCloudError, PepperMfaRequiredError


@dataclass(slots=True)
class LoginSession:
    pepper_token: str
    access_key_id: str
    secret_access_key: str
    session_token: str
    region: str


def _access_key_hint(aws: dict[str, Any]) -> str | None:
    """Redacted AccessKeyId for comparing with app logcat (e.g. ASIA…XXM7)."""

    key = _pick(aws, "AccessKeyId", "accessKeyId")
    if not key:
        return None
    text = str(key)
    if len(text) <= 8:
        return text
    return f"{text[:4]}…{text[-4:]}"


def _pick(mapping: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = mapping.get(key)
        if value not in (None, ""):
            return value
    return None


def _token_shape(value: Any) -> dict[str, Any]:
    """Describe a token string without exposing its value."""

    if not value:
        return {"present": False, "length": 0}

    text = str(value)
    parts = text.split(".")
    return {
        "present": True,
        "length": len(text),
        "looks_like_jwt": len(parts) == 3 and text.startswith("eyJ"),
        "dot_segments": len(parts) - 1,
        "has_newlines": "\n" in text or "\r" in text,
        "prefix": text[:12] if len(text) >= 12 else text[:4],
    }


def summarize_jwt_claims(token: str | None) -> dict[str, Any]:
    """Decode JWT payload (no signature verification) for diagnostics."""

    if not token:
        return {"present": False}
    parts = str(token).split(".")
    if len(parts) < 2:
        return {"present": True, "decodable": False}
    payload = parts[1]
    padding = "=" * (-len(payload) % 4)
    try:
        raw = base64.urlsafe_b64decode(payload + padding)
        claims = json.loads(raw.decode("utf-8"))
    except (ValueError, json.JSONDecodeError, UnicodeDecodeError):
        return {"present": True, "decodable": False}

    if not isinstance(claims, dict):
        return {"present": True, "decodable": False}

    interesting = (
        "sub",
        "email",
        "accountId",
        "account_id",
        "userId",
        "user_id",
        "brand",
        "exp",
        "iat",
        "iss",
    )
    summary: dict[str, Any] = {
        "present": True,
        "decodable": True,
        "claim_count": len(claims),
    }
    for key in interesting:
        if key in claims:
            summary[key] = claims[key]
    return summary


def summarize_login_response(data: dict[str, Any]) -> dict[str, Any]:
    """Return a redacted summary of a login payload for debugging."""

    pepper_user = data.get("pepperUser") or {}
    aws = pepper_user.get("awsUserCredentials") or {}
    cognito = data.get("cognitoProfile") or {}
    external = pepper_user.get("externalAccountMap") or {}
    return {
        "email": data.get("email"),
        "brand": data.get("brand"),
        "token": _token_shape(data.get("token")),
        "lr_token": _token_shape(data.get("lrToken")),
        "cognito_profile_token": _token_shape(cognito.get("Token") or cognito.get("token")),
        "cognito_identity_id": cognito.get("IdentityId") or cognito.get("identityId"),
        "has_mfa_login_info": bool(data.get("mfaLoginInfo")),
        "account_id": pepper_user.get("account_id") or pepper_user.get("accountId"),
        "user_id": pepper_user.get("userId") or pepper_user.get("user_id"),
        "has_external_cognito": bool(external.get("cognito")),
        "has_external_login_radius": bool(external.get("loginRadius")),
        "aws_region": _pick(aws, "region", "Region"),
        "aws_access_key_hint": _access_key_hint(aws),
        "aws_expiration": _pick(aws, "Expiration", "expiration"),
        "has_aws_credentials": bool(
            _pick(aws, "AccessKeyId", "accessKeyId")
            and _pick(aws, "SecretAccessKey", "secretAccessKey")
            and _pick(aws, "SessionToken", "sessionToken")
        ),
        "jwt_claims": summarize_jwt_claims(data.get("token")),
    }


def extract_lr_token(data: dict[str, Any]) -> str:
    """Return LoginRadius lrToken from a byEmail response (app uses this for byToken)."""

    if data.get("mfaLoginInfo"):
        raise PepperMfaRequiredError(
            "This account requires MFA. Complete login in the Merkury Smart app first, "
            "or disable MFA temporarily for API access."
        )
    lr_token = data.get("lrToken")
    if not lr_token:
        raise PepperCloudError("Login response did not include lrToken")
    return str(lr_token)


def parse_login_response(data: dict[str, Any]) -> LoginSession:
    """Extract session token and AWS credentials from a profile response."""

    if data.get("mfaLoginInfo"):
        raise PepperMfaRequiredError(
            "This account requires MFA. Complete login in the Merkury Smart app first, "
            "or disable MFA temporarily for API access."
        )

    token = data.get("token")
    if not token:
        raise PepperCloudError("Login response did not include a token")

    pepper_user = data.get("pepperUser") or {}
    aws = pepper_user.get("awsUserCredentials") or {}

    access_key = _pick(aws, "AccessKeyId", "accessKeyId")
    secret_key = _pick(aws, "SecretAccessKey", "secretAccessKey")
    session_token = _pick(aws, "SessionToken", "sessionToken")
    region = _pick(aws, "region", "Region")

    if not all([access_key, secret_key, session_token, region]):
        raise PepperCloudError(
            "Login succeeded but temporary AWS credentials were missing"
        )

    return LoginSession(
        pepper_token=str(token),
        access_key_id=str(access_key),
        secret_access_key=str(secret_key),
        session_token=str(session_token),
        region=str(region),
    )


def apply_login_response(data: dict[str, Any]) -> LoginSession:
    """Alias for parse_login_response (used after byEmail or byToken)."""

    return parse_login_response(data)
