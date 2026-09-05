#!/usr/bin/env bash
# M1 CSCA V1 — production BUSINESS E2E (post-009)
#
# Default: INSPECT ONLY (read-only decrypt + reminder dry-run). Never one-shot.
# Does NOT invent CSCA dates, SQL-insert timeline rows, bulk-copy 900 schedules,
# run migrations, or touch Tunnel/Caddy/Cloudflare/secrets/CNBER/main.
#
# Run ON M1 only:
#   cd /Users/agent001/deploy/huaqiao-international-eligibility-system
#   git pull --ff-only origin cursor/mobile-cloud-preview
#   bash deploy/api/m1-csca-v1-business-e2e.sh --inspect-only
#
# Regenerate personalized CSCA timeline ONLY when profile already has real ISO dates
# and status is PLANNED/REGISTERED (idempotent sync_csca_timeline; never invents):
#   CONFIRM_CSCA_TIMELINE_SYNC=YES \
#   bash deploy/api/m1-csca-v1-business-e2e.sh --sync-timeline
#
# Optional write (REAL operator-supplied ISO dates only — never auto-invented):
#   CONFIRM_CSCA_BUSINESS_WRITE=YES \
#   CSCA_STATUS=REGISTERED \
#   CSCA_DATE_SOURCE=student \
#   CSCA_EXAM_DATE=YYYY-MM-DD \
#   CSCA_REGISTRATION_DEADLINE=YYYY-MM-DD \
#   CSCA_RESULT_DATE=YYYY-MM-DD \
#   bash deploy/api/m1-csca-v1-business-e2e.sh --apply-real-dates
#
# One-shot is FORBIDDEN in this script (always NOT_RUN).
set -Eeuo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
BACKEND="${ROOT}/huaqiao-saas-pro/backend"
ENV_FILE="${BACKEND}/.env"
VENV_PY="${BACKEND}/.venv/bin/python"
PG_CONTAINER="huaqiao-postgres"
EXPECTED_REV="009_csca_notification_rules"
MODE="inspect-only"

for _arg in "$@"; do
  case "${_arg}" in
    --inspect-only) MODE="inspect-only" ;;
    --sync-timeline) MODE="sync-timeline" ;;
    --apply-real-dates) MODE="apply-real-dates" ;;
    --help|-h)
      echo "Usage: $0 [--inspect-only|--sync-timeline|--apply-real-dates]"
      exit 0
      ;;
    *)
      echo "ABORT: unknown arg ${_arg}" >&2
      exit 1
      ;;
  esac
done

abort() { echo "ABORT: $*" >&2; exit 1; }
section() { echo; echo "######## $* ########"; }

[[ -x "${VENV_PY}" ]] || abort "missing ${VENV_PY}"
[[ -f "${ENV_FILE}" ]] || abort "missing ${ENV_FILE}"
docker inspect -f '{{.State.Running}}' "${PG_CONTAINER}" 2>/dev/null | grep -qx true \
  || abort "${PG_CONTAINER} not running"

# Load backend .env (secrets stay in env; never echoed).
set -a
# shellcheck disable=SC1090
source "${ENV_FILE}"
set +a

DATABASE_URL="${DATABASE_URL:-}"
[[ -n "${DATABASE_URL}" ]] || abort "DATABASE_URL missing"
case "${DATABASE_URL}" in
  sqlite*|SQLite*) abort "SQLITE_FALLBACK=BLOCKED" ;;
esac
echo "${DATABASE_URL}" | grep -qE ':5432/' && abort "DATABASE_URL port 5432 blocked"
echo "${DATABASE_URL}" | grep -qE '@(127\.0\.0\.1|localhost):5433/huaqiao($|\?)' \
  || abort "DATABASE_URL must target 127.0.0.1:5433/huaqiao"
[[ -n "${VAULT_FERNET_KEY:-}" ]] || abort "VAULT_FERNET_KEY missing (required to decrypt student profile)"

