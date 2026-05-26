#!/usr/bin/env python3
"""Test Pepper OS cloud login and device discovery for Merkury Smart.

Signed account API calls require HTTP/2 (same as the Android app). Install deps with:
  python -m pip install "httpx[http2]"

Usage:
  python tools/test_pepper_cloud.py --email you@example.com --password 'your-password'
"""

from __future__ import annotations

import argparse
import base64
import importlib.util
import json
import sys
import types
import urllib.parse
from pathlib import Path
from typing import Any

try:
    import httpx
except ImportError as exc:  # pragma: no cover - CLI guard
    raise SystemExit(
        'Install test dependencies: python -m pip install "httpx[http2]"'
    ) from exc

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "custom_components" / "merkury_smart"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _bootstrap_integration_modules():
    """Load pepper_cloud helpers without importing Home Assistant."""

    pkg = types.ModuleType("merkury_smart")
    pkg.__path__ = [str(PKG)]
    sys.modules["merkury_smart"] = pkg
    sys.modules["merkury_smart.const"] = _load("merkury_smart.const", PKG / "const.py")

    cloud_pkg = types.ModuleType("merkury_smart.pepper_cloud")
    cloud_pkg.__path__ = [str(PKG / "pepper_cloud")]
    sys.modules["merkury_smart.pepper_cloud"] = cloud_pkg

    _load("merkury_smart.pepper_cloud.exceptions", PKG / "pepper_cloud" / "exceptions.py")
    _load("merkury_smart.pepper_cloud.signer", PKG / "pepper_cloud" / "signer.py")
    urls = _load("merkury_smart.pepper_cloud.urls", PKG / "pepper_cloud" / "urls.py")
    auth = _load("merkury_smart.pepper_cloud.auth", PKG / "pepper_cloud" / "auth.py")
    devices = _load(
        "merkury_smart.pepper_cloud.devices", PKG / "pepper_cloud" / "devices.py"
    )
    exceptions = sys.modules["merkury_smart.pepper_cloud.exceptions"]
    signer = sys.modules["merkury_smart.pepper_cloud.signer"]
    return auth, devices, exceptions, signer, urls


auth_mod, devices_mod, exc_mod, signer_mod, urls_mod = _bootstrap_integration_modules()
parse_login_response = auth_mod.parse_login_response
extract_lr_token = auth_mod.extract_lr_token
summarize_login_response = auth_mod.summarize_login_response
build_discovered_entry = devices_mod.build_discovered_entry
normalize_device_state = devices_mod.normalize_device_state
PepperAuthError = exc_mod.PepperAuthError
PepperMfaRequiredError = exc_mod.PepperMfaRequiredError
PepperCloudError = exc_mod.PepperCloudError
PepperApiError = exc_mod.PepperApiError
ensure_trailing_slash = signer_mod.ensure_trailing_slash
sign_request = signer_mod.sign_request
resolve_regional_base_url = urls_mod.resolve_regional_base_url

ENVIRONMENT_HOSTS = urls_mod.DEFAULT_HOSTS


def _join_url(base: str, path: str) -> str:
    return base.rstrip("/") + ensure_trailing_slash(
        path if path.startswith("/") else f"/{path}"
    )


_HTTP_CLIENT: httpx.Client | None = None


def _get_http_client() -> httpx.Client:
    global _HTTP_CLIENT
    if _HTTP_CLIENT is None or _HTTP_CLIENT.is_closed:
        _HTTP_CLIENT = httpx.Client(http2=True, timeout=30.0)
    return _HTTP_CLIENT


def _http_request(
    method: str,
    url: str,
    headers: dict[str, str],
    body: bytes = b"",
) -> tuple[int, str]:
    client = _get_http_client()
    response = client.request(
        method,
        url,
        headers=headers,
        content=body or None,
    )
    return response.status_code, response.text


