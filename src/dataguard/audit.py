from __future__ import annotations

import uuid
from datetime import datetime, timezone


def generate_run_id(prefix: str = "run") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def build_audit_record(stage: str, status: str, details: dict[str, str | int]) -> dict[str, str | int]:
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "stage": stage,
        "status": status,
        **details,
    }
