"""Data baseline regression: university 125 vs catalog 122, timeline templates vs expanded schedules."""
import os
import sys

from cryptography.fernet import Fernet

os.environ.setdefault("JWT_SECRET_KEY", "test-jwt-key-data-baseline")
os.environ.setdefault("VAULT_FERNET_KEY", Fernet.generate_key().decode())
os.environ.setdefault("DATABASE_URL", "sqlite:///./test_data_baseline.db")
os.environ.setdefault("ENV", "development")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from fastapi.testclient import TestClient

from app.services.data_baseline import (
    EXPECTED_CATALOG_UNIQUE_COUNT,
    EXPECTED_FREE_UNIVERSITY_COUNT,
    EXPECTED_SEEDED_UNIVERSITY_COUNT,
    EXPECTED_TIMELINE_TEMPLATE_COUNT,
    FREE_UNIVERSITY_NAMES,
    catalog_metrics,
    db_schedule_metrics,
    db_university_metrics,
    expected_seeded_schedule_count,
    resolve_targets,
    resolve_university,
    timeline_template_metrics,
)
from app.services.student_profile import empty_profile, empty_target, merge_section
from app.services.university_catalog import DEFAULT_SCHEDULES, FIELD_SCHEDULES, UNIVERSITIES
from app.services.eligibility_engine import (
    InternationalStudentInput,
    OverseasChineseStudentInput,
    evaluate_international_student,
    evaluate_overseas_chinese_student,
)


@pytest.fixture(scope="module")
def client():
    from app.config import get_settings
    get_settings.cache_clear()
    from app.database import Base, engine
    from app import models  # noqa: F401
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    from app.main import app
    with TestClient(app) as c:
        yield c
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="module")
def auth_headers(client):
    import uuid
    from datetime import datetime, timedelta
    email = f"baseline-{uuid.uuid4().hex[:10]}@example.com"
    client.post(
        "/api/auth/register",
        json={"tenant_name": "基线测试", "email": email, "password": "pass1234", "name": "顾问"},
    )
    r = client.post("/api/auth/login", json={"email": email, "password": "pass1234"})
    if r.status_code != 200:
        email = "demo@example.com"
        r = client.post("/api/auth/login", json={"email": email, "password": "demo123456"})
    assert r.status_code == 200, r.text
    token = r.json()["token"]
    from app.database import SessionLocal
    from app.models import User
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        assert user is not None
        user.plan_code = "pro_yearly"
        user.membership_until = datetime.utcnow() + timedelta(days=365)
        user.student_profile_limit_override = 50
        db.add(user)
        db.commit()
    finally:
        db.close()
    return {"Authorization": f"Bearer {token}"}


class TestUniversityBaseline:
    def test_catalog_expected_count(self):
        assert len(UNIVERSITIES) == EXPECTED_CATALOG_UNIQUE_COUNT == 122

    def test_catalog_unique_name_count(self):
        assert len({u["name"] for u in UNIVERSITIES}) == 122
        m = catalog_metrics()
        assert m["unique_name_count"] == 122
        assert m["source_raw_count"] == 122
        assert m["free_university_count"] == EXPECTED_FREE_UNIVERSITY_COUNT
        assert m["seeded_expected_count"] == EXPECTED_SEEDED_UNIVERSITY_COUNT
        assert set(m["missing_vs_historical_baseline_if_catalog_only"]) == set(FREE_UNIVERSITY_NAMES)

    def test_seeded_db_count_is_historical_125(self, client):
        from app.database import SessionLocal
        db = SessionLocal()
        try:
            metrics = db_university_metrics(db)
            assert metrics["db_count"] == EXPECTED_SEEDED_UNIVERSITY_COUNT
            assert metrics["db_unique_name_count"] == 125
            for name in FREE_UNIVERSITY_NAMES:
                assert name in metrics["names"]
            for u in UNIVERSITIES:
                assert u["name"] in metrics["names"]
        finally:
            db.close()

    def test_target_university_resolves_catalog_id(self, client):
        from app.database import SessionLocal
        db = SessionLocal()
        try:
            for name in ("北京大学", "清华大学", "浙江大学", "深圳大学"):
                uni = resolve_university(db, name)
                assert uni is not None, name
                assert uni.name == name
                assert uni.id is not None
            result = resolve_targets(
                db,
                [
                    {"university_name": "北京大学", "major": "计算机"},
                    {"university_name": "不存在的大学XYZ", "major": "x"},
                ],
            )
            assert len(result["resolved"]) == 1
            assert result["resolved"][0]["university_id"]
            assert result["resolved"][0]["university_name"] == "北京大学"
            assert len(result["unresolved"]) == 1
        finally:
            db.close()

    def test_api_paid_and_free_counts(self, client, auth_headers):
        # Paid entitlement: full seeded library (125)
        r = client.get("/api/universities?target=international", headers=auth_headers)
        assert r.status_code == 200
        rows = r.json()
        assert len(rows) == EXPECTED_SEEDED_UNIVERSITY_COUNT
        names = {u["name"] for u in rows}
        assert {"北京大学", "清华大学", "浙江大学", *FREE_UNIVERSITY_NAMES}.issubset(names)
        # Anonymous/free entitlement: only non-core free schools (3), not a catalog shrink
        free = client.get("/api/universities?target=international")
        assert free.status_code == 200
        assert len(free.json()) == EXPECTED_FREE_UNIVERSITY_COUNT


