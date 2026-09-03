"""Student Master Profile v2 tests — schema, legacy compat, section save, writeback.

Does not modify eligibility engine rules.
"""
import os
import sys

from cryptography.fernet import Fernet

os.environ.setdefault("JWT_SECRET_KEY", "test-jwt-key-student-profile-v2")
os.environ.setdefault("VAULT_FERNET_KEY", Fernet.generate_key().decode())
os.environ.setdefault("DATABASE_URL", "sqlite:///./test_student_profile_v2.db")
os.environ.setdefault("ENV", "development")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from fastapi.testclient import TestClient

from app.services.eligibility_engine import (
    InternationalStudentInput,
    OverseasChineseStudentInput,
    evaluate_international_student,
    evaluate_overseas_chinese_student,
)
from app.services.student_profile import (
    apply_eligibility_result,
    completeness,
    empty_course,
    empty_grade,
    empty_language_exam,
    empty_profile,
    empty_target,
    merge_section,
    migrate_legacy_vault,
    normalize_profile,
    project_legacy_vault,
)
from app.services.university_catalog import DEFAULT_SCHEDULES, FIELD_SCHEDULES, UNIVERSITIES


@pytest.fixture(scope="module")
def client():
    from app.config import get_settings
    get_settings.cache_clear()
    from app.database import Base, engine
    from app import models  # noqa: F401
    Base.metadata.create_all(bind=engine)
    from app.main import app
    with TestClient(app) as c:
        yield c
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def auth_headers(client):
    import uuid
    email = f"profile-v2-{uuid.uuid4().hex[:10]}@example.com"
    client.post(
        "/api/auth/register",
        json={"tenant_name": "档案测试机构", "email": email, "password": "pass1234", "name": "顾问"},
    )
    r = client.post("/api/auth/login", json={"email": email, "password": "pass1234"})
    if r.status_code != 200:
        email = "demo@example.com"
        r = client.post("/api/auth/login", json={"email": email, "password": "demo123456"})
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
    token = r.json()["token"]
    return {"Authorization": f"Bearer {token}"}


class TestLegacyMigration:
    def test_old_vault_opens_without_error(self):
        old = {
            "family_note": "父母在英国定居",
            "child_identity": "英国护照",
            "residence_note": "近四年在伦敦",
            "goal_note": "冲刺清北",
            "intended_major": "计算机",
            "target_schools": "清华大学\n北京大学",
            "school": "Westminster School",
            "subjects": "Mathematics, Physics",
            "predicted_grade": "A*",
            "target_university": "清华大学",
            "target_major": "计算机",
            "nationality": "英国",
            "notes": "旧总备注",
        }
        profile = migrate_legacy_vault(old)
        assert profile["schema_version"] == 2
        assert profile["education"]["current_school"]["school_name"] == "Westminster School"
        assert len(profile["goals"]["targets"]) >= 2
        assert profile["goals"]["targets"][0]["university_name"] == "清华大学"
        assert profile["goals"]["targets"][1]["university_name"] == "北京大学"
        assert any(c["subject"] == "Mathematics" for c in profile["courses"]["items"])
        assert any(g["grade"] == "A*" and g["is_predicted"] for g in profile["courses"]["grades"])
        assert profile["legacy"]["target_schools"] == "清华大学\n北京大学"
        assert profile["basic_info"]["basic_info_notes"] == "父母在英国定居"
        assert profile["summary"]["summary_notes"] == "旧总备注"
        projected = project_legacy_vault(profile)
        assert projected["school"] == "Westminster School"
        assert "清华大学" in projected["target_schools"]

    def test_empty_legacy_does_not_crash(self):
        profile = migrate_legacy_vault({})
        assert profile["identity"]["international"]["status"] == "NOT_ASSESSED"
        assert profile["identity"]["huaqiao"]["status"] == "NOT_ASSESSED"