def _basic_auth(brand: str, username: str, password: str) -> str:
    token = base64.b64encode(f"{brand}:{username}:{password}".encode()).decode("ascii")
    return f"Basic {token}"


DEFAULT_USER_AGENT = "okhttp/4.4.1"
AUTH_BODY = b"null"


def _auth_headers() -> dict[str, str]:
    return {
        "Accept": "application/json",
        "Content-Type": "application/json; charset=utf-8",
        "Content-Length": str(len(AUTH_BODY)),
        "User-Agent": DEFAULT_USER_AGENT,
    }


def login(
    base_url: str,
    brand: str,
    email: str,
    password: str,
    *,
    dump: bool = False,
) -> tuple[str, dict[str, str], dict[str, Any]]:
    url = f"{base_url.rstrip('/')}/authentication/byEmail"
    status, body = _http_request(
        "POST",
        url,
        {
            "Authorization": _basic_auth(brand, email, password),
            **_auth_headers(),
        },
        AUTH_BODY,
    )
    if status == 401:
        raise PepperAuthError("Invalid email or password")
    if status >= 400:
        raise PepperApiError(status, body or "Authentication failed")

    data = json.loads(body)
    if not isinstance(data, dict):
        raise PepperCloudError("Unexpected authentication response")
    if dump:
        print(
            f"DEBUG login summary ({base_url}): "
            + json.dumps(summarize_login_response(data), indent=2),
            file=sys.stderr,
        )

    session = parse_login_response(data)
    creds = {
        "access_key_id": session.access_key_id,
        "secret_access_key": session.secret_access_key,
        "session_token": session.session_token,
        "region": session.region,
    }
    return session.pepper_token, creds, data


def refresh_by_token(
    base_url: str,
    brand: str,
    token_value: str,
    *,
    dump: bool = False,
) -> tuple[str, dict[str, str], dict[str, Any]] | None:
    """Call authenticateByToken using lrToken (LoginRadius session id)."""

    if not token_value:
        return None

    url = f"{base_url.rstrip('/')}/authentication/byToken"
    token = base64.b64encode(f"{brand}:{token_value}".encode()).decode("ascii")
    status, body = _http_request(
        "POST",
        url,
        {
            "Authorization": f"Basic {token}",
            **_auth_headers(),
        },
        AUTH_BODY,
    )
    if status >= 400:
        if dump:
            print(
                f"DEBUG authenticateByToken HTTP {status} (continuing with byEmail session)",
                file=sys.stderr,
            )
        return None

    data = json.loads(body)
    if not isinstance(data, dict):
        return None
    if dump:
        print(
            "DEBUG authenticateByToken summary: "
            + json.dumps(summarize_login_response(data), indent=2),
            file=sys.stderr,
        )
    session = parse_login_response(data)
    creds = {
        "access_key_id": session.access_key_id,
        "secret_access_key": session.secret_access_key,
        "session_token": session.session_token,
        "region": session.region,
    }
    return session.pepper_token, creds, data


def login_with_regional(
    environment: str,
    brand: str,
    email: str,
    password: str,
    *,
    dump: bool = False,
    debug: bool = False,
    skip_regional_login: bool = False,  # noqa: ARG001 — kept for CLI compatibility
    use_by_token: bool = False,
) -> tuple[str, str, dict[str, str], dict[str, Any]]:
    """Login at the global Pepper host (matches app fresh sign-in capture)."""

    api_base = ENVIRONMENT_HOSTS[environment].rstrip("/")
    if debug or dump:
        print(f"DEBUG login at {api_base} (app environment={environment})", file=sys.stderr)

    pepper_token, aws, login_data = login(
        api_base, brand, email, password, dump=dump
    )

    if not use_by_token:
        if dump or debug:
            print(
                "DEBUG using byEmail session only (MITM capture: no byToken on fresh sign-in)",
                file=sys.stderr,
            )
        return api_base, pepper_token, aws, login_data

    lr_token = extract_lr_token(login_data)
    refreshed = refresh_by_token(
        api_base,
        brand,
        lr_token,
        dump=dump or debug,
    )
    if not refreshed:
        raise PepperCloudError("authenticateByToken failed")
    pepper_token, aws, login_data = refreshed
    return api_base, pepper_token, aws, login_data