class TestTimelineBaseline:
    def test_timeline_template_count(self):
        m = timeline_template_metrics()
        assert m["default_template_count"] == 7
        assert m["field_template_count"] == 4
        assert m["timeline_template_count"] == EXPECTED_TIMELINE_TEMPLATE_COUNT == 11
        assert len(DEFAULT_SCHEDULES) == 7
        assert sum(len(v) for v in FIELD_SCHEDULES.values()) == 4

    def test_admission_schedule_count_after_seed(self, client):
        from app.database import SessionLocal
        db = SessionLocal()
        try:
            expected = expected_seeded_schedule_count()
            assert expected == 900
            metrics = db_schedule_metrics(db)
            assert metrics["admission_schedule_count"] == expected
            assert metrics["generated_timeline_node_count"] == expected
            assert metrics["university_timeline_coverage"] == EXPECTED_SEEDED_UNIVERSITY_COUNT
        finally:
            db.close()

    def test_313_is_not_template_or_current_expanded(self):
        m = timeline_template_metrics()
        assert m["timeline_template_count"] != 313
        assert m["expected_admission_schedule_count_after_seed"] != 313
        assert "stale" in m["historical_313_meaning"].lower() or "313" in m["historical_313_meaning"]


class TestPersonalizedTimelineTraceability:
    def _profile(self):
        profile = empty_profile()
        profile = merge_section(
            profile,
            "basic_info",
            {"chinese_name": "基线生", "intended_entry_year": "2027", "basic_info_notes": "n"},
        )
        profile = merge_section(
            profile,
            "goals",
            {
                "targets": [
                    empty_target(university_name="北京大学", major="计算机", priority_level="reach", entry_year="2027"),
                    empty_target(university_name="清华大学", major="电子", priority_level="target", entry_year="2027"),
                    empty_target(university_name="浙江大学", major="软件", priority_level="safety", entry_year="2027"),
                ],
                "goals_notes": "g",
            },
        )
        return profile

    def test_auto_nodes_source_traceable(self, client, auth_headers):
        created = client.post("/api/students", json={"wizard": True, "profile": self._profile()}, headers=auth_headers)
        assert created.status_code == 200, created.text
        sid = created.json()["id"]
        regen = client.post(f"/api/students/{sid}/timeline/regenerate", headers=auth_headers)
        assert regen.status_code == 200, regen.text
        body = regen.json()
        items = body["items"]
        assert items, "expected personalized nodes from public schedules"
        auto = [i for i in items if not i.get("is_manual")]
        assert auto
        for it in auto:
            assert it["source_timeline_id"] is not None, it
            assert it.get("source_traceable") is True
            assert it["university_name"] in {"北京大学", "清华大学", "浙江大学"}
            # university_name must match catalog/DB canonical name
            assert it["university_id"] is not None

    def test_pku_tsinghua_zju_generation(self, client, auth_headers):
        created = client.post("/api/students", json={"wizard": True, "profile": self._profile()}, headers=auth_headers)
        sid = created.json()["id"]
        regen = client.post(f"/api/students/{sid}/timeline/regenerate", headers=auth_headers)
        items = regen.json()["items"]
        by_uni = {}
        for it in items:
            if it.get("is_manual"):
                continue
            by_uni.setdefault(it["university_name"], []).append(it)
        for name in ("北京大学", "清华大学", "浙江大学"):
            assert name in by_uni, f"{name} timeline missing"
            assert all(i["source_timeline_id"] for i in by_uni[name])
            # name consistency with DB
            from app.database import SessionLocal
            from app.models import University, AdmissionSchedule
            db = SessionLocal()
            try:
                uni = db.query(University).filter(University.name == name).one()
                for i in by_uni[name]:
                    assert i["university_id"] == uni.id
                    assert i["university_name"] == uni.name
                    src = db.query(AdmissionSchedule).filter(AdmissionSchedule.id == i["source_timeline_id"]).one()
                    assert src.university_id == uni.id
            finally:
                db.close()

    def test_manual_item_no_source_required(self, client, auth_headers):
        created = client.post("/api/students", json={"wizard": True, "profile": self._profile()}, headers=auth_headers)
        sid = created.json()["id"]
        manual = client.post(
            f"/api/students/{sid}/timeline/manual",
            json={"title": "IELTS 考试", "deadline": "2026-09-15", "student_note": "已约考"},
            headers=auth_headers,
        )
        assert manual.status_code == 200
        body = manual.json()
        assert body["is_manual"] is True
        assert body["source_timeline_id"] is None
        assert body["source_traceable"] is True  # manual exempt
        # regenerate keeps manual
        client.post(f"/api/students/{sid}/timeline/regenerate", headers=auth_headers)
        items = client.get(f"/api/students/{sid}/timeline", headers=auth_headers).json()["items"]
        manuals = [i for i in items if i["id"] == body["id"]]
        assert manuals
        assert manuals[0]["student_note"] == "已约考"
        assert manuals[0]["is_manual"] is True


class TestEligibilityEnginesUnchanged:
    def test_international_engine(self):
        result = evaluate_international_student(
            InternationalStudentInput(
                current_nationality="美国",
                has_foreign_nationality=True,
                has_chinese_nationality=False,
            )
        )
        assert result.result.value in {
            "PRELIMINARY_ELIGIBLE",
            "MANUAL_REVIEW_REQUIRED",
            "PRELIMINARY_INELIGIBLE",
        }

    def test_huaqiao_engine(self):
        result = evaluate_overseas_chinese_student(
            OverseasChineseStudentInput(has_chinese_nationality=True, has_foreign_nationality=False)
        )
        assert result.result.value in {
            "PRELIMINARY_ELIGIBLE",
            "MANUAL_REVIEW_REQUIRED",
            "PRELIMINARY_INELIGIBLE",
        }