class TestEducationAndCourses:
    def test_multiple_education_history_not_overwritten(self):
        profile = empty_profile()
        history = [
            {"school_name": "School A", "country": "UK", "is_current": False, "start_date": "2020-09"},
            {"school_name": "School B", "country": "UK", "is_current": False, "start_date": "2022-09"},
            {"school_name": "School C", "country": "UK", "is_current": True, "start_date": "2024-09"},
        ]
        profile = merge_section(profile, "education", {"history": history, "education_notes": "教育备注A"})
        assert len(profile["education"]["history"]) == 3
        names = [x["school_name"] for x in profile["education"]["history"]]
        assert names == ["School A", "School B", "School C"]
        assert profile["education"]["current_school"]["school_name"] == "School C"
        profile = merge_section(
            profile,
            "education",
            {"history": profile["education"]["history"] + [{"school_name": "School D", "is_current": False}], "education_notes": "教育备注B"},
        )
        assert len(profile["education"]["history"]) == 4
        assert profile["education"]["education_notes"] == "教育备注B"

    def test_curriculum_and_custom(self):
        profile = merge_section(
            empty_profile(),
            "courses",
            {"curricula": ["A-Level", "Custom"], "custom_curriculum": "Pre-U", "courses_notes": "课备注"},
        )
        assert "A-Level" in profile["courses"]["curricula"]
        assert profile["courses"]["custom_curriculum"] == "Pre-U"

    def test_multiple_courses_and_multi_year_grades(self):
        math = empty_course(subject="Mathematics", qualification="A-Level", level="AS", exam_board="CCEA", start_year="2025", end_year="2027")
        fm = empty_course(subject="Further Mathematics", qualification="A-Level")
        phy = empty_course(subject="Physics", qualification="A-Level")
        g1 = empty_grade(course_id=math["id"], subject="Mathematics", exam_session="AS", grade_type="Actual", grade="A", is_predicted=False)
        g2 = empty_grade(course_id=math["id"], subject="Mathematics", exam_session="A2", grade_type="Predicted", grade="A*", is_predicted=True)
        profile = merge_section(
            empty_profile(),
            "courses",
            {"curricula": ["A-Level"], "items": [math, fm, phy], "grades": [g1, g2], "courses_notes": "成绩备注"},
        )
        math_grades = [g for g in profile["courses"]["grades"] if g["subject"] == "Mathematics"]
        assert len(profile["courses"]["items"]) == 3
        assert len(math_grades) == 2
        types = {g["grade_type"] for g in math_grades}
        assert types == {"Actual", "Predicted"}

    def test_language_exam_hsk6(self):
        exam = empty_language_exam(exam_type="HSK", overall_score="6", exam_date="2025-06-01")
        profile = merge_section(empty_profile(), "courses", {"language_exams": [exam]})
        assert profile["courses"]["language_exams"][0]["exam_type"] == "HSK"
        assert profile["courses"]["language_exams"][0]["overall_score"] == "6"


class TestGoalsAndNotes:
    def test_five_targets_priority_and_no_overwrite(self):
        profile = empty_profile()
        first = [
            empty_target(university_name="清华大学", major="计算机", priority_level="reach"),
            empty_target(university_name="北京大学", major="人工智能", priority_level="target"),
        ]
        profile = merge_section(profile, "goals", {"targets": first, "goals_notes": "目标备注1"})
        more = profile["goals"]["targets"] + [
            empty_target(university_name="复旦大学", major="软件工程", priority_level="match"),
            empty_target(university_name="浙江大学", major="计算机", priority_level="safety"),
            empty_target(university_name="清华大学", major="电子信息", priority_level="target"),
        ]
        profile = merge_section(profile, "goals", {"targets": more, "goals_notes": "目标备注2"})
        names = [(t["university_name"], t["major"], t["priority_level"]) for t in profile["goals"]["targets"]]
        assert len(names) == 5
        assert ("清华大学", "计算机", "reach") in names
        assert ("清华大学", "电子信息", "target") in names
        assert profile["goals"]["goals_notes"] == "目标备注2"

    def test_per_section_notes_are_independent(self):
        profile = empty_profile()
        profile = merge_section(profile, "basic_info", {"chinese_name": "张三", "basic_info_notes": "基本备注"})
        profile = merge_section(profile, "education", {"education_notes": "教育备注"})
        profile = merge_section(profile, "courses", {"courses_notes": "课程备注"})
        profile = merge_section(profile, "goals", {"goals_notes": "目标备注"})
        profile = merge_section(profile, "identity", {"identity_notes": "身份备注"})
        profile = merge_section(profile, "planning", {"planning_notes": "规划备注"})
        profile = merge_section(profile, "summary", {"summary_notes": "总览备注"})
        # generic notes must not clobber
        profile = merge_section(profile, "basic_info", {"notes": "不要覆盖", "chinese_name": "张三"})
        assert profile["basic_info"]["basic_info_notes"] == "基本备注"
        assert profile["education"]["education_notes"] == "教育备注"
        assert profile["courses"]["courses_notes"] == "课程备注"
        assert profile["goals"]["goals_notes"] == "目标备注"
        assert profile["identity"]["identity_notes"] == "身份备注"
        assert profile["planning"]["planning_notes"] == "规划备注"
        assert profile["summary"]["summary_notes"] == "总览备注"


