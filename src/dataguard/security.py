from __future__ import annotations

import re
from pathlib import Path


def redact_value(value: object) -> str:
    """Return a privacy-safe representation of a value for logs and reports."""
    text = str(value)
    if text == "":
        return "<empty>"
    if len(text) <= 6:
        return "***"
    return f"{text[:2]}***{text[-2:]}"


def sanitize_path(path: str | Path) -> str:
    """Replace sensitive path segments with a generic placeholder."""
    safe = str(path)
    safe = safe.replace("\\", "/")
    match = re.search(r"(?:[A-Za-z]:)?/(.+)", safe)
    if match:
        return f".../{match.group(1).split('/')[-1]}"
    return safe


def safe_log_message(message: str, *values: object) -> str:
    """Create a deterministic, redacted message for logs."""
    if not values:
        return message
    masked = [redact_value(v) for v in values]
    return message.format(*masked)
