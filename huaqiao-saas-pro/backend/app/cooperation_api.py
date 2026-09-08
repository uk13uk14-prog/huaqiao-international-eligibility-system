"""Public + admin APIs for 合作中心."""
from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .config import get_settings
from .database import get_db
from .models import CooperationBrand, User
from .services.admin_rbac import require_capability
from .services.cooperation import (
    MEDIA_PREFIX,
    apply_settings,
    ensure_settings,
    is_safe_media_name,
    next_sort_order,
    public_payload,
    reorder_brands,
    serialize_brand,
    serialize_settings,
    upload_dir,
)

public_router = APIRouter(prefix="/api/cooperation", tags=["cooperation-public"])
admin_router = APIRouter(prefix="/api/admin/v1/cooperation", tags=["cooperation-admin"])

_ALLOWED_TYPES = {
    "image/png": "png",
    "image/jpeg": "jpg",
    "image/jpg": "jpg",
    "image/webp": "webp",
    "image/gif": "gif",
}
_MAX_BYTES = 2 * 1024 * 1024


class SettingsIn(BaseModel):
    page_title: str | None = None
    intro: str | None = None
    contact_name: str | None = None
    wechat: str | None = None
    phone: str | None = None
    email: str | None = None
    contact_note: str | None = None
    qr_image_url: str | None = None
    show_contact_name: bool | None = None
    show_wechat: bool | None = None
    show_phone: bool | None = None
    show_email: bool | None = None
    show_contact_note: bool | None = None
    show_qr: bool | None = None


class BrandIn(BaseModel):
    brand_name: str = Field(default="", max_length=160)
    logo_url: str = ""
    description: str = ""
    link: str = ""
    sort_order: int | None = None
    is_active: bool = True


class BrandPatch(BaseModel):
    brand_name: str | None = None
    logo_url: str | None = None
    description: str | None = None
    link: str | None = None
    sort_order: int | None = None
    is_active: bool | None = None


class ReorderIn(BaseModel):
    ids: list[int] = Field(default_factory=list)


@public_router.get("")
@public_router.get("/")
def get_public_cooperation(db: Session = Depends(get_db)):
    return public_payload(db)


@public_router.get("/media/{filename}")
def get_cooperation_media(filename: str):
    if not is_safe_media_name(filename):
        raise HTTPException(status_code=404, detail="文件不存在")
    path = upload_dir(get_settings().cooperation_upload_dir) / filename
    if not path.is_file():
        raise HTTPException(status_code=404, detail="文件不存在")
    suffix = path.suffix.lower()
    media = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp", ".gif": "image/gif"}
    return FileResponse(path, media_type=media.get(suffix, "application/octet-stream"))


@admin_router.get("/settings")
def admin_get_settings(
    admin: User = Depends(require_capability("cooperation.read")),
    db: Session = Depends(get_db),
):
    return serialize_settings(ensure_settings(db))


@admin_router.patch("/settings")
def admin_patch_settings(
    body: SettingsIn,
    admin: User = Depends(require_capability("cooperation.write")),
    db: Session = Depends(get_db),
):
    row = ensure_settings(db)
    apply_settings(row, body.model_dump(exclude_unset=True))
    db.add(row)
    db.commit()
    db.refresh(row)
    return serialize_settings(row)


@admin_router.get("/brands")
def admin_list_brands(
    admin: User = Depends(require_capability("cooperation.read")),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(CooperationBrand)
        .order_by(CooperationBrand.sort_order.asc(), CooperationBrand.id.asc())
        .all()
    )
    return {"brands": [serialize_brand(r) for r in rows]}


@admin_router.post("/brands")
def admin_create_brand(
    body: BrandIn,
    admin: User = Depends(require_capability("cooperation.write")),
    db: Session = Depends(get_db),
):
    name = (body.brand_name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="品牌名称不能为空")
    row = CooperationBrand(
        brand_name=name,
        logo_url=(body.logo_url or "").strip(),
        description=(body.description or "").strip(),
        link=(body.link or "").strip(),
        sort_order=body.sort_order if body.sort_order is not None else next_sort_order(db),
        is_active=bool(body.is_active),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return serialize_brand(row)


@admin_router.patch("/brands/{brand_id}")
def admin_patch_brand(
    brand_id: int,
    body: BrandPatch,
    admin: User = Depends(require_capability("cooperation.write")),
    db: Session = Depends(get_db),
):
    row = db.query(CooperationBrand).filter(CooperationBrand.id == brand_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="品牌不存在")
    data = body.model_dump(exclude_unset=True)
    if "brand_name" in data:
        name = (data["brand_name"] or "").strip()
        if not name:
            raise HTTPException(status_code=400, detail="品牌名称不能为空")
        row.brand_name = name
    for key in ("logo_url", "description", "link"):
        if key in data:
            setattr(row, key, (data[key] or "").strip())
    if "sort_order" in data and data["sort_order"] is not None:
        row.sort_order = int(data["sort_order"])
    if "is_active" in data and data["is_active"] is not None:
        row.is_active = bool(data["is_active"])
    row.updated_at = datetime.utcnow()
    db.add(row)
    db.commit()
    db.refresh(row)
    return serialize_brand(row)


@admin_router.delete("/brands/{brand_id}")
def admin_delete_brand(
    brand_id: int,
    admin: User = Depends(require_capability("cooperation.write")),
    db: Session = Depends(get_db),
):
    row = db.query(CooperationBrand).filter(CooperationBrand.id == brand_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="品牌不存在")
    db.delete(row)
    db.commit()
    return {"ok": True, "id": brand_id}


@admin_router.post("/brands/reorder")
def admin_reorder_brands(
    body: ReorderIn,
    admin: User = Depends(require_capability("cooperation.write")),
    db: Session = Depends(get_db),
):
    rows = reorder_brands(db, body.ids or [])
    db.commit()
    return {"brands": [serialize_brand(r) for r in rows]}


@admin_router.post("/upload")
async def admin_upload_image(
    file: UploadFile = File(...),
    admin: User = Depends(require_capability("cooperation.write")),
):
    ctype = (file.content_type or "").split(";")[0].strip().lower()
    ext = _ALLOWED_TYPES.get(ctype)
    if not ext:
        raise HTTPException(status_code=400, detail="仅支持 PNG / JPG / WEBP / GIF")
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="文件为空")
    if len(raw) > _MAX_BYTES:
        raise HTTPException(status_code=400, detail="图片不能超过 2MB")
    name = f"{uuid.uuid4().hex[:16]}.{ext}"
    dest = upload_dir(get_settings().cooperation_upload_dir) / name
    dest.write_bytes(raw)
    url = f"{MEDIA_PREFIX}{name}"
    return {"url": url, "filename": name}