def _signed_headers_label(headers: dict[str, str]) -> str:
    auth = headers.get("Authorization", "")
    if "SignedHeaders=" in auth:
        return auth.split("SignedHeaders=", 1)[1].split(",", 1)[0]
    return "?"


def signed_request(
    base_url: str,
    method: str,
    path: str,
    pepper_token: str | None,
    aws: dict[str, str],
    body: bytes = b"",
    *,
    query: dict[str, str] | None = None,
    debug: bool = False,
) -> Any:
    url = _join_url(base_url, path)
    if query:
        params = "&".join(
            f"{urllib.parse.quote(key, safe='-_.~')}="
            f"{urllib.parse.quote(value, safe='-_.~')}"
            for key, value in sorted(query.items())
        )
        url = f"{url}?{params}"
    headers = {
        "Accept": "application/json",
        "User-Agent": DEFAULT_USER_AGENT,
    }
    if body:
        headers["Content-Type"] = "application/json; charset=utf-8"
        headers["Content-Length"] = str(len(body))
    else:
        headers["Content-Type"] = "application/json"
    if pepper_token:
        headers["peppertoken"] = pepper_token

    signed_headers = sign_request(
        method,
        url,
        headers,
        body,
        access_key=aws["access_key_id"],
        secret_key=aws["secret_access_key"],
        session_token=aws["session_token"],
        region=aws["region"],
    )

    if debug:
        redacted = {
            k: ("***" if k.lower() in {"authorization", "peppertoken", "x-amz-security-token"} else v)
            for k, v in signed_headers.items()
        }
        print(f"DEBUG {method} {url}", file=sys.stderr)
        print(f"DEBUG SignedHeaders={_signed_headers_label(signed_headers)}", file=sys.stderr)
        print(f"DEBUG headers={json.dumps(redacted, indent=2)}", file=sys.stderr)

    status, text = _http_request(method, url, signed_headers, body)
    if status == 401:
        raise PepperCloudError("Session expired or unauthorized")
    if status >= 400:
        raise PepperApiError(status, text or "Request failed")
    if not text:
        return None
    return json.loads(text)


def list_devices(
    base_url: str,
    pepper_token: str,
    aws: dict[str, str],
    *,
    debug: bool = False,
) -> list[dict[str, Any]]:
    result = signed_request(
        base_url, "GET", "/account/devices", pepper_token, aws, debug=debug
    )
    if not isinstance(result, list):
        return []
    return [item for item in result if isinstance(item, dict)]


def _try_signed(
    label: str,
    base_url: str,
    path: str,
    pepper_token: str | None,
    aws: dict[str, str],
    *,
    query: dict[str, str] | None = None,
    debug: bool = False,
    show_sig: bool = False,
) -> None:
    url = _join_url(base_url, path)
    if query:
        params = "&".join(
            f"{urllib.parse.quote(key, safe='-_.~')}="
            f"{urllib.parse.quote(value, safe='-_.~')}"
            for key, value in sorted(query.items())
        )
        url = f"{url}?{params}"
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": DEFAULT_USER_AGENT,
    }
    if pepper_token:
        headers["peppertoken"] = pepper_token
    signed_headers = sign_request(
        "GET",
        url,
        headers,
        b"",
        access_key=aws["access_key_id"],
        secret_key=aws["secret_access_key"],
        session_token=aws["session_token"],
        region=aws["region"],
    )
    sig = _signed_headers_label(signed_headers)
    try:
        status, text = _http_request("GET", url, signed_headers)
        if status >= 400:
            raise PepperApiError(status, text or "Request failed")
        suffix = f" SignedHeaders={sig}" if show_sig else ""
        print(f"  OK  {label}{suffix}", file=sys.stderr)
    except PepperApiError as err:
        suffix = f" SignedHeaders={sig}" if show_sig else ""
        print(f"  ERR {label}: {err}{suffix}", file=sys.stderr)