class TestIdentityWriteback:
    def test_unassessed_default_and_engine_writeback(self):
        profile = empty_profile()
        assert profile["identity"]["international"]["status"] == "NOT_ASSESSED"
        assert profile["identity"]["huaqiao"]["status"] == "NOT_ASSESSED"
        profile = apply_eligibility_result(
            profile,
            "international",
            {"result": "PRELIMINARY_ELIGIBLE", "explanation": "初步符合", "record_id": 11, "policy_version": "R4.2"},
            confirm=False,
        )
        assert profile["identity"]["international"]["status"] == "LIKELY_ELIGIBLE"
        assert profile["identity"]["international"]["confirmed"] is False
        profile = apply_eligibility_result(
            profile,
            "international",
            {"result": "PRELIMINARY_ELIGIBLE", "explanation": "初步符合", "record_id": 11, "policy_version": "R4.2"},
            confirm=True,
        )
        assert profile["identity"]["international"]["confirmed"] is True
        assert profile["identity"]["international"]["status"] == "ELIGIBLE"
        assert profile["identity"]["international"]["policy_version"] == "R4.2"

    def test_toggles_are_facts_not_verdict(self):
        profile = merge_section(
            empty_profile(),
            "identity",
            {"has_foreign_nationality": True, "has_chinese_nationality": False},
        )
        assert profile["identity"]["has_foreign_nationality"] is True
        assert profile["identity"]["international"]["status"] == "NOT_ASSESSED"


class TestCompleteness:
    def test_missing_prompts(self):
        profile = empty_profile()
        c = completeness(profile)
        assert c["percent"] < 50
        assert "国际生尚未判定" in c["missing"]
        assert "华侨生尚未判定" in c["missing"]
        assert "语言成绩未填写" in c["missing"]
        assert "预测成绩缺失" in c["missing"]


class TestCatalogUnchanged:
    def test_university_catalog_size(self):
        assert len(UNIVERSITIES) >= 120

    def test_timeline_template_unchanged(self):
        assert len(DEFAULT_SCHEDULES) == 7
        assert set(FIELD_SCHEDULES.keys()) == {"体育", "音乐", "美术", "设计"}


class TestEligibilityEngineUntouched:
    def test_international_engine_still_runs(self):
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

    def test_huaqiao_engine_still_runs(self):
        result = evaluate_overseas_chinese_student(
            OverseasChineseStudentInput(has_chinese_nationality=True, has_foreign_nationality=False)
        )
        assert result.result.value in {
            "PRELIMINARY_ELIGIBLE",
            "MANUAL_REVIEW_REQUIRED",
            "PRELIMINARY_INELIGIBLE",
        }


class TestStudentApi:
    def test_create_save_reload(self, client, auth_headers):
        created = client.post("/api/students", json={"wizard": True, "profile": {}}, headers=auth_headers)
        assert created.status_code == 200, created.text
        sid = created.json()["id"]
        r = client.patch(
            f"/api/students/{sid}/sections/basic_info",
            json={"data": {"chinese_name": "李明", "english_name": "Li Ming", "birth_date": "2008-04-01", "intended_entry_year": "2027", "basic_info_notes": "基本独立备注"}},
            headers=auth_headers,
        )
        assert r.status_code == 200, r.text
        edu = {
            "history": [
                {"school_name": "Alpha College", "country": "UK", "city": "London", "school_type": "International School", "is_current": False, "start_date": "2021-09", "end_date": "2023-07"},
                {"school_name": "Beta Grammar", "country": "UK", "city": "Oxford", "school_type": "Grammar School", "is_current": False, "start_date": "2023-09", "end_date": "2024-07"},
                {"school_name": "Gamma High", "country": "UK", "city": "Cambridge", "school_type": "Private School", "is_current": True, "current_grade": "Y13", "start_date": "2024-09"},
            ],
            "education_notes": "教育独立备注",
        }
        r = client.patch(f"/api/students/{sid}/sections/education", json={"data": edu}, headers=auth_headers)
        assert r.status_code == 200, r.text
        math = empty_course(subject="Mathematics", qualification="A-Level", level="AS", exam_board="CCEA", start_year="2025", end_year="2027")
        courses = {
            "curricula": ["A-Level"],
            "items": [
                math,
                empty_course(subject="Further Mathematics", qualification="A-Level"),
                empty_course(subject="Physics", qualification="A-Level"),
            ],
            "grades": [
                empty_grade(course_id=math["id"], subject="Mathematics", exam_session="AS", grade_type="Actual", grade="A"),
                empty_grade(course_id=math["id"], subject="Mathematics", exam_session="A2", grade_type="Predicted", grade="A*", is_predicted=True),
            ],
            "language_exams": [empty_language_exam(exam_type="HSK", overall_score="6")],
            "courses_notes": "课程独立备注",
        }
        r = client.patch(f"/api/students/{sid}/sections/courses", json={"data": courses}, headers=auth_headers)
        assert r.status_code == 200, r.text
        targets = [
            empty_target(university_name="清华大学", major="计算机", priority_level="reach"),
            empty_target(university_name="北京大学", major="软件", priority_level="target"),
            empty_target(university_name="复旦大学", major="微电子", priority_level="match"),
            empty_target(university_name="浙江大学", major="计算机", priority_level="safety"),
            empty_target(university_name="上海交通大学", major="人工智能", priority_level="target"),
        ]
        r = client.patch(
            f"/api/students/{sid}/sections/goals",
            json={"data": {"targets": targets, "goals_notes": "目标独立备注"}},
            headers=auth_headers,
        )
        assert r.status_code == 200, r.text
        r = client.post(
            f"/api/students/{sid}/eligibility/writeback",
            json={"kind": "international", "result": "PRELIMINARY_ELIGIBLE", "conclusion": "初步符合", "confirm": True, "policy_version": "R4.2"},
            headers=auth_headers,
        )
        assert r.status_code == 200, r.text
        loaded = client.get(f"/api/students/{sid}", headers=auth_headers)
        assert loaded.status_code == 200
        body = loaded.json()
        profile = body["profile"]
        assert profile["basic_info"]["chinese_name"] == "李明"
        assert len(profile["education"]["history"]) == 3
        assert profile["education"]["current_school"]["school_name"] == "Gamma High"
        assert len(profile["courses"]["items"]) == 3
        assert len([g for g in profile["courses"]["grades"] if g["subject"] == "Mathematics"]) == 2
        assert profile["courses"]["language_exams"][0]["exam_type"] == "HSK"
        assert len(profile["goals"]["targets"]) == 5
        assert profile["identity"]["international"]["confirmed"] is True
        assert body["completeness"]["percent"] >= 50
        listed = client.get("/api/students", headers=auth_headers)
        assert any(s["id"] == sid for s in listed.json()["students"])

    def test_legacy_vault_migrates_on_list(self, client, auth_headers):
        vault = {
            "family_note": "旧家庭",
            "target_schools": "南京大学",
            "school": "Old School",
            "intended_major": "化学",
        }
        r = client.put("/api/vault/profile", json={"profile": vault}, headers=auth_headers)
        # unpaid demo may 402; paid after we still accept 402 or 200
        if r.status_code == 402:
            pytest.skip("vault cloud requires paid plan; migration covered by unit tests")
        listed = client.get("/api/students", headers=auth_headers)
        assert listed.status_code == 200
        students = listed.json()["students"]
        assert students
        detail = client.get(f"/api/students/{students[0]['id']}", headers=auth_headers).json()
        assert detail["profile"]["education"]["current_school"]["school_name"] == "Old School"