export DATABASE_URL
export VAULT_FERNET_KEY
export MODE
export CONFIRM_CSCA_BUSINESS_WRITE="${CONFIRM_CSCA_BUSINESS_WRITE:-NO}"
export CONFIRM_CSCA_TIMELINE_SYNC="${CONFIRM_CSCA_TIMELINE_SYNC:-NO}"
export CSCA_STATUS="${CSCA_STATUS:-}"
export CSCA_DATE_SOURCE="${CSCA_DATE_SOURCE:-}"
export CSCA_EXAM_DATE="${CSCA_EXAM_DATE:-}"
export CSCA_REGISTRATION_DEADLINE="${CSCA_REGISTRATION_DEADLINE:-}"
export CSCA_RESULT_DATE="${CSCA_RESULT_DATE:-}"
export EXPECTED_REV
export STUDENT_ID="${STUDENT_ID:-}"

section "GUOQIAO CSCA V1 BUSINESS E2E — MODE=${MODE}"
echo "FAKE_CSCA_DATE=NO"
echo "SQL_TIMELINE_INSERT=NO"
echo "BULK_COPY_900=NO"
echo "SCHEDULER_ONESHOT_DEFAULT=NO"
echo "MIGRATION=NO"
echo "INFRA_CHANGE=NO"

cd "${BACKEND}"
"${VENV_PY}" - <<'PY'

from __future__ import annotations

import os
import sys
from datetime import datetime

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.models import StudentMasterProfile, StudentTimelineItem
from app.services.csca import (
    CSCA_TIMELINE_SPECS,
    csca_card,
    normalize_csca,
    parse_real_date,
    sync_csca_timeline,
)
from app.services.notifications.scheduler import run_scheduler_tick
from app.services.student_profile import normalize_profile
from app.services.vault_crypto import decrypt_profile_json, encrypt_profile_json

url = os.environ["DATABASE_URL"]
mode = os.environ.get("MODE", "inspect-only")
expected_rev = os.environ.get("EXPECTED_REV", "009_csca_notification_rules")

eng = create_engine(url)
SessionLocal = sessionmaker(bind=eng, autocommit=False, autoflush=False)
db = SessionLocal()

report: dict[str, object] = {
    "DB_REVISION": "",
    "TEST_STUDENT_ID": "",
    "CSCA_STATUS": "",
    "CSCA_DATE_SOURCE": "",
    "STUDENT_TIMELINE_ITEM_COUNT": 0,
    "CSCA_TIMELINE_CREATED": "NO",
    "CSCA_TIMELINE_DEDUPE": "N/A",
    "REMINDER_DRY_RUN": "NO",
    "CANDIDATE_COUNT": 0,
    "WOULD_CREATE_COUNT": 0,
    "DEDUPE_SKIPPED_COUNT": 0,
    "CANDIDATES_VALID": "NO",
    "READY_FOR_ONESHOT": "NO",
    "SCHEDULER_ONESHOT": "NOT_RUN",
    "SECOND_RUN_DUPLICATE_CREATED": "N/A",
    "ADMIN_360_CSCA": "PENDING_MANUAL",
    "STUDENT_H5_CSCA": "PENDING_MANUAL",
    "CSCA_NOTIFICATION_E2E": "BLOCKED",
    "PRODUCTION_FREEZE": "YES",
    "NEXT_ACTION": "",
    "HAS_ANY_REAL_DATE": "NO",
    "MODE": mode,
    "FAKE_DATE_USED": "NO",
    "BUSINESS_WRITE": "NO",
}

CSCA_TITLES = {s["title"] for s in CSCA_TIMELINE_SPECS}


def emit() -> None:
    print("======== GUOQIAO_CSCA_FINAL_E2E_REPORT ========")
    for k in (
        "DB_REVISION",
        "TEST_STUDENT_ID",
        "CSCA_STATUS",
        "CSCA_DATE_SOURCE",
        "STUDENT_TIMELINE_ITEM_COUNT",
        "CSCA_TIMELINE_CREATED",
        "CSCA_TIMELINE_DEDUPE",
        "REMINDER_DRY_RUN",
        "CANDIDATE_COUNT",
        "WOULD_CREATE_COUNT",
        "DEDUPE_SKIPPED_COUNT",
        "CANDIDATES_VALID",
        "READY_FOR_ONESHOT",
        "SCHEDULER_ONESHOT",
        "SECOND_RUN_DUPLICATE_CREATED",
        "ADMIN_360_CSCA",
        "STUDENT_H5_CSCA",
        "CSCA_NOTIFICATION_E2E",
        "PRODUCTION_FREEZE",
        "HAS_ANY_REAL_DATE",
        "MODE",
        "FAKE_DATE_USED",
        "BUSINESS_WRITE",
        "NEXT_ACTION",
    ):
        print(f"{k}={report[k]}")
    print("==============================================")


