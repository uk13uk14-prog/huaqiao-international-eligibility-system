"""
R4.2 SEAL — Free/SaaS Parity Tests
验证免费版和SaaS版使用相同输入得到相同资格结果
"""
import sys
import pytest
from datetime import date, timedelta

# Import from free backend
sys.path.insert(0, '/workspace/projects/huaqiao-international-eligibility-system/backend')
from app.services.eligibility_engine import (
    ResultType,
    evaluate_international_student, evaluate_overseas_chinese_student,
    InternationalStudentInput, OverseasChineseStudentInput
)

# Import from SaaS backend (same code, different location)
sys.path.insert(0, '/workspace/projects/huaqiao-international-eligibility-system/huaqiao-saas-pro/backend')
from app.services.eligibility_engine import (
    ResultType,
    evaluate_international_student as saas_evaluate_international,
    evaluate_overseas_chinese_student as saas_evaluate_overseas,
    InternationalStudentInput as SaaSInternationalStudentInput,
    OverseasChineseStudentInput as SaaSOverseasChineseStudentInput,
)


class TestFreeSaaSParity:
    """验证免费版和SaaS版对相同输入得到相同结果"""

    def test_parity_oc_539_days(self):
        """华侨生 539天 → 两边结果相同"""
        free_input = OverseasChineseStudentInput(
            has_permanent_residence=True,
            applicant_residence_days_2_consecutive_years=539,
            applicant_residence_days_pre_2_years=540,
            parent_residence_days_2_consecutive_years=540,
        )
        saas_input = SaaSOverseasChineseStudentInput(
            has_permanent_residence=True,
            applicant_residence_days_2_consecutive_years=539,
            applicant_residence_days_pre_2_years=540,
            parent_residence_days_2_consecutive_years=540,
        )
        free_result = evaluate_overseas_chinese_student(free_input)
        saas_result = saas_evaluate_overseas(saas_input)
        assert free_result.result == saas_result.result
        assert free_result.matched_rules == saas_result.matched_rules
        assert free_result.failed_rules == saas_result.failed_rules
        assert free_result.manual_review_rules == saas_result.manual_review_rules

    def test_parity_oc_540_days(self):
        """华侨生 540天 → 两边结果相同"""
        free_input = OverseasChineseStudentInput(
            has_permanent_residence=True,
            applicant_residence_days_2_consecutive_years=540,
            applicant_residence_days_pre_2_years=540,
            parent_residence_days_2_consecutive_years=540,
        )
        saas_input = SaaSOverseasChineseStudentInput(
            has_permanent_residence=True,
            applicant_residence_days_2_consecutive_years=540,
            applicant_residence_days_pre_2_years=540,
            parent_residence_days_2_consecutive_years=540,
        )
        free_result = evaluate_overseas_chinese_student(free_input)
        saas_result = saas_evaluate_overseas(saas_input)
        assert free_result.result == saas_result.result
        assert free_result.matched_rules == saas_result.matched_rules

    def test_parity_oc_541_days(self):
        """华侨生 541天 → 两边结果相同"""
        free_input = OverseasChineseStudentInput(
            has_permanent_residence=True,
            applicant_residence_days_2_consecutive_years=541,
            applicant_residence_days_pre_2_years=541,
            parent_residence_days_2_consecutive_years=541,
        )
        saas_input = SaaSOverseasChineseStudentInput(
            has_permanent_residence=True,
            applicant_residence_days_2_consecutive_years=541,
            applicant_residence_days_pre_2_years=541,
            parent_residence_days_2_consecutive_years=541,
        )
        free_result = evaluate_overseas_chinese_student(free_input)
        saas_result = saas_evaluate_overseas(saas_input)
        assert free_result.result == saas_result.result

    def test_parity_oc_dual_window_conflict(self):
        """华侨生双窗口冲突 → 两边结果相同"""
        free_input = OverseasChineseStudentInput(
            has_permanent_residence=True,
            applicant_residence_days_2_consecutive_years=540,
            applicant_residence_days_pre_2_years=539,
            parent_residence_days_2_consecutive_years=540,
        )
        saas_input = SaaSOverseasChineseStudentInput(
            has_permanent_residence=True,
            applicant_residence_days_2_consecutive_years=540,
            applicant_residence_days_pre_2_years=539,
            parent_residence_days_2_consecutive_years=540,
        )
        free_result = evaluate_overseas_chinese_student(free_input)
        saas_result = saas_evaluate_overseas(saas_input)
        assert free_result.result == saas_result.result
        assert free_result.failed_rules == saas_result.failed_rules

    def test_parity_oc_parent_fail(self):
        """华侨生父母不满足 → 两边结果相同"""
        free_input = OverseasChineseStudentInput(
            has_permanent_residence=True,
            applicant_residence_days_2_consecutive_years=540,
            applicant_residence_days_pre_2_years=540,
            parent_residence_days_2_consecutive_years=539,
        )
        saas_input = SaaSOverseasChineseStudentInput(
            has_permanent_residence=True,
            applicant_residence_days_2_consecutive_years=540,
            applicant_residence_days_pre_2_years=540,
            parent_residence_days_2_consecutive_years=539,
        )
        free_result = evaluate_overseas_chinese_student(free_input)
        saas_result = saas_evaluate_overseas(saas_input)
        assert free_result.result == saas_result.result
        assert free_result.failed_rules == saas_result.failed_rules

    def test_parity_oc_mainland_hukou(self):
        """华侨生有内地户籍 → 两边都 MANUAL_REVIEW"""
        free_input = OverseasChineseStudentInput(
            has_permanent_residence=True,
            applicant_residence_days_2_consecutive_years=540,
            applicant_residence_days_pre_2_years=540,
            parent_residence_days_2_consecutive_years=540,
            has_mainland_hukou=True,
        )
        saas_input = SaaSOverseasChineseStudentInput(
            has_permanent_residence=True,
            applicant_residence_days_2_consecutive_years=540,
            applicant_residence_days_pre_2_years=540,
            parent_residence_days_2_consecutive_years=540,
            has_mainland_hukou=True,
        )
        free_result = evaluate_overseas_chinese_student(free_input)
        saas_result = saas_evaluate_overseas(saas_input)
        assert free_result.result == saas_result.result == ResultType.MANUAL_REVIEW_REQUIRED
        assert "MR-002" in [r.rule_id for r in free_result.manual_review_rules]
        assert "MR-002" in [r.rule_id for r in saas_result.manual_review_rules]

    def test_parity_int_passport_under_4y(self):
        """国际生护照不足4年 → 两边结果相同"""
        free_input = InternationalStudentInput(
            current_nationality="USA",
            has_foreign_nationality=True,
            foreign_passport_issue_date=date.today() - timedelta(days=3*365+180),
        )
        saas_input = SaaSInternationalStudentInput(
            current_nationality="USA",
            has_foreign_nationality=True,
            foreign_passport_issue_date=date.today() - timedelta(days=3*365+180),
        )
        free_result = evaluate_international_student(free_input)
        saas_result = saas_evaluate_international(saas_input)
        assert free_result.result == saas_result.result
        assert free_result.failed_rules == saas_result.failed_rules

    def test_parity_int_passport_exactly_4y(self):
        """国际生护照正好4年 → 两边结果相同"""
        free_input = InternationalStudentInput(
            current_nationality="USA",
            has_foreign_nationality=True,
            foreign_passport_issue_date=date(2022, 4, 30),
        )
        saas_input = SaaSInternationalStudentInput(
            current_nationality="USA",
            has_foreign_nationality=True,
            foreign_passport_issue_date=date(2022, 4, 30),
        )
        free_result = evaluate_international_student(free_input)
        saas_result = saas_evaluate_international(saas_input)
        assert free_result.result == saas_result.result
        assert free_result.matched_rules == saas_result.matched_rules

    def test_parity_int_mr003(self):
        """国际生只有days无法判断month → 两边结果相同"""
        free_input = InternationalStudentInput(
            current_nationality="USA",
            has_foreign_nationality=True,
            foreign_passport_issue_date=date(2020, 1, 1),
            total_days_abroad_last_4_years=730,
        )
        saas_input = SaaSInternationalStudentInput(
            current_nationality="USA",
            has_foreign_nationality=True,
            foreign_passport_issue_date=date(2020, 1, 1),
            total_days_abroad_last_4_years=730,
        )
        free_result = evaluate_international_student(free_input)
        saas_result = saas_evaluate_international(saas_input)
        assert free_result.result == saas_result.result
        # Both should have MR-003 in manual review
        free_mr = [r.rule_id for r in free_result.manual_review_rules]
        saas_mr = [r.rule_id for r in saas_result.manual_review_rules]
        assert "MR-003" in free_mr
        assert "MR-003" in saas_mr

    def test_parity_int_mr001(self):
        """国际生 parent_settled_abroad 不确定 → 两边结果相同"""
        free_input = InternationalStudentInput(
            current_nationality="USA",
            has_foreign_nationality=True,
            born_abroad=True,
            parent_chinese_citizen=True,
            parent_settled_abroad=None,
            foreign_passport_issue_date=date(2020, 1, 1),
        )
        saas_input = SaaSInternationalStudentInput(
            current_nationality="USA",
            has_foreign_nationality=True,
            born_abroad=True,
            parent_chinese_citizen=True,
            parent_settled_abroad=None,
            foreign_passport_issue_date=date(2020, 1, 1),
        )
        free_result = evaluate_international_student(free_input)
        saas_result = saas_evaluate_international(saas_input)
        assert free_result.result == saas_result.result
        # Both should have MR-001 in manual review
        free_mr = [r.rule_id for r in free_result.manual_review_rules]
        saas_mr = [r.rule_id for r in saas_result.manual_review_rules]
        assert "MR-001" in free_mr
        assert "MR-001" in saas_mr
