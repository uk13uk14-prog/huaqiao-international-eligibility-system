"""
R4.2 Policy Boundary Tests — 40+ 边界案例

华侨生 20 Cases + 国际生 20 Cases
"""

import pytest
from datetime import date

from app.services.eligibility_engine import (
    evaluate_international_student,
    evaluate_overseas_chinese_student,
    InternationalStudentInput,
    OverseasChineseStudentInput,
    ResidenceRecord,
)
from app.services.policy_registry import ResultType


# =============================================================================
# 华侨生边界案例 (20 Cases)
# =============================================================================

class TestOverseasChineseBoundaryCases:
    """华侨生边界案例测试"""
    
    def test_oc_01_permanent_539_days(self):
        """OC-01: 永久居留路径，考生连续两年539天（差1天）"""
        input_data = OverseasChineseStudentInput(
            has_chinese_nationality=True,
            has_permanent_residence=True,
            applicant_residence_days_2_consecutive_years=539,
            applicant_residence_days_pre_2_years=540,
            parent_residence_days_2_consecutive_years=540,
        )
        result = evaluate_overseas_chinese_student(input_data)
        assert result.result == ResultType.PRELIMINARY_INELIGIBLE
        assert any(r.rule_id == "OC-002" for r in result.failed_rules)
    
    def test_oc_02_permanent_540_days_exact(self):
        """OC-02: 永久居留路径，考生连续两年正好540天"""
        input_data = OverseasChineseStudentInput(
            has_chinese_nationality=True,
            has_permanent_residence=True,
            applicant_residence_days_2_consecutive_years=540,
            applicant_residence_days_pre_2_years=540,
            parent_residence_days_2_consecutive_years=540,
        )
        result = evaluate_overseas_chinese_student(input_data)
        assert result.result == ResultType.PRELIMINARY_ELIGIBLE
    
    def test_oc_03_permanent_541_days(self):
        """OC-03: 永久居留路径，考生连续两年541天"""
        input_data = OverseasChineseStudentInput(
            has_chinese_nationality=True,
            has_permanent_residence=True,
            applicant_residence_days_2_consecutive_years=541,
            applicant_residence_days_pre_2_years=540,
            parent_residence_days_2_consecutive_years=540,
        )
        result = evaluate_overseas_chinese_student(input_data)
        assert result.result == ResultType.PRELIMINARY_ELIGIBLE
    
    def test_oc_04_window1_pass_window2_fail(self):
        """OC-04: 连续自然年满足但报名前2年不满足"""
        input_data = OverseasChineseStudentInput(
            has_chinese_nationality=True,
            has_permanent_residence=True,
            applicant_residence_days_2_consecutive_years=540,
            applicant_residence_days_pre_2_years=539,  # 不足
            parent_residence_days_2_consecutive_years=540,
        )
        result = evaluate_overseas_chinese_student(input_data)
        assert result.result == ResultType.PRELIMINARY_INELIGIBLE
    
    def test_oc_05_window1_fail_window2_pass(self):
        """OC-05: 报名前2年满足但连续自然年不满足"""
        input_data = OverseasChineseStudentInput(
            has_chinese_nationality=True,
            has_permanent_residence=True,
            applicant_residence_days_2_consecutive_years=539,  # 不足
            applicant_residence_days_pre_2_years=540,
            parent_residence_days_2_consecutive_years=540,
        )
        result = evaluate_overseas_chinese_student(input_data)
        assert result.result == ResultType.PRELIMINARY_INELIGIBLE
    
    def test_oc_06_applicant_pass_parent_fail(self):
        """OC-06: 考生满足但父母不满足"""
        input_data = OverseasChineseStudentInput(
            has_chinese_nationality=True,
            has_permanent_residence=True,
            applicant_residence_days_2_consecutive_years=540,
            applicant_residence_days_pre_2_years=540,
            parent_residence_days_2_consecutive_years=539,  # 不足
        )
        result = evaluate_overseas_chinese_student(input_data)
        assert result.result == ResultType.PRELIMINARY_INELIGIBLE
        assert any(r.rule_id == "OC-004" for r in result.failed_rules)
    
    def test_oc_07_parent_pass_applicant_fail(self):
        """OC-07: 父母满足但考生不满足"""
        input_data = OverseasChineseStudentInput(
            has_chinese_nationality=True,
            has_permanent_residence=True,
            applicant_residence_days_2_consecutive_years=539,  # 不足
            applicant_residence_days_pre_2_years=540,
            parent_residence_days_2_consecutive_years=540,
        )
        result = evaluate_overseas_chinese_student(input_data)
        assert result.result == ResultType.PRELIMINARY_INELIGIBLE
    
    def test_oc_08_permanent_path_full_pass(self):
        """OC-08: 永久居留路径全部满足"""
        input_data = OverseasChineseStudentInput(
            has_chinese_nationality=True,
            has_permanent_residence=True,
            applicant_residence_days_2_consecutive_years=600,
            applicant_residence_days_pre_2_years=600,
            parent_residence_days_2_consecutive_years=600,
        )
        result = evaluate_overseas_chinese_student(input_data)
        assert result.result == ResultType.PRELIMINARY_ELIGIBLE
    
    def test_oc_09_five_year_path_899_days(self):
        """OC-09: 5年合法居留路径，考生连续5年899天（差1天）"""
        input_data = OverseasChineseStudentInput(
            has_chinese_nationality=True,
            has_long_term_residence=True,
            applicant_residence_days_5_consecutive_years=899,
            applicant_residence_days_pre_5_years=900,
            parent_residence_days_5_consecutive_years=900,
        )
        result = evaluate_overseas_chinese_student(input_data)
        assert result.result == ResultType.PRELIMINARY_INELIGIBLE
    
    def test_oc_10_five_year_path_900_days_exact(self):
        """OC-10: 5年合法居留路径，考生连续5年正好900天"""
        input_data = OverseasChineseStudentInput(
            has_chinese_nationality=True,
            has_long_term_residence=True,
            applicant_residence_days_5_consecutive_years=900,
            applicant_residence_days_pre_5_years=900,
            parent_residence_days_5_consecutive_years=900,
        )
        result = evaluate_overseas_chinese_student(input_data)
        assert result.result == ResultType.PRELIMINARY_ELIGIBLE
    
    def test_oc_11_study_abroad_period(self):
        """OC-11: 留学期间不视为华侨"""
        input_data = OverseasChineseStudentInput(
            has_chinese_nationality=True,
            has_permanent_residence=True,
            applicant_residence_days_2_consecutive_years=540,
            applicant_residence_days_pre_2_years=540,
            parent_residence_days_2_consecutive_years=540,
            is_study_abroad_period=True,
        )
        result = evaluate_overseas_chinese_student(input_data)
        assert result.result == ResultType.PRELIMINARY_INELIGIBLE
        assert any(r.rule_id == "OC-010" for r in result.failed_rules)
    
    def test_oc_12_official_duty_period(self):
        """OC-12: 因公出国期间不视为华侨"""
        input_data = OverseasChineseStudentInput(
            has_chinese_nationality=True,
            has_permanent_residence=True,
            applicant_residence_days_2_consecutive_years=540,
            applicant_residence_days_pre_2_years=540,
            parent_residence_days_2_consecutive_years=540,
            is_official_duty_period=True,
        )
        result = evaluate_overseas_chinese_student(input_data)
        assert result.result == ResultType.PRELIMINARY_INELIGIBLE
    
    def test_oc_13_has_mainland_hukou(self):
        """OC-13: 有内地户籍 → MANUAL_REVIEW（非FAIL）"""
        input_data = OverseasChineseStudentInput(
            has_chinese_nationality=True,
            has_permanent_residence=True,
            applicant_residence_days_2_consecutive_years=540,
            applicant_residence_days_pre_2_years=540,
            parent_residence_days_2_consecutive_years=540,
            has_mainland_hukou=True,
        )
        result = evaluate_overseas_chinese_student(input_data)
        # 不是 PRELIMINARY_INELIGIBLE，而是 MANUAL_REVIEW
        assert result.result == ResultType.MANUAL_REVIEW_REQUIRED
        assert any(r.rule_id == "MR-002" for r in result.manual_review_rules)
    
    def test_oc_14_no_mainland_hukou(self):
        """OC-14: 无内地户籍 → 正常通过"""
        input_data = OverseasChineseStudentInput(
            has_chinese_nationality=True,
            has_permanent_residence=True,
            applicant_residence_days_2_consecutive_years=540,
            applicant_residence_days_pre_2_years=540,
            parent_residence_days_2_consecutive_years=540,
            has_mainland_hukou=False,
        )
        result = evaluate_overseas_chinese_student(input_data)
        assert result.result == ResultType.PRELIMINARY_ELIGIBLE
    
    def test_oc_15_parent_info_insufficient(self):
        """OC-15: 父母资料不足"""
        input_data = OverseasChineseStudentInput(
            has_chinese_nationality=True,
            has_permanent_residence=True,
            applicant_residence_days_2_consecutive_years=540,
            applicant_residence_days_pre_2_years=540,
            parent_residence_days_2_consecutive_years=0,  # 无数据
        )
        result = evaluate_overseas_chinese_student(input_data)
        assert result.result == ResultType.PRELIMINARY_INELIGIBLE
    
    def test_oc_16_no_residence_permit(self):
        """OC-16: 无居留证明"""
        input_data = OverseasChineseStudentInput(
            has_chinese_nationality=True,
            has_permanent_residence=False,
            has_long_term_residence=False,
        )
        result = evaluate_overseas_chinese_student(input_data)
        assert result.result == ResultType.MANUAL_REVIEW_REQUIRED
    
    def test_oc_17_no_chinese_nationality(self):
        """OC-17: 无中国国籍 → 不符合"""
        input_data = OverseasChineseStudentInput(
            has_chinese_nationality=False,
            has_permanent_residence=True,
        )
        result = evaluate_overseas_chinese_student(input_data)
        assert result.result == ResultType.PRELIMINARY_INELIGIBLE
    
    def test_oc_18_target_university_triggers_review(self):
        """OC-18: 指定目标大学触发 MR-004"""
        input_data = OverseasChineseStudentInput(
            has_chinese_nationality=True,
            has_permanent_residence=True,
            applicant_residence_days_2_consecutive_years=540,
            applicant_residence_days_pre_2_years=540,
            parent_residence_days_2_consecutive_years=540,
            target_university="浙江大学",
        )
        result = evaluate_overseas_chinese_student(input_data)
        assert result.result == ResultType.MANUAL_REVIEW_REQUIRED
        assert any(r.rule_id == "MR-004" for r in result.manual_review_rules)
    
    def test_oc_19_explanation_contains_disclaimer(self):
        """OC-19: 解释文案包含免责声明"""
        input_data = OverseasChineseStudentInput(
            has_chinese_nationality=True,
            has_permanent_residence=True,
            applicant_residence_days_2_consecutive_years=540,
            applicant_residence_days_pre_2_years=540,
            parent_residence_days_2_consecutive_years=540,
        )
        result = evaluate_overseas_chinese_student(input_data)
        assert "初步资格评估" in result.explanation
        assert "不替代" in result.explanation
    
    def test_oc_20_decision_to_dict(self):
        """OC-20: 判定结果可序列化为字典"""
        input_data = OverseasChineseStudentInput(
            has_chinese_nationality=True,
            has_permanent_residence=True,
            applicant_residence_days_2_consecutive_years=540,
            applicant_residence_days_pre_2_years=540,
            parent_residence_days_2_consecutive_years=540,
        )
        result = evaluate_overseas_chinese_student(input_data)
        d = result.to_dict()
        assert d["result"] == "PRELIMINARY_ELIGIBLE"
        assert d["category"] == "OVERSEAS_CHINESE"
        assert isinstance(d["matched_rules"], list)


