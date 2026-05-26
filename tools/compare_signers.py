#!/usr/bin/env python3
"""Compare our SigV4 signer vs botocore against the live Pepper API."""

from __future__ import annotations

import argparse
import importlib.util
import sys
import types
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "custom_components" / "merkury_smart"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _bootstrap():
    pkg = types.ModuleType("merkury_smart")
    pkg.__path__ = [str(PKG)]
    sys.modules["merkury_smart"] = pkg
    cloud = types.ModuleType("merkury_smart.pepper_cloud")
    cloud.__path__ = [str(PKG / "pepper_cloud")]
    sys.modules["merkury_smart.pepper_cloud"] = cloud
    _load("merkury_smart.pepper_cloud.exceptions", PKG / "pepper_cloud" / "exceptions.py")
    signer = _load("merkury_smart.pepper_cloud.signer", PKG / "pepper_cloud" / "signer.py")
    auth = _load("merkury_smart.pepper_cloud.auth", PKG / "pepper_cloud" / "auth.py")
    urls = _load("merkury_smart.pepper_cloud.urls", PKG / "pepper_cloud" / "urls.py")
    return signer, auth, urls


def _http(method: str, url: str, headers: dict[str, str], body: bytes = b"") -> tuple[int, str]:
    kwargs: dict = {"headers": headers, "method": method}
    if body or method.upper() not in {"GET", "HEAD"}:
        kwargs["data"] = body
    req = urllib.request.Request(url, **kwargs)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as err:
        return err.code, err.read().decode("utf-8", errors="replace")


def _signed_headers_label(headers: dict[str, str]) -> str:
    auth = headers.get("Authorization", "")
    if "SignedHeaders=" in auth:
        return auth.split("SignedHeaders=", 1)[1].split(",", 1)[0]
    return "?"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--email", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--brand", default="geeni")
    args = parser.parse_args()

    signer_mod, auth_mod, urls_mod = _bootstrap()

    # Reuse test_pepper_cloud login helpers
    spec = importlib.util.spec_from_file_location(
        "test_pepper_cloud", ROOT / "tools" / "test_pepper_cloud.py"
    )
    test = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(test)

    api_base, pepper_token, aws, _ = test.login_with_regional(
        "production",
        args.brand,
        args.email,
        args.password,
    )
    url = f"{api_base.rstrip('/')}/account/devices/"
    base_headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": "okhttp/4.4.1",
        "peppertoken": pepper_token,
    }

    def probe(label: str, headers: dict[str, str]) -> None:
        sh = _signed_headers_label(headers)
        status, body = _http("GET", url, headers)
        print(f"{label}: HTTP {status} SignedHeaders={sh}")
        if status >= 400:
            print(f"  body: {body[:160]}")

    signed = signer_mod.sign_request(
        "GET",
        url,
        dict(base_headers),
        b"",
        access_key=aws["access_key_id"],
        secret_key=aws["secret_access_key"],
        session_token=aws["session_token"],
        region=aws["region"],
    )
    probe("ours", signed)

    try:
        import botocore.auth
        import botocore.awsrequest
        import botocore.credentials

        creds = botocore.credentials.Credentials(
            aws["access_key_id"],
            aws["secret_access_key"],
            aws["session_token"],
        )
        req = botocore.awsrequest.AWSRequest(
            method="GET", url=url, headers=dict(base_headers), data=b""
        )
        botocore.auth.SigV4Auth(creds, "execute-api", aws["region"]).add_auth(req)
        probe("botocore (all wire headers signed)", dict(req.headers))

        # Pepper RequestSigner only puts host + x-amz-* into DefaultRequest before sign.
        minimal = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "okhttp/4.4.1",
        }
        req2 = botocore.awsrequest.AWSRequest(
            method="GET", url=url, headers=minimal, data=b""
        )
        botocore.auth.SigV4Auth(creds, "execute-api", aws["region"]).add_auth(req2)
        signed = dict(req2.headers)
        signed["peppertoken"] = pepper_token
        probe("botocore (minimal signed + peppertoken)", signed)
    except ImportError:
        print("botocore not installed")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