def count_timeline(student_id: int) -> tuple[int, int]:
    rows = (
        db.query(StudentTimelineItem)
        .filter(StudentTimelineItem.student_id == student_id)
        .all()
    )
    csca_n = 0
    for it in rows:
        blob = f"{it.title or ''} {it.description or ''} {it.student_note or ''}"
        if (it.title or "") in CSCA_TITLES or "[csca:" in blob:
            csca_n += 1
    return len(rows), csca_n


def require_real(label: str, raw: str) -> str:
    raw = (raw or "").strip()
    if not raw:
        return ""
    parsed = parse_real_date(raw)
    if not parsed:
        raise SystemExit(f"ABORT: {label} is not a real ISO date: {raw!r}")
    if parsed.year < 2024:
        raise SystemExit(f"ABORT: {label} year looks invalid for production CSCA: {raw}")
    return parsed.isoformat()


try:
    rev = db.execute(text("SELECT version_num FROM alembic_version LIMIT 1")).scalar()
    report["DB_REVISION"] = rev or ""
    if rev != expected_rev:
        print(f"ABORT: DB revision {rev} != {expected_rev}", file=sys.stderr)
        emit()
        sys.exit(2)

    profiles_n = db.execute(
        text("SELECT count(*) FROM student_master_profiles WHERE status != 'DELETED'")
    ).scalar()
    timeline_global = db.execute(text("SELECT count(*) FROM student_timeline_items")).scalar()
    print(f"STUDENT_MASTER_PROFILES={profiles_n}")
    print(f"STUDENT_TIMELINE_ITEMS_GLOBAL={timeline_global}")

    sid_env = (os.environ.get("STUDENT_ID") or "").strip()
    q = db.query(StudentMasterProfile).filter(StudentMasterProfile.status != "DELETED")
    if sid_env:
        row = q.filter(StudentMasterProfile.id == int(sid_env)).first()
    else:
        rows = q.order_by(StudentMasterProfile.id.asc()).all()
        if len(rows) != 1:
            print(
                f"STUDENT_PROFILE_COUNT={len(rows)} (expected 1 for default path)",
                file=sys.stderr,
            )
        row = rows[0] if rows else None
    if not row:
        print("ABORT: no student_master_profiles", file=sys.stderr)
        emit()
        sys.exit(3)

    report["TEST_STUDENT_ID"] = row.id
    if not row.cipher_blob:
        profile = normalize_profile({})
    else:
        profile = normalize_profile(decrypt_profile_json(row.cipher_blob))

    csca = normalize_csca(profile.get("csca") if isinstance(profile.get("csca"), dict) else {})
    card = csca_card(csca)
    report["CSCA_STATUS"] = csca.get("csca_status") or "NOT_PLANNED"
    sources = [
        csca.get("exam_date_source") or "",
        csca.get("registration_deadline_source") or "",
        csca.get("result_date_source") or "",
    ]
    sources = [s for s in sources if s]
    report["CSCA_DATE_SOURCE"] = ",".join(sorted(set(sources))) if sources else "NONE"
    report["HAS_ANY_REAL_DATE"] = "YES" if card.get("has_any_real_date") else "NO"

    total_n, csca_n_before = count_timeline(row.id)
    report["STUDENT_TIMELINE_ITEM_COUNT"] = total_n
    print(f"CSCA_TIMELINE_ITEM_COUNT_BEFORE={csca_n_before}")
    print(f"CSCA_CARD_HAS_REAL_DATE={card.get('has_any_real_date')}")
    print(f"CSCA_EXAM_DATE_DISPLAY={card.get('csca_exam_date')}")
    print(f"CSCA_REG_DEADLINE_DISPLAY={card.get('csca_registration_deadline')}")
    print(f"CSCA_RESULT_DATE_DISPLAY={card.get('csca_result_date')}")
    print(f"TIMELINE_ELIGIBLE={card.get('timeline_eligible')}")

    wrote = False
    if mode == "inspect-only":
        print("INSPECT_TIMELINE_REFRESH=SKIPPED_READ_ONLY")
        report["CSCA_TIMELINE_CREATED"] = "YES" if csca_n_before > 0 else "NO"
        report["CSCA_TIMELINE_DEDUPE"] = "N/A"

    elif mode == "sync-timeline":
        if os.environ.get("CONFIRM_CSCA_TIMELINE_SYNC") != "YES":
            print("ABORT: set CONFIRM_CSCA_TIMELINE_SYNC=YES for --sync-timeline", file=sys.stderr)
            emit()
            sys.exit(4)
        if not card.get("has_any_real_date"):
            print("ABORT: no real CSCA dates in profile — refuse invent", file=sys.stderr)
            emit()
            sys.exit(5)
        if csca.get("csca_status") not in ("PLANNED", "REGISTERED"):
            print(
                "ABORT: csca_status must be PLANNED/REGISTERED to sync timeline",
                file=sys.stderr,
            )
            emit()
            sys.exit(6)
        sync1 = sync_csca_timeline(
            db,
            student_id=row.id,
            user_id=row.user_id,
            tenant_id=row.tenant_id,
            csca=csca,
            commit=True,
        )
        sync2 = sync_csca_timeline(
            db,
            student_id=row.id,
            user_id=row.user_id,
            tenant_id=row.tenant_id,
            csca=csca,
            commit=True,
        )
        wrote = True
        report["CSCA_TIMELINE_CREATED"] = (
            "YES" if sync1.get("created") or csca_n_before > 0 else "NO"
        )
        report["CSCA_TIMELINE_DEDUPE"] = (
            "PASS" if not sync2.get("created") else "FAIL_CREATED_AGAIN"
        )
        print(f"TIMELINE_SYNC_CREATED={sync1.get('created')}")
        print(f"TIMELINE_SYNC_UPDATED={sync1.get('updated')}")
        print(f"TIMELINE_SYNC_REMOVED={sync1.get('removed')}")
        print(f"TIMELINE_SYNC_SECOND_CREATED={sync2.get('created')}")

    elif mode == "apply-real-dates":
        if os.environ.get("CONFIRM_CSCA_BUSINESS_WRITE") != "YES":
            print("ABORT: set CONFIRM_CSCA_BUSINESS_WRITE=YES for write mode", file=sys.stderr)
            emit()
            sys.exit(4)
        status = (os.environ.get("CSCA_STATUS") or "").strip().upper()
        if status not in ("PLANNED", "REGISTERED"):
            print("ABORT: CSCA_STATUS must be PLANNED or REGISTERED", file=sys.stderr)
            emit()
            sys.exit(5)
        src = (os.environ.get("CSCA_DATE_SOURCE") or "").strip().lower()
        if src not in ("student", "admin", "official"):
            print("ABORT: CSCA_DATE_SOURCE must be student|admin|official", file=sys.stderr)
            emit()
            sys.exit(6)

        exam = require_real("CSCA_EXAM_DATE", os.environ.get("CSCA_EXAM_DATE", ""))
        reg = require_real(
            "CSCA_REGISTRATION_DEADLINE", os.environ.get("CSCA_REGISTRATION_DEADLINE", "")
        )
        result = require_real("CSCA_RESULT_DATE", os.environ.get("CSCA_RESULT_DATE", ""))
        if not any((exam, reg, result)):
            print(
                "ABORT: at least one real ISO CSCA date required (never invent)",
                file=sys.stderr,
            )
            emit()
            sys.exit(7)

        patch = {
            "csca_status": status,
            "csca_exam_date": exam,
            "csca_registration_deadline": reg,
            "csca_result_date": result,
            "exam_date_source": src if exam else "",
            "registration_deadline_source": src if reg else "",
            "result_date_source": src if result else "",
            "updated_at": datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
        }
        csca = normalize_csca({**csca, **patch})
        profile["csca"] = csca
        row.cipher_blob = encrypt_profile_json(normalize_profile(profile))
        row.updated_at = datetime.utcnow()
        db.add(row)
        db.flush()
        sync1 = sync_csca_timeline(
            db,
            student_id=row.id,
            user_id=row.user_id,
            tenant_id=row.tenant_id,
            csca=csca,
            commit=False,
        )
        sync2 = sync_csca_timeline(
            db,
            student_id=row.id,
            user_id=row.user_id,
            tenant_id=row.tenant_id,
            csca=csca,
            commit=False,
        )
        db.commit()
        wrote = True
        report["CSCA_STATUS"] = csca["csca_status"]
        report["CSCA_DATE_SOURCE"] = src
        report["HAS_ANY_REAL_DATE"] = "YES"
        report["CSCA_TIMELINE_CREATED"] = "YES" if sync1.get("created") else "NO"
        report["CSCA_TIMELINE_DEDUPE"] = (
            "PASS" if not sync2.get("created") else "FAIL_CREATED_AGAIN"
        )
        print(f"TIMELINE_SYNC_CREATED={sync1.get('created')}")
        print(f"TIMELINE_SYNC_UPDATED={sync1.get('updated')}")
        print(f"TIMELINE_SYNC_REMOVED={sync1.get('removed')}")
        print(f"TIMELINE_SYNC_SECOND_CREATED={sync2.get('created')}")
    else:
        print(f"ABORT: unknown MODE={mode}", file=sys.stderr)
        emit()
        sys.exit(8)

    total_n, csca_n_after = count_timeline(row.id)
    report["STUDENT_TIMELINE_ITEM_COUNT"] = total_n
    print(f"CSCA_TIMELINE_ITEM_COUNT_AFTER={csca_n_after}")

    # Reminder dry-run only — never one-shot in this script.
    out = run_scheduler_tick(db, dry_run=True)
    scan = out.get("scan") or {}
    cand = int(scan.get("candidate_count", scan.get("scanned_items", 0)) or 0)
    would = int(scan.get("would_create_count", 0) or 0)
    dedupe = int(scan.get("dedupe_skipped_count", 0) or 0)
    report["REMINDER_DRY_RUN"] = "PASS"
    report["CANDIDATE_COUNT"] = cand
    report["WOULD_CREATE_COUNT"] = would
    report["DEDUPE_SKIPPED_COUNT"] = dedupe
    report["CANDIDATES_VALID"] = "YES" if cand > 0 else "NO"
    report["READY_FOR_ONESHOT"] = "YES" if cand > 0 else "NO"
    report["SCHEDULER_ONESHOT"] = "NOT_RUN"
    report["SECOND_RUN_DUPLICATE_CREATED"] = "N/A"
    report["PRODUCTION_FREEZE"] = "YES"
    report["BUSINESS_WRITE"] = "YES" if wrote else "NO"

    if cand > 0 and csca_n_after > 0:
        report["CSCA_NOTIFICATION_E2E"] = "READY_FOR_ONESHOT_GATE"
        report["NEXT_ACTION"] = (
            "Manual verify Admin 360 + Student H5 CSCA cards; then only if still "
            "CANDIDATE_COUNT>0 run reminder one-shot via release script with "
            "CONFIRM_NOTIFICATION_ONESHOT=YES (this business script never runs one-shot)"
        )
        report["ADMIN_360_CSCA"] = "PENDING_MANUAL"
        report["STUDENT_H5_CSCA"] = "PENDING_MANUAL"
    else:
        report["CSCA_NOTIFICATION_E2E"] = "BLOCKED_NO_CANDIDATES"
        if report["HAS_ANY_REAL_DATE"] == "NO":
            report["NEXT_ACTION"] = (
                "Enter REAL CSCA ISO dates via Student H5 (CSCA考试) or Admin 360 "
                "(status PLANNED/REGISTERED) — product path auto-syncs timeline; "
                "then re-run --inspect-only; do NOT invent dates; do NOT run one-shot "
                "while CANDIDATE_COUNT=0"
            )
        elif csca_n_after == 0 and csca.get("csca_status") in ("PLANNED", "REGISTERED"):
            report["NEXT_ACTION"] = (
                "Real dates present but no CSCA StudentTimelineItem — run "
                "CONFIRM_CSCA_TIMELINE_SYNC=YES --sync-timeline then --inspect-only; "
                "do NOT SQL-insert; do NOT run one-shot"
            )
        else:
            report["NEXT_ACTION"] = (
                "Real dates/timeline present but reminder window has 0 candidates "
                "(deadlines outside T-1..T+31). Use only real published dates or wait "
                "until within reminder ladder; do NOT run one-shot"
            )

    print(f"BUSINESS_WRITE={'YES' if wrote else 'NO'}")
    print("SCHEDULER_ONESHOT=NOT_RUN")
    emit()
finally:
    db.close()

PY
