"""Durable audit events for Admin / AI Expert console.

Metadata must NEVER contain passport/ID plaintext.
"""
from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from ..models import AuditEvent

# Actions used by Admin V1
VIEW_STUDENT = "VIEW_STUDENT"
CSCA_UPDATE = "CSCA_UPDATE"
AI_GENERATE = "AI_GENERATE"
AI_EDIT = "AI_EDIT"
AI_APPROVE = "AI_APPROVE"
AI_PUBLISH = "AI_PUBLISH"

_SENSITIVE_KEY_RE = re.compile(
    r"(passport|id_card|id_number|national_id|document_no|certificate_no|hukou)",
    re.I,
)


def _scrub(obj: Any) -> Any:
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if _SENSITIVE_KEY_RE.search(str(k)):
                out[k] = "[REDACTED]"
            else:
                out[k] = _scrub(v)
        return out
    if isinstance(obj, list):
        return [_scrub(x) for x in obj]
    if isinstance(obj, str) and len(obj) >= 10 and obj[:1].isalpha() and any(c.isdigit() for c in obj):
        # Heuristic: do not store long alphanumeric document-like strings
        return obj[:2] + "***"
    return obj


def record_audit(
    db: Session,
    *,
    actor_user_id: int | None,
    action: str,
    resource_type: str,
    resource_id: str | int | None = None,
    student_id: int | None = None,
    metadata: dict | None = None,
) -> AuditEvent:
    safe_meta = _scrub(metadata or {})
    row = AuditEvent(
        actor_user_id=actor_user_id,
        action=action,
        resource_type=resource_type,
        resource_id=str(resource_id) if resource_id is not None else None,
        student_id=student_id,
        metadata_json=json.dumps(safe_meta, ensure_ascii=False),
        created_at=datetime.utcnow(),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row
