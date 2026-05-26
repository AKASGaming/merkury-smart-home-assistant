"""AWS Signature Version 4 signing for Pepper OS API Gateway requests."""

from __future__ import annotations

import hashlib
import hmac
from datetime import UTC, datetime
from typing import Mapping
from urllib.parse import parse_qsl, quote, urlparse


def _sign(key: bytes, msg: str) -> bytes:
    return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()


def _canonical_query(params: Mapping[str, str] | None) -> str:
    if not params:
        return ""
    items = sorted(params.items())
    return "&".join(
        f"{quote(str(k), safe='-_.~')}={quote(str(v), safe='-_.~')}" for k, v in items
    )


def _canonical_headers(headers: Mapping[str, str]) -> tuple[str, str]:
    normalized = {
        k.lower().strip(): " ".join(v.split())
        for k, v in headers.items()
        if k.lower() not in {"authorization"}
    }
    signed = sorted(normalized)
    canonical = "".join(f"{k}:{normalized[k]}\n" for k in signed)
    return canonical, ";".join(signed)


def ensure_trailing_slash(path: str) -> str:
    if not path or path.endswith("/"):
        return path
    return f"{path}/"


def _headers_to_sign(
    host: str,
    amz_date: str,
    session_token: str,
) -> dict[str, str]:
    """Build the SigV4 header map (matches Pepper SDK RequestSigner + AWS4Signer).

    MITM captures show SignedHeaders=host;x-amz-date;x-amz-security-token for GET
    and PUT alike. peppertoken, Accept, Content-Type, and Content-Length are sent
    on the wire but are not included in the signature.
    """

    return {
        "host": host,
        "x-amz-date": amz_date,
        "x-amz-security-token": session_token,
    }


def sign_request(
    method: str,
    url: str,
    headers: dict[str, str],
    body: bytes,
    *,
    access_key: str,
    secret_key: str,
    session_token: str,
    region: str,
    service: str = "execute-api",
) -> dict[str, str]:
    """Return headers with AWS SigV4 Authorization added."""

    parsed = urlparse(url)
    path = ensure_trailing_slash(parsed.path or "/")
    host = parsed.netloc
    query_params = dict(parse_qsl(parsed.query, keep_blank_values=True))
    amz_date = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    date_stamp = amz_date[:8]
    payload_hash = hashlib.sha256(body).hexdigest()

    signed_headers_map = _headers_to_sign(host, amz_date, session_token)

    canonical_headers, signed_headers = _canonical_headers(signed_headers_map)
    canonical_request = "\n".join(
        [
            method.upper(),
            path,
            _canonical_query(query_params),
            canonical_headers,
            signed_headers,
            payload_hash,
        ]
    )

    credential_scope = f"{date_stamp}/{region}/{service}/aws4_request"
    string_to_sign = "\n".join(
        [
            "AWS4-HMAC-SHA256",
            amz_date,
            credential_scope,
            hashlib.sha256(canonical_request.encode("utf-8")).hexdigest(),
        ]
    )

    k_date = _sign(f"AWS4{secret_key}".encode("utf-8"), date_stamp)
    k_region = _sign(k_date, region)
    k_service = _sign(k_region, service)
    k_signing = _sign(k_service, "aws4_request")
    signature = hmac.new(
        k_signing, string_to_sign.encode("utf-8"), hashlib.sha256
    ).hexdigest()

    authorization = (
        f"AWS4-HMAC-SHA256 Credential={access_key}/{credential_scope}, "
        f"SignedHeaders={signed_headers}, Signature={signature}"
    )

    result = dict(headers)
    result["X-Amz-Date"] = amz_date
    result["X-Amz-Security-Token"] = session_token
    result["Authorization"] = authorization
    return result
