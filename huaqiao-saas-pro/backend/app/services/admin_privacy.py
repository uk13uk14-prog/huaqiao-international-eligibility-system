"""Admin DTO privacy: mask sensitive fields; never expose cipher_blob."""
from __future__ import annotations

import copy
from typing import Any

from .privacy import mask_id_card, mask_passport, mask_sensitive_fields

# Extra keys commonly used in student profile / documents.
EXTRA_MASK_KEYS = {
    "passport_info",
    "passport_number",
    "passport_no",
    "id_card",
    "id_card_number",
    "id_number",
    "national_id",
    "document_number",
    "document_no",
    "certificate_no",
    "hukou_number",
    "household_info",
}


def _mask_scalar(key: str, value: Any) -> Any:
    if not isinstance(value, str) or not value:
        return value
    kl = key.lower()
    if "passport" in kl:
        return mask_passport(value)
    if any(x in kl for x in ("id_card", "id_number", "national_id", "hukou")):
        return mask_id_card(value)
    if any(x in kl for x in ("document_number", "document_no", "certificate_no")):
        return mask_id_card(value)
    if key in EXTRA_MASK_KEYS:
        return mask_id_card(value) if len(value) >= 4 else "****"
    return value


def redact_profile_for_admin(profile: dict | None, *, role: str = "super_admin") -> dict:
    """Return a deep-copied profile with sensitive identity fields masked.

    V1: always mask (even super_admin). Unmask is a future capability.
    support role gets a further stripped view (no identity documents section detail).
    """
    if not profile or not isinstance(profile, dict):
        return {}
    doc = copy.deepcopy(profile)
    # Strip any accidental cipher fields
    doc.pop("cipher_blob", None)
    doc.pop("cipher", None)

    # First pass: known mask keys; second pass: pattern-based nested walk.
    masked = mask_sensitive_fields(doc, fields_to_mask=set(EXTRA_MASK_KEYS))
    masked = _walk_mask(masked)

    if role == "support":
        # Support: only basic + owner-facing contact-ish summary, strip deep identity.
        basic = masked.get("basic_info") or {}
        return {
            "schema_version": masked.get("schema_version"),
            "basic_info": {
                "chinese_name": basic.get("chinese_name") or "",
                "english_name": basic.get("english_name") or "",
                "current_country": basic.get("current_country") or "",
                "current_city": basic.get("current_city") or "",
            },
            "summary": masked.get("summary") or {},
            "_privacy": {"role": "support", "view": "minimal"},
        }

    masked["_privacy"] = {
        "role": role,
        "masked": True,
        "note": "Sensitive document numbers are masked by default in Admin V1.",
    }
    return masked


def _walk_mask(node: Any) -> Any:
    if isinstance(node, dict):
        out = {}
        for k, v in node.items():
            if isinstance(v, (dict, list)):
                out[k] = _walk_mask(v)
            else:
                out[k] = _mask_scalar(k, v)
        return out
    if isinstance(node, list):
        return [_walk_mask(x) for x in node]
    return node


def assert_no_cipher(payload: Any) -> None:
    """Raise AssertionError if cipher_blob appears anywhere (tests / safety)."""
    if isinstance(payload, dict):
        if "cipher_blob" in payload:
            raise AssertionError("cipher_blob must not be exposed")
        for v in payload.values():
            assert_no_cipher(v)
    elif isinstance(payload, list):
        for item in payload:
            assert_no_cipher(item)


def public_student_meta(row) -> dict:
    """Safe student list/meta fields (no profile blob)."""
    return {
        "id": row.id,
        "display_name": row.display_name or "",
        "user_id": row.user_id,
        "tenant_id": row.tenant_id,
        "status": row.status,
        "source": row.source,
        "schema_version": row.schema_version,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }
