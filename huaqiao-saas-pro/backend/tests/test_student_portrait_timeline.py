"""Student Portrait + Personalized Timeline tests."""
import os
import sys
from datetime import date, timedelta

from cryptography.fernet import Fernet

os.environ.setdefault("JWT_SECRET_KEY", "test-jwt-key-portrait-timeline")
os.environ.setdefault("VAULT_FERNET_KEY", Fernet.generate_key().decode())
os.environ.setdefault("DATABASE_URL", "sqlite:///./test_portrait_timeline.db")
os.environ.setdefault("ENV", "development")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from fastapi.testclient import TestClient

from app.services.student_portrait import StudentPortraitService, build_student_portrait
from app.services.student_profile import (
    apply_eligibility_result,
    empty_course,
    empty_grade,
    empty_language_exam,
    empty_profile,
    empty_target,
    merge_section,
)
from app.services.student_timeline import (
    compute_status,
    days_until,
    infer_deadline,
    match_public_schedules,
    regenerate_student_timeline,
    serialize_item,
    timeline_summary,
)
from app.services.university_catalog import UNIVERSITIES


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
    email = f"portrait-tl-{uuid.uuid4().hex[:10]}@example.com"
    client.post(
        "/api/auth/register",
        json={"tenant_name": "画像测试", "email": email, "password": "pass1234", "name": "顾问"},
    )
    r = client.post("/api/auth/login", json={"email": email, "password": "pass1234"})
    if r.status_code != 200:
        r = client.post("/api/auth/login", json={"email": "demo@example.com", "password": "demo123456"})
        email = "demo@example.com"
    assert r.status_code == 200, r.text
    from app.database import SessionLocal
    from app.models import User
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        if user:
            user.student_profile_limit_override = 50
            db.add(user)
            db.commit()
    finally:
        db.close()
    return {"Authorization": f"Bearer {r.json()['token']}"}


def _rich_profile():
    profile = empty_profile()
    profile = merge_section(
        profile,
        "basic_info",
        {
            "chinese_name": "王宁",
            "english_name": "Wang Ning",
            "birth_date": "2008-05-01",
            "current_country": "UK",
            "intended_entry_year": "2027",
            "basic_info_notes": "b",
        },
    )
    profile = merge_section(
        profile,
        "education",
        {
            "history": [
                {
                    "school_name": "Cambridge College",
                    "country": "UK",
                    "current_grade": "Y13",
                    "is_current": True,
                    "school_type": "Private School",
                }
            ],
            "education_notes": "e",
        },
    )
    math = empty_course(subject="Mathematics", qualification="A-Level")
    profile = merge_section(
        profile,
        "courses",
        {
            "curricula": ["A-Level"],
            "items": [math, empty_course(subject="Physics", qualification="A-Level")],
            "grades": [
                empty_grade(course_id=math["id"], subject="Mathematics", grade_type="Actual", grade="A"),
                empty_grade(course_id=math["id"], subject="Mathematics", grade_type="Predicted", grade="A*", is_predicted=True),
                empty_grade(subject="Physics", grade_type="Actual", grade="D"),
            ],
            "language_exams": [empty_language_exam(exam_type="HSK", overall_score="6")],
            "courses_notes": "c",
        },
    )
    profile = merge_section(
        profile,
        "goals",
        {
            "targets": [
                empty_target(university_name="清华大学", major="计算机", priority_level="reach", entry_year="2027", application_route="international"),
                empty_target(university_name="北京大学", major="软件", priority_level="target", entry_year="2027"),
                empty_target(university_name="浙江大学", major="电子", priority_level="safety", entry_year="2027"),
            ],
            "goals_notes": "g",
        },
    )
    return profile


