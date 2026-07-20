"""Best-effort redaction for logs and terminal diagnostics."""

import re
from collections.abc import Mapping
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

REDACTED = "<redacted>"
_SENSITIVE_KEY = re.compile(
    r"(?:authorization|api[_-]?key|token|secret|password|credential|cookie)", re.IGNORECASE
)
_BEARER = re.compile(r"(?i)(bearer\s+)[A-Za-z0-9._~+\-/=]+")
_ASSIGNED_SECRET = re.compile(
    r"(?i)([\"']?(?:api[_-]?key|token|secret|password|credential)[\"']?\s*[:=]\s*[\"']?)"
    r"([^\"',}\s]+)"
)


def is_sensitive_key(key: str) -> bool:
    return bool(_SENSITIVE_KEY.search(key))


def redact_text(value: str) -> str:
    """Remove bearer values and sensitive URL query values from text."""
    redacted = _BEARER.sub(r"\1" + REDACTED, value)
    redacted = _ASSIGNED_SECRET.sub(r"\1" + REDACTED, redacted)
    return re.sub(
        r"(?i)([?&](?:api[_-]?key|token|secret|password)=)[^&#\s]+",
        r"\1" + REDACTED,
        redacted,
    )


def redact_url(url: str) -> str:
    parts = urlsplit(url)
    query = [
        (key, REDACTED if is_sensitive_key(key) else value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
    ]
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


def redact_mapping(data: Mapping[str, Any]) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for key, value in data.items():
        if is_sensitive_key(str(key)):
            output[str(key)] = REDACTED
        elif isinstance(value, Mapping):
            output[str(key)] = redact_mapping(value)
        elif isinstance(value, list):
            output[str(key)] = [
                redact_mapping(item) if isinstance(item, Mapping) else item for item in value
            ]
        elif isinstance(value, str):
            output[str(key)] = redact_text(value)
        else:
            output[str(key)] = value
    return output


def redact_deployment_plan(data: Mapping[str, Any]) -> dict[str, Any]:
    """Redact sensitive fields plus every user-supplied container env value."""
    output = redact_mapping(data)
    environment = output.get("env")
    if isinstance(environment, dict):
        output["env"] = {str(key): REDACTED for key in environment}
    return output
