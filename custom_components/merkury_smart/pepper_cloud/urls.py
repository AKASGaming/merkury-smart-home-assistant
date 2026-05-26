"""Pepper OS API host resolution (matches Pepper SDK environmentMap)."""

from __future__ import annotations

ENVIRONMENT_PREFIX: dict[str, str] = {
    "production": "",
    "staging": "staging.",
    "uat": "uat.",
    "dev": "dev.",
}

REGION_PREFIX: dict[str, str] = {
    "us-east-1": "us-east-1.",
    "us-east-2": "us-east-2.",
    "us-west-2": "us-west-2.",
}

DEFAULT_HOSTS: dict[str, str] = {
    "production": "https://api.pepperos.io",
    "staging": "https://staging.api.pepperos.io",
    "uat": "https://uat.api.pepperos.io",
    "dev": "https://dev.api.pepperos.io",
}


def resolve_regional_base_url(environment: str, region: str | None) -> str:
    """Return the regional API host used by the Merkury Smart app after login."""

    env_prefix = ENVIRONMENT_PREFIX.get(environment)
    if env_prefix is None:
        raise ValueError(f"Unsupported environment: {environment}")

    region_prefix = REGION_PREFIX.get(region or "", "")
    if not region_prefix:
        return DEFAULT_HOSTS[environment]

    return f"https://{region_prefix}{env_prefix}api.pepperos.io"