class TestStudentPortrait:
    def test_auto_generate_from_profile(self):
        portrait = build_student_portrait(_rich_profile())
        assert portrait["basic"]["chinese_name"] == "王宁"
        assert portrait["basic"]["current_school"] == "Cambridge College"
        assert "A-Level" in portrait["academic"]["curricula"]
        assert any("Mathematics" in s for s in portrait["academic"]["academic_strengths"])
        assert any("Physics" in s for s in portrait["academic"]["academic_weaknesses"])
        assert portrait["language"]["filled_count"] >= 1
        assert portrait["targets"]["counts"]["reach"] == 1
        assert portrait["targets"]["counts"]["safety"] == 1
        assert portrait["application_readiness"]["score"] >= 0
        assert "components" in portrait["application_readiness"]
        assert portrait["portrait_version"]
        assert portrait["portrait_generated_at"]

    def test_refresh_after_grade_change(self):
        profile = _rich_profile()
        p1 = build_student_portrait(profile)
        profile = merge_section(
            profile,
            "courses",
            {
                **profile["courses"],
                "grades": profile["courses"]["grades"]
                + [empty_grade(subject="Further Mathematics", grade_type="Predicted", grade="A*", is_predicted=True)],
            },
        )
        p2 = build_student_portrait(profile)
        assert len(p2["academic"]["predicted_grades"]) >= len(p1["academic"]["predicted_grades"])

    def test_refresh_after_targets_change(self):
        profile = _rich_profile()
        p1 = build_student_portrait(profile)
        profile = merge_section(
            profile,
            "goals",
            {"targets": profile["goals"]["targets"] + [empty_target(university_name="复旦大学", priority_level="match")], "goals_notes": "x"},
        )
        p2 = build_student_portrait(profile)
        assert p2["targets"]["counts"]["match"] == p1["targets"]["counts"]["match"] + 1

    def test_unassessed_identity(self):
        portrait = build_student_portrait(empty_profile())
        assert portrait["identity"]["international"]["status"] == "NOT_ASSESSED"
        assert portrait["identity"]["huaqiao"]["status"] == "NOT_ASSESSED"
        assert "尚未完成身份判定" in portrait["identity"]["international"]["prompt"]

    def test_portrait_does_not_override_engine(self):
        profile = apply_eligibility_result(
            empty_profile(),
            "international",
            {"result": "PRELIMINARY_ELIGIBLE", "explanation": "初步符合", "policy_version": "R4.2"},
            confirm=True,
        )
        portrait = build_student_portrait(profile)
        assert portrait["identity"]["international"]["status"] == "ELIGIBLE"
        assert portrait["identity"]["international"]["engine_result"] == "PRELIMINARY_ELIGIBLE"
        # mutating portrait dict must not affect source
        portrait["identity"]["international"]["status"] = "NOT_ELIGIBLE"
        again = build_student_portrait(profile)
        assert again["identity"]["international"]["status"] == "ELIGIBLE"

    def test_risk_and_next_actions(self):
        portrait = build_student_portrait(empty_profile())
        assert any("身份尚未判定" in r for r in portrait["risk_flags"])
        assert len(portrait["next_actions"]) <= 5
        assert portrait["next_actions"]