def probe_endpoints(
    base_url: str,
    pepper_token: str,
    aws: dict[str, str],
    *,
    debug: bool = False,
) -> None:
    paths = [
        "/account/devices",
        "/account/contactInfo",
        "/account/deviceGroups",
    ]
    print("Probing signed endpoints:", file=sys.stderr)
    for path in paths:
        _try_signed(path, base_url, path, pepper_token, aws, debug=debug)


def diagnose_session(
    base_url: str,
    pepper_token: str,
    aws: dict[str, str],
    login_data: dict[str, Any],
    *,
    debug: bool = False,
) -> None:
    """Run controlled probes to distinguish SigV4 vs peppertoken failures."""

    print("\nDiagnose: token shapes from login (after byEmail)", file=sys.stderr)
    summary = summarize_login_response(login_data)
    print(json.dumps(summary, indent=2), file=sys.stderr)
    hint = summary.get("aws_access_key_hint")
    if hint:
        print(
            f"\nDiagnose: compare aws_access_key_hint={hint} with "
            "AccessKeyId in the app MITM capture (byEmail response)",
            file=sys.stderr,
        )

    region = aws.get("region", "")
    regional_base = resolve_regional_base_url("production", region)
    if regional_base.rstrip("/") != base_url.rstrip("/"):
        print(
            f"\nDiagnose: same account API on regional host ({regional_base})",
            file=sys.stderr,
        )
        _try_signed(
            "regional /account/devices + peppertoken",
            regional_base,
            "/account/devices",
            pepper_token,
            aws,
            show_sig=True,
        )

    print("\nDiagnose: signed GET variants for /account/devices/", file=sys.stderr)
    _try_signed(
        "devices + peppertoken header",
        base_url,
        "/account/devices",
        pepper_token,
        aws,
        debug=debug,
        show_sig=True,
    )
    _try_signed(
        "devices + no peppertoken",
        base_url,
        "/account/devices",
        None,
        aws,
        debug=debug,
    )

    cognito = login_data.get("cognitoProfile") or {}
    cognito_token = cognito.get("Token") or cognito.get("token")
    if cognito_token and str(cognito_token) != pepper_token:
        _try_signed(
            "devices + cognitoProfile.token header",
            base_url,
            "/account/devices",
            str(cognito_token),
            aws,
            debug=debug,
        )

    lr_token = login_data.get("lrToken")
    if lr_token and str(lr_token) != pepper_token:
        _try_signed(
            "devices + lrToken header",
            base_url,
            "/account/devices",
            str(lr_token),
            aws,
            debug=debug,
        )

    print("\nDiagnose: /account/contactInfo/", file=sys.stderr)
    _try_signed(
        "contactInfo + peppertoken",
        base_url,
        "/account/contactInfo",
        pepper_token,
        aws,
        show_sig=True,
    )

    aws_session_len = len(aws.get("session_token", ""))
    print(
        f"\nDiagnose: approximate request header sizes "
        f"(peppertoken={len(pepper_token)}, "
        f"x-amz-security-token={aws_session_len}, "
        f"combined~{len(pepper_token) + aws_session_len + 400})",
        file=sys.stderr,
    )

    pepper_user = login_data.get("pepperUser") or {}
    account_id = pepper_user.get("accountId") or pepper_user.get("account_id")
    if account_id:
        print(f"\nDiagnose: listLocationsByAccountId ({account_id})", file=sys.stderr)
        _try_signed(
            "locations by account id",
            base_url,
            f"/account/accounts/{account_id}/locations",
            pepper_token,
            aws,
            debug=debug,
        )

    print("\nDiagnose: deviceGroups token delivery", file=sys.stderr)
    _try_signed(
        "deviceGroups + peppertoken header",
        base_url,
        "/account/deviceGroups",
        pepper_token,
        aws,
        debug=debug,
    )
    if lr_token:
        _try_signed(
            "deviceGroups + lrToken header",
            base_url,
            "/account/deviceGroups",
            str(lr_token),
            aws,
            debug=debug,
        )
    _try_signed(
        "deviceGroups + peppertoken query param (signed)",
        base_url,
        "/account/deviceGroups",
        None,
        aws,
        query={"peppertoken": pepper_token},
        debug=debug,
    )
    _try_signed(
        "deviceGroups + header and query param",
        base_url,
        "/account/deviceGroups",
        pepper_token,
        aws,
        query={"peppertoken": pepper_token},
        debug=debug,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--email", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--brand", default="geeni")
    parser.add_argument(
        "--environment",
        default="production",
        choices=list(ENVIRONMENT_HOSTS),
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Print signed request URL and headers (secrets redacted)",
    )
    parser.add_argument(
        "--dump-login",
        action="store_true",
        help="Print redacted login response summary",
    )
    parser.add_argument(
        "--probe",
        action="store_true",
        help="Try several signed GET endpoints before listing devices",
    )
    parser.add_argument(
        "--diagnose",
        action="store_true",
        help="Print token shapes and try signed-request variants (see stderr)",
    )
    parser.add_argument(
        "--skip-regional-login",
        action="store_true",
        help="Deprecated; login always uses the environment global host",
    )
    parser.add_argument(
        "--use-regional-api",
        action="store_true",
        help="After login, call account APIs on {region}.api.pepperos.io",
    )
    parser.add_argument(
        "--use-by-token",
        action="store_true",
        help="Also call authenticateByToken after byEmail (not used on fresh sign-in in v2.8.1)",
    )
    args = parser.parse_args()

    try:
        api_base, pepper_token, aws, login_data = login_with_regional(
            args.environment,
            args.brand,
            args.email,
            args.password,
            dump=args.dump_login or args.debug or args.diagnose,
            debug=args.debug,
            skip_regional_login=args.skip_regional_login,
            use_by_token=args.use_by_token,
        )
        print("Login OK")
        if args.use_regional_api:
            api_base = resolve_regional_base_url(args.environment, aws.get("region"))
            print(f"Using regional account API host: {api_base}")
        if args.debug:
            print(f"DEBUG region={aws['region']}", file=sys.stderr)
            print(f"DEBUG api_host={api_base}", file=sys.stderr)

        if args.probe:
            probe_endpoints(api_base, pepper_token, aws, debug=args.debug)

        if args.diagnose:
            diagnose_session(
                api_base,
                pepper_token,
                aws,
                login_data,
                debug=args.debug,
            )

        devices = list_devices(api_base, pepper_token, aws, debug=args.debug)
        print(f"\nFound {len(devices)} device(s):\n")
        for device in devices:
            entry = build_discovered_entry(device)
            state = normalize_device_state(device)
            print(f"- {entry['name']} ({entry['device_id']})")
            print(
                f"  class={entry['device_class']} model={entry.get('model')} "
                f"provider={entry.get('provider')}"
            )
            print(
                "  state="
                + json.dumps(
                    {k: v for k, v in state.items() if k != "raw"},
                    default=str,
                )
            )
    except PepperMfaRequiredError as err:
        print(f"MFA required: {err}", file=sys.stderr)
        return 1
    except PepperAuthError as err:
        print(f"Authentication failed: {err}", file=sys.stderr)
        return 1
    except PepperCloudError as err:
        print(f"Cloud error: {err}", file=sys.stderr)
        return 1
    except PepperApiError as err:
        print(f"API error: {err}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
