"""Small local security controls; enterprise infrastructure is still required."""

import hashlib
import json
import re
from typing import Any


SENSITIVE_KEYS = {"api_key", "authorization", "secret", "token", "password"}


def redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: "[REDACTED]" if key.casefold() in SENSITIVE_KEYS else redact(child)
            for key, child in value.items()
        }
    if isinstance(value, list):
        return [redact(child) for child in value]
    if isinstance(value, str):
        value = re.sub(r"sk-[A-Za-z0-9_-]{10,}", "[REDACTED_API_KEY]", value)
    return value


def canonical_checksum(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