class TestPersonalizedTimeline:
    def test_infer_deadline_and_overdue(self):
        d = infer_deadline(2020, 1)
        assert d == date(2020, 1, 31)
        assert days_until(d, today=date(2020, 2, 1)) == -1
        assert compute_status({"status": "NOT_STARTED", "deadline": d}, today=date(2020, 2, 1)) == "OVERDUE"
        assert days_until(None) is None

    def test_no_fake_countdown_without_deadline(self):
        item = serialize_item(
            type("R", (), {
                "id": 1, "student_id": 1, "source_timeline_id": None, "title": "x", "description": "",
                "start_date": None, "deadline": None, "university_id": None, "university_name": "",
                "entry_year": 2027, "application_route": "", "status": "NOT_STARTED", "completed_at": None,
                "student_note": "", "is_manual": True, "needs_confirmation": True, "created_at": None, "updated_at": None,
            })()
        )
        assert item["has_precise_deadline"] is False
        assert item["days_until_deadline"] is None

    def test_api_generate_preserve_completed_note_manual(self, client, auth_headers):
        created = client.post("/api/students", json={"wizard": True, "profile": _rich_profile()}, headers=auth_headers)
        assert created.status_code == 200, created.text
        sid = created.json()["id"]

        # seed public universities/schedules via seed_data already ran on startup; ensure regenerate works
        regen = client.post(f"/api/students/{sid}/timeline/regenerate", headers=auth_headers)
        assert regen.status_code == 200, regen.text
        items = regen.json()["items"]
        assert isinstance(items, list)

        # create manual item
        manual = client.post(
            f"/api/students/{sid}/timeline/manual",
            json={"title": "参加 IELTS", "deadline": (date.today() + timedelta(days=10)).isoformat(), "student_note": "已约考"},
            headers=auth_headers,
        )
        assert manual.status_code == 200, manual.text
        mid = manual.json()["id"]

        # mark one derived or manual completed
        if items:
            first = items[0]
            patched = client.patch(
                f"/api/students/{sid}/timeline/{first['id']}",
                json={"status": "COMPLETED", "student_note": "已完成材料"},
                headers=auth_headers,
            )
            assert patched.status_code == 200
            completed_id = first["id"]
            note = "已完成材料"
        else:
            patched = client.patch(
                f"/api/students/{sid}/timeline/{mid}",
                json={"status": "COMPLETED", "student_note": "手工已完成"},
                headers=auth_headers,
            )
            assert patched.status_code == 200
            completed_id = mid
            note = "手工已完成"

        # change targets and regenerate
        client.patch(
            f"/api/students/{sid}/sections/goals",
            json={
                "data": {
                    "targets": [
                        empty_target(university_name="清华大学", major="计算机", priority_level="reach", entry_year="2027"),
                        empty_target(university_name="复旦大学", major="软件", priority_level="target", entry_year="2027"),
                        empty_target(university_name="浙江大学", major="电子", priority_level="safety", entry_year="2027"),
                    ],
                    "goals_notes": "updated",
                }
            },
            headers=auth_headers,
        )
        regen2 = client.post(f"/api/students/{sid}/timeline/regenerate", headers=auth_headers)
        assert regen2.status_code == 200
        items2 = {i["id"]: i for i in regen2.json()["items"]}
        assert mid in items2
        assert items2[mid]["is_manual"] is True
        assert items2[mid]["title"] == "参加 IELTS"
        assert completed_id in items2
        assert items2[completed_id]["status"] == "COMPLETED"
        assert note in (items2[completed_id]["student_note"] or "")

        # overdue detection on past deadline manual
        past = client.post(
            f"/api/students/{sid}/timeline/manual",
            json={"title": "过期事项", "deadline": (date.today() - timedelta(days=3)).isoformat()},
            headers=auth_headers,
        )
        assert past.status_code == 200
        assert past.json()["status"] == "OVERDUE"
        assert past.json()["has_precise_deadline"] is True

        portrait = client.get(f"/api/students/{sid}/portrait", headers=auth_headers)
        assert portrait.status_code == 200
        body = portrait.json()["portrait"]
        assert "timeline_summary" in body
        assert body["identity"]["international"]["status"] in {
            "NOT_ASSESSED", "IN_PROGRESS", "ELIGIBLE", "LIKELY_ELIGIBLE", "NOT_ELIGIBLE", "NEED_MORE_INFO"
        }

    def test_source_timeline_not_modified(self, client, auth_headers):
        from app.database import SessionLocal
        from app.models import AdmissionSchedule
        db = SessionLocal()
        try:
            before = db.query(AdmissionSchedule).count()
        finally:
            db.close()
        created = client.post("/api/students", json={"wizard": True, "profile": _rich_profile()}, headers=auth_headers)
        sid = created.json()["id"]
        client.post(f"/api/students/{sid}/timeline/regenerate", headers=auth_headers)
        db = SessionLocal()
        try:
            after = db.query(AdmissionSchedule).count()
        finally:
            db.close()
        assert before == after

    def test_university_count_unchanged(self):
        from app.services.data_baseline import (
            EXPECTED_CATALOG_UNIQUE_COUNT,
            EXPECTED_SEEDED_UNIVERSITY_COUNT,
            FREE_UNIVERSITY_NAMES,
            catalog_metrics,
        )
        # Catalog layer (source lists) remains 122; historical 125 is seeded DB.
        assert len(UNIVERSITIES) == EXPECTED_CATALOG_UNIQUE_COUNT
        assert len({u["name"] for u in UNIVERSITIES}) == EXPECTED_CATALOG_UNIQUE_COUNT
        m = catalog_metrics()
        assert m["seeded_expected_count"] == EXPECTED_SEEDED_UNIVERSITY_COUNT
        assert set(FREE_UNIVERSITY_NAMES) == {"深圳大学", "南方科技大学", "首都师范大学"}

    def test_public_schedule_templates_unchanged(self):
        from app.services.university_catalog import DEFAULT_SCHEDULES, FIELD_SCHEDULES
        from app.services.data_baseline import EXPECTED_TIMELINE_TEMPLATE_COUNT, expected_seeded_schedule_count
        assert len(DEFAULT_SCHEDULES) == 7
        assert set(FIELD_SCHEDULES.keys()) == {"体育", "音乐", "美术", "设计"}
        assert len(DEFAULT_SCHEDULES) + sum(len(v) for v in FIELD_SCHEDULES.values()) == EXPECTED_TIMELINE_TEMPLATE_COUNT
        assert expected_seeded_schedule_count() == 900