# =============================================================================
# 国际生边界案例 (20 Cases)
# =============================================================================

class TestInternationalStudentBoundaryCases:
    """国际生边界案例测试"""
    
    def test_int_01_passport_3years_364days(self):
        """INT-01: 护照持有3年364天（差1天）"""
        input_data = InternationalStudentInput(
            current_nationality="USA",
            has_chinese_nationality=False,
            has_foreign_nationality=True,
            foreign_passport_issue_date=date(2022, 5, 1),  # 到2026年4月30日不足4年
            total_days_abroad_last_4_years=800,
            admission_year=2026,
        )
        result = evaluate_international_student(input_data)
        assert result.result == ResultType.PRELIMINARY_INELIGIBLE
        assert any(r.rule_id == "INT-001" for r in result.failed_rules)
    
    def test_int_02_passport_exactly_4years(self):
        """INT-02: 护照持有正好4年"""
        input_data = InternationalStudentInput(
            current_nationality="USA",
            has_chinese_nationality=False,
            has_foreign_nationality=True,
            foreign_passport_issue_date=date(2022, 4, 29),  # 到2026年4月30日正好4年
            total_days_abroad_last_4_years=800,
            admission_year=2026,
        )
        result = evaluate_international_student(input_data)
        # 护照满足，但居住记录需要检查
        assert any(r.rule_id == "INT-001" for r in result.matched_rules)
    
    def test_int_03_passport_over_4years(self):
        """INT-03: 护照持有超过4年"""
        input_data = InternationalStudentInput(
            current_nationality="USA",
            has_chinese_nationality=False,
            has_foreign_nationality=True,
            foreign_passport_issue_date=date(2020, 1, 1),
            total_days_abroad_last_4_years=800,
            admission_year=2026,
        )
        result = evaluate_international_student(input_data)
        assert any(r.rule_id == "INT-001" for r in result.matched_rules)
    
    def test_int_04_residence_insufficient(self):
        """INT-04: 4年居住不足2年"""
        input_data = InternationalStudentInput(
            current_nationality="USA",
            has_chinese_nationality=False,
            has_foreign_nationality=True,
            foreign_passport_issue_date=date(2020, 1, 1),
            total_days_abroad_last_4_years=700,  # 不足730天
            admission_year=2026,
        )
        result = evaluate_international_student(input_data)
        # 可能是不符合或需要人工审核（取决于是否有月份级数据）
        assert result.result in [ResultType.PRELIMINARY_INELIGIBLE, ResultType.MANUAL_REVIEW_REQUIRED]
    
    def test_int_05_residence_sufficient_with_records(self):
        """INT-05: 有出入境记录且居住满足"""
        input_data = InternationalStudentInput(
            current_nationality="USA",
            has_chinese_nationality=False,
            has_foreign_nationality=True,
            foreign_passport_issue_date=date(2020, 1, 1),
            residence_records=[
                ResidenceRecord(entry_date=date(2022, 1, 1), exit_date=date(2023, 12, 31), country="USA"),
                ResidenceRecord(entry_date=date(2024, 1, 1), exit_date=date(2025, 12, 31), country="USA"),
            ],
            total_days_abroad_last_4_years=800,
            admission_year=2026,
        )
        result = evaluate_international_student(input_data)
        assert any(r.rule_id == "INT-002" for r in result.matched_rules)
    
    def test_int_06_days_only_triggers_mr003(self):
        """INT-06: 只有天数数据无法判断'9个月' → MANUAL_REVIEW"""
        input_data = InternationalStudentInput(
            current_nationality="USA",
            has_chinese_nationality=False,
            has_foreign_nationality=True,
            foreign_passport_issue_date=date(2020, 1, 1),
            residence_records=[],  # 无出入境记录
            total_days_abroad_last_4_years=800,  # 超过730天
            admission_year=2026,
        )
        result = evaluate_international_student(input_data)
        assert result.result == ResultType.MANUAL_REVIEW_REQUIRED
        assert any(r.rule_id == "MR-003" for r in result.manual_review_rules)
    
    def test_int_07_parent_chinese_citizen_settled(self):
        """INT-07: 父母中国籍且定居国外"""
        input_data = InternationalStudentInput(
            current_nationality="USA",
            has_chinese_nationality=False,
            has_foreign_nationality=True,
            born_abroad=True,
            parent_chinese_citizen=True,
            parent_settled_abroad=True,
            foreign_passport_issue_date=date(2020, 1, 1),
            total_days_abroad_last_4_years=800,
            admission_year=2026,
        )
        result = evaluate_international_student(input_data)
        assert any(r.rule_id == "INT-004" for r in result.matched_rules)
    
    def test_int_08_parent_chinese_not_settled(self):
        """INT-08: 父母中国籍但未定居国外"""
        input_data = InternationalStudentInput(
            current_nationality="USA",
            has_chinese_nationality=False,
            has_foreign_nationality=True,
            born_abroad=True,
            parent_chinese_citizen=True,
            parent_settled_abroad=False,
            foreign_passport_issue_date=date(2020, 1, 1),
            total_days_abroad_last_4_years=800,
            admission_year=2026,
        )
        result = evaluate_international_student(input_data)
        # 国籍法第五条不适用
        assert not any(r.rule_id == "INT-004" for r in result.matched_rules)
    
    def test_int_09_parent_settled_unknown(self):
        """INT-09: 父母是否定居不确定 → MANUAL_REVIEW"""
        input_data = InternationalStudentInput(
            current_nationality="USA",
            has_chinese_nationality=False,
            has_foreign_nationality=True,
            born_abroad=True,
            parent_chinese_citizen=True,
            parent_settled_abroad=None,  # 不确定
            foreign_passport_issue_date=date(2020, 1, 1),
            total_days_abroad_last_4_years=800,
            admission_year=2026,
        )
        result = evaluate_international_student(input_data)
        assert result.result == ResultType.MANUAL_REVIEW_REQUIRED
        assert any(r.rule_id == "MR-001" for r in result.manual_review_rules)
    
    def test_int_10_born_in_china(self):
        """INT-10: 出生在中国"""
        input_data = InternationalStudentInput(
            current_nationality="USA",
            has_chinese_nationality=False,
            has_foreign_nationality=True,
            born_in_china=True,
            born_abroad=False,
            foreign_passport_issue_date=date(2020, 1, 1),
            total_days_abroad_last_4_years=800,
            admission_year=2026,
        )
        result = evaluate_international_student(input_data)
        # 出生在中国，国籍法第五条不直接适用
        assert not any(r.rule_id == "INT-004" for r in result.matched_rules)
    
    def test_int_11_has_chinese_nationality(self):
        """INT-11: 同时具有中国国籍 → 不符合"""
        input_data = InternationalStudentInput(
            current_nationality="USA",
            has_chinese_nationality=True,  # 同时有中国籍
            has_foreign_nationality=True,
            foreign_passport_issue_date=date(2020, 1, 1),
            total_days_abroad_last_4_years=800,
            admission_year=2026,
        )
        result = evaluate_international_student(input_data)
        assert result.result == ResultType.PRELIMINARY_INELIGIBLE
    
    def test_int_12_was_chinese_citizen(self):
        """INT-12: 曾经是中国籍（后取得外国籍）"""
        input_data = InternationalStudentInput(
            current_nationality="USA",
            has_chinese_nationality=False,
            has_foreign_nationality=True,
            was_chinese_citizen=True,
            naturalization_date=date(2020, 6, 1),
            foreign_passport_issue_date=date(2020, 7, 1),
            total_days_abroad_last_4_years=800,
            admission_year=2026,
        )
        result = evaluate_international_student(input_data)
        assert any("申请人曾具有中国国籍" in e for e in result.evidence)
        assert "国籍变更/退出证明文件" in result.missing_documents
    
    def test_int_13_passport_none(self):
        """INT-13: 未提供护照签发日期"""
        input_data = InternationalStudentInput(
            current_nationality="USA",
            has_chinese_nationality=False,
            has_foreign_nationality=True,
            foreign_passport_issue_date=None,
            total_days_abroad_last_4_years=800,
            admission_year=2026,
        )
        result = evaluate_international_student(input_data)
        assert result.result == ResultType.PRELIMINARY_INELIGIBLE
        assert any(r.rule_id == "INT-001" for r in result.failed_rules)
    
    def test_int_14_residence_zero_days(self):
        """INT-14: 境外居住0天"""
        input_data = InternationalStudentInput(
            current_nationality="USA",
            has_chinese_nationality=False,
            has_foreign_nationality=True,
            foreign_passport_issue_date=date(2020, 1, 1),
            total_days_abroad_last_4_years=0,
            admission_year=2026,
        )
        result = evaluate_international_student(input_data)
        assert result.result == ResultType.PRELIMINARY_INELIGIBLE
    
    def test_int_15_full_eligible(self):
        """INT-15: 完全符合国际生资格"""
        input_data = InternationalStudentInput(
            current_nationality="USA",
            has_chinese_nationality=False,
            has_foreign_nationality=True,
            born_abroad=True,
            parent_chinese_citizen=True,
            parent_settled_abroad=True,
            foreign_passport_issue_date=date(2020, 1, 1),
            residence_records=[
                ResidenceRecord(entry_date=date(2022, 1, 1), exit_date=date(2025, 12, 31), country="USA"),
            ],
            total_days_abroad_last_4_years=1000,
            admission_year=2026,
        )
        result = evaluate_international_student(input_data)
        assert result.result == ResultType.PRELIMINARY_ELIGIBLE
    
    def test_int_16_explanation_contains_disclaimer(self):
        """INT-16: 解释文案包含免责声明"""
        input_data = InternationalStudentInput(
            current_nationality="USA",
            has_chinese_nationality=False,
            has_foreign_nationality=True,
            foreign_passport_issue_date=date(2020, 1, 1),
            total_days_abroad_last_4_years=800,
            admission_year=2026,
        )
        result = evaluate_international_student(input_data)
        assert "初步资格评估" in result.explanation
        assert "不替代" in result.explanation
    
    def test_int_17_decision_to_dict(self):
        """INT-17: 判定结果可序列化为字典"""
        input_data = InternationalStudentInput(
            current_nationality="USA",
            has_chinese_nationality=False,
            has_foreign_nationality=True,
            foreign_passport_issue_date=date(2020, 1, 1),
            total_days_abroad_last_4_years=800,
            admission_year=2026,
        )
        result = evaluate_international_student(input_data)
        d = result.to_dict()
        assert d["result"] in ["PRELIMINARY_ELIGIBLE", "MANUAL_REVIEW_REQUIRED", "PRELIMINARY_INELIGIBLE"]
        assert d["category"] == "INTERNATIONAL"
    
    def test_int_18_naturalized_from_hkmt(self):
        """INT-18: 港澳台居民移民后申请"""
        input_data = InternationalStudentInput(
            current_nationality="USA",
            has_chinese_nationality=False,
            has_foreign_nationality=True,
            was_chinese_citizen=True,
            naturalization_date=date(2020, 1, 1),
            foreign_passport_issue_date=date(2020, 2, 1),
            total_days_abroad_last_4_years=800,
            admission_year=2026,
        )
        result = evaluate_international_student(input_data)
        assert any("申请人曾具有中国国籍" in e for e in result.evidence)
    
    def test_int_19_material_insufficient(self):
        """INT-19: 国籍材料不足"""
        input_data = InternationalStudentInput(
            current_nationality="",  # 未提供
            has_chinese_nationality=False,
            has_foreign_nationality=False,  # 未提供
            foreign_passport_issue_date=date(2020, 1, 1),
            total_days_abroad_last_4_years=800,
            admission_year=2026,
        )
        result = evaluate_international_student(input_data)
        # 应该能处理这种情况
        assert result.result in [ResultType.PRELIMINARY_ELIGIBLE, ResultType.MANUAL_REVIEW_REQUIRED, ResultType.PRELIMINARY_INELIGIBLE]
    
    def test_int_20_all_rules_traceable(self):
        """INT-20: 所有规则可追溯到政策文件"""
        input_data = InternationalStudentInput(
            current_nationality="USA",
            has_chinese_nationality=False,
            has_foreign_nationality=True,
            foreign_passport_issue_date=date(2020, 1, 1),
            total_days_abroad_last_4_years=800,
            admission_year=2026,
        )
        result = evaluate_international_student(input_data)
        # 所有 matched/failed/manual_review rules 都应有 evidence_source
        for rule in result.matched_rules + result.failed_rules + result.manual_review_rules:
            assert rule.evidence_source.startswith("SRC-"), f"Rule {rule.rule_id} missing evidence source"
