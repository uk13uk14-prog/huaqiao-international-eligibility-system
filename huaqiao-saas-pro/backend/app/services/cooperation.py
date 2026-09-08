"""Cooperation Center — settings + brands (no hardcoded H5 content)."""
from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

from sqlalchemy.orm import Session

from ..models import CooperationBrand, CooperationSettings

MEDIA_PREFIX = "/api/cooperation/media/"
_SAFE_NAME = re.compile(r"^[a-f0-9]{8,32}\.(png|jpg|jpeg|webp|gif)$", re.I)

SETTINGS_FIELDS = (
    "page_title",
    "intro",
    "contact_name",
    "wechat",
    "phone",
    "email",
    "contact_note",
    "qr_image_url",
    "show_contact_name",
    "show_wechat",
    "show_phone",
    "show_email",
    "show_contact_note",
    "show_qr",
)

CONTACT_VISIBILITY = {
    "contact_name": "show_contact_name",
    "wechat": "show_wechat",
    "phone": "show_phone",
    "email": "show_email",
    "contact_note": "show_contact_note",
    "qr_image_url": "show_qr",
}


def upload_dir(configured: str = "") -> Path:
    if configured:
        p = Path(configured)
    else:
        p = Path(__file__).resolve().parents[2] / "var" / "cooperation_uploads"
    p.mkdir(parents=True, exist_ok=True)
    return p


def is_safe_media_name(name: str) -> bool:
    return bool(name and _SAFE_NAME.match(name))


def ensure_settings(db: Session) -> CooperationSettings:
    row = db.query(CooperationSettings).filter(CooperationSettings.id == 1).first()
    if row:
        return row
    row = CooperationSettings(id=1, page_title="合作中心")
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def serialize_settings(row: CooperationSettings) -> dict:
    return {k: getattr(row, k) for k in SETTINGS_FIELDS} | {"id": row.id}


def serialize_brand(row: CooperationBrand) -> dict:
    return {
        "id": row.id,
        "brand_name": row.brand_name or "",
        "logo_url": row.logo_url or "",
        "description": row.description or "",
        "link": row.link or "",
        "sort_order": int(row.sort_order or 0),
        "is_active": bool(row.is_active),
    }


def public_contact(row: CooperationSettings) -> dict:
    out = {}
    for field, flag in CONTACT_VISIBILITY.items():
        if not getattr(row, flag, False):
            continue
        val = (getattr(row, field, None) or "").strip()
        if not val:
            continue
        key = "qr_url" if field == "qr_image_url" else field
        out[key] = val
    return out


def public_payload(db: Session) -> dict:
    settings = ensure_settings(db)
    brands = (
        db.query(CooperationBrand)
        .filter(CooperationBrand.is_active.is_(True))
        .order_by(CooperationBrand.sort_order.asc(), CooperationBrand.id.asc())
        .all()
    )
    return {
        "page_title": (settings.page_title or "合作中心").strip() or "合作中心",
        "intro": (settings.intro or "").strip(),
        "contact": public_contact(settings),
        "brands": [
            {
                "id": b.id,
                "brand_name": b.brand_name,
                "logo_url": b.logo_url or "",
                "description": b.description or "",
                "link": b.link or "",
                "sort_order": int(b.sort_order or 0),
            }
            for b in brands
        ],
    }


def apply_settings(row: CooperationSettings, data: dict) -> CooperationSettings:
    for key in SETTINGS_FIELDS:
        if key not in data:
            continue
        val = data[key]
        if key.startswith("show_"):
            setattr(row, key, bool(val))
        elif val is None:
            setattr(row, key, "")
        else:
            setattr(row, key, str(val).strip())
    row.updated_at = datetime.utcnow()
    return row


def next_sort_order(db: Session) -> int:
    current = [int(x.sort_order or 0) for x in db.query(CooperationBrand).all()]
    return (max(current) + 10) if current else 10


def reorder_brands(db: Session, ids: list[int]) -> list[CooperationBrand]:
    rows = {r.id: r for r in db.query(CooperationBrand).all()}
    order = 10
    for bid in ids:
        row = rows.get(int(bid))
        if not row:
            continue
        row.sort_order = order
        row.updated_at = datetime.utcnow()
        order += 10
    return (
        db.query(CooperationBrand)
        .order_by(CooperationBrand.sort_order.asc(), CooperationBrand.id.asc())
        .all()
    )
