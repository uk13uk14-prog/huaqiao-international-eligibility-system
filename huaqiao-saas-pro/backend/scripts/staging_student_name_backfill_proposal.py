#!/usr/bin/env python3
"""Read-only proposal: sync display_name from cipher chinese/english names.

Default: dry-run. Never invent names. Never use email.
Production apply forbidden unless APPLY_STAGING=1 and DB is staging.
"""
from __future__ import annotations
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

def main():
    url = os.environ.get("DATABASE_URL", "")
    apply = os.environ.get("APPLY_STAGING") == "1"
    if "5433" in url or url.rstrip("/").endswith("/huaqiao"):
        print("REFUSE: looks like production DB")
        return 2
    from app.database import SessionLocal
    from app.models import StudentMasterProfile
    from app.services.vault_crypto import decrypt_profile_json
    from app.services.student_profile import display_name_of, normalize_profile
    from app.services.student_crm import is_placeholder_name
    db = SessionLocal()
    rows = db.query(StudentMasterProfile).filter(StudentMasterProfile.status != "DELETED").all()
    proposals = []
    for row in rows:
        try:
            prof = normalize_profile(decrypt_profile_json(row.cipher_blob) if row.cipher_blob else {})
        except Exception as e:
            proposals.append({"id": row.id, "error": str(e)})
            continue
        resolved = display_name_of(prof)
        current = row.display_name or ""
        if is_placeholder_name(current) and not is_placeholder_name(resolved):
            proposals.append({"id": row.id, "from": current, "to": resolved, "source": "cipher_basic_info"})
            if apply:
                row.display_name = resolved
                db.add(row)
        else:
            proposals.append({"id": row.id, "from": current, "to": current, "source": "no_change" if not is_placeholder_name(current) else "still_unnamed"})
    if apply:
        db.commit()
    print({"apply": apply, "count": len(proposals), "proposals": proposals[:50]})
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
