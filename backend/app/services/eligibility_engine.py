"""
Eligibility Engine — R4.2 政策规则引擎

基于 R4.1B 确认的官方规则实现资格判定。
输出三种结果：PRELIMINARY_ELIGIBLE / MANUAL_REVIEW_REQUIRED / PRELIMINARY_INELIGIBLE

禁止重新解释政策，只能实现 R4.1B 已确认的规则。
"""

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional
from enum import Enum

from .policy_registry import (
    INTERNATIONAL_RULES,
    OVERSEAS_CHINESE_RULES,
    MANUAL_REVIEW_RULES,
    get_source,
    ResultType,
)


# =============================================================================
# Input Data Models
# =============================================================================

@dataclass
class ResidenceRecord:
    """出入境记录"""
    entry_date: date  # 入境日期
    exit_date: date   # 出境日期
    country: str      # 国家代码


@dataclass
class InternationalStudentInput:
    """国际生资格判定输入"""
    # 国籍信息
    current_nationality: str  # 当前国籍
    has_chinese_nationality: bool = False
    has_foreign_nationality: bool = True
    foreign_passport_issue_date: Optional[date] = None
    
    # 出生信息
    born_in_china: bool = False
    born_abroad: bool = True
    
    # 父母信息
    parent_chinese_citizen: bool = False
    parent_settled_abroad: Optional[bool] = None  # None = 不确定
    
    # 居住记录
    residence_records: list[ResidenceRecord] = field(default_factory=list)
    total_days_abroad_last_4_years: int = 0
    
    # 入学年度
    admission_year: int = 2026
    
    # 原中国籍移民情况
    was_chinese_citizen: bool = False
    naturalization_date: Optional[date] = None


@dataclass
class OverseasChineseStudentInput:
    """华侨生资格判定输入"""
    # 国籍信息
    has_chinese_nationality: bool = True
    has_foreign_nationality: bool = False
    
    # 居留权类型
    has_permanent_residence: bool = False  # 永久居留
    has_long_term_residence: bool = False  # 长期居留（5年以上）
    residence_permit_issue_date: Optional[date] = None
    
    # 考生居住记录
    applicant_residence_days_2_consecutive_years: int = 0  # 连续两个自然年
    applicant_residence_days_pre_2_years: int = 0  # 报名前2年
    applicant_residence_days_5_consecutive_years: int = 0  # 连续5个自然年
    applicant_residence_days_pre_5_years: int = 0  # 报名前5年
    
    # 父母居住记录（仅一方）
    parent_residence_days_2_consecutive_years: int = 0
    parent_residence_days_5_consecutive_years: int = 0
    
    # 户籍信息
    has_mainland_hukou: Optional[bool] = None  # None = 不确定
    
    # 排除情形
    is_study_abroad_period: bool = False  # 留学期间
    is_official_duty_period: bool = False  # 因公出国期间
    
    # 目标大学
    target_university: Optional[str] = None
    
    # 报名年度
    admission_year: int = 2026


# =============================================================================
# Decision Output
# =============================================================================

@dataclass
class RuleEvaluation:
    """单条规则评估结果"""
    rule_id: str
    passed: bool
    reason: str
    evidence_source: str


@dataclass
class EligibilityDecision:
    """资格判定结果"""
    result: ResultType
    category: str  # "INTERNATIONAL" | "OVERSEAS_CHINESE"
    matched_rules: list[RuleEvaluation] = field(default_factory=list)
    failed_rules: list[RuleEvaluation] = field(default_factory=list)
    manual_review_rules: list[RuleEvaluation] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)
    missing_documents: list[str] = field(default_factory=list)
    explanation: str = ""
    
    def to_dict(self) -> dict:
        return {
            "result": self.result.value,
            "category": self.category,
            "matched_rules": [
                {"rule_id": r.rule_id, "reason": r.reason, "evidence_source": r.evidence_source}
                for r in self.matched_rules
            ],
            "failed_rules": [
                {"rule_id": r.rule_id, "reason": r.reason, "evidence_source": r.evidence_source}
                for r in self.failed_rules
            ],
            "manual_review_rules": [
                {"rule_id": r.rule_id, "reason": r.reason, "evidence_source": r.evidence_source}
                for r in self.manual_review_rules
            ],
            "evidence": self.evidence,
            "missing_documents": self.missing_documents,
            "explanation": self.explanation,
        }


# =============================================================================
# Helper Functions
# =============================================================================

def calculate_years_from_months(months: int) -> float:
    """将月份转换为年数（用于华侨生规则）"""
    return months / 12


def check_passport_validity(
    issue_date: Optional[date],
    admission_year: int,
    required_years: int = 4
) -> tuple[bool, str]:
    """
    INT-001: 检查护照有效期
    截止日：入学年度4月30日
    """
    if issue_date is None:
        return False, "未提供外国护照签发日期"
    
    cutoff_date = date(admission_year, 4, 30)
    years_held = (cutoff_date - issue_date).days / 365.25
    
    if years_held >= required_years:
        return True, f"截至{admission_year}年4月30日，持有外国护照约{years_held:.1f}年，满足{required_years}年要求"
    else:
        return False, f"截至{admission_year}年4月30日，持有外国护照约{years_held:.1f}年，不满足{required_years}年要求"


def check_residence_4years(
    total_days: int,
    has_month_level_data: bool = False
) -> tuple[Optional[bool], str, Optional[str]]:
    """
    INT-002/INT-003: 检查4年内居住记录
    要求：2年以上（约730天）
    
    注意：官方规则是"9个月可按一年计算"，需要出入境签章数据
    如果只有天数，无法精确判断"满9个月"，需要人工审核
    """
    required_days = 2 * 365  # 约730天
    
    if not has_month_level_data:
        # 只有天数数据，无法精确判断"满9个月"
        if total_days >= required_days:
            return None, f"境外居住{total_days}天，超过2年要求，但无法精确验证'9个月折算1年'规则", "MR-003"
        else:
            return False, f"境外居住{total_days}天，不足2年要求", None
    
    # 有出入境记录，可以精确计算
    if total_days >= required_days:
        return True, f"境外居住{total_days}天，满足2年要求", None
    else:
        return False, f"境外居住{total_days}天，不足2年要求", None


# =============================================================================
# International Student Evaluation
# =============================================================================

def evaluate_international_student(input_data: InternationalStudentInput) -> EligibilityDecision:
    """评估国际生资格"""
    decision = EligibilityDecision(
        result=ResultType.PRELIMINARY_ELIGIBLE,
        category="INTERNATIONAL",
    )
    
    # INT-001: 护照有效期
    passport_ok, passport_reason = check_passport_validity(
        input_data.foreign_passport_issue_date,
        input_data.admission_year,
        required_years=4
    )
    if passport_ok:
        decision.matched_rules.append(RuleEvaluation(
            rule_id="INT-001",
            passed=True,
            reason=passport_reason,
            evidence_source="SRC-001"
        ))
    else:
        decision.failed_rules.append(RuleEvaluation(
            rule_id="INT-001",
            passed=False,
            reason=passport_reason,
            evidence_source="SRC-001"
        ))
        decision.result = ResultType.PRELIMINARY_INELIGIBLE
    
    # INT-002/INT-003: 居住记录
    has_month_data = len(input_data.residence_records) > 0
    residence_result, residence_reason, review_rule = check_residence_4years(
        input_data.total_days_abroad_last_4_years,
        has_month_level_data=has_month_data
    )
    
    if residence_result is True:
        decision.matched_rules.append(RuleEvaluation(
            rule_id="INT-002",
            passed=True,
            reason=residence_reason,
            evidence_source="SRC-001"
        ))
    elif residence_result is False:
        decision.failed_rules.append(RuleEvaluation(
            rule_id="INT-002",
            passed=False,
            reason=residence_reason,
            evidence_source="SRC-001"
        ))
        decision.result = ResultType.PRELIMINARY_INELIGIBLE
    else:
        # 需要人工审核
        decision.manual_review_rules.append(RuleEvaluation(
            rule_id=review_rule or "MR-003",
            passed=None,
            reason=residence_reason,
            evidence_source="SRC-001"
        ))
        if decision.result == ResultType.PRELIMINARY_ELIGIBLE:
            decision.result = ResultType.MANUAL_REVIEW_REQUIRED
    
    # INT-004: 国籍法第五条
    if input_data.born_abroad and input_data.parent_chinese_citizen:
        if input_data.parent_settled_abroad is None:
            # 不确定父母是否定居
            decision.manual_review_rules.append(RuleEvaluation(
                rule_id="MR-001",
                passed=None,
                reason="无法确定父母是否在外国'定居'，需人工审核国籍法第五条适用性",
                evidence_source="SRC-002"
            ))
            if decision.result == ResultType.PRELIMINARY_ELIGIBLE:
                decision.result = ResultType.MANUAL_REVIEW_REQUIRED
        elif input_data.parent_settled_abroad and input_data.has_foreign_nationality:
            decision.matched_rules.append(RuleEvaluation(
                rule_id="INT-004",
                passed=True,
                reason="出生在国外，父母一方为中国公民并定居外国，本人具有外国国籍，依据国籍法第五条不具有中国国籍",
                evidence_source="SRC-002"
            ))
    
    # INT-005: 原中国籍移民
    if input_data.was_chinese_citizen:
        decision.evidence.append("申请人曾具有中国国籍，后取得外国国籍")
        decision.missing_documents.append("国籍变更/退出证明文件")
    
    # 国籍状态检查
    if input_data.has_chinese_nationality:
        decision.failed_rules.append(RuleEvaluation(
            rule_id="INT-004",
            passed=False,
            reason="国际生不得同时具有中国国籍",
            evidence_source="SRC-002"
        ))
        decision.result = ResultType.PRELIMINARY_INELIGIBLE
    
    # 生成解释
    if decision.result == ResultType.PRELIMINARY_ELIGIBLE:
        decision.explanation = "初步符合国际生资格条件，建议进一步确认材料完整性"
    elif decision.result == ResultType.MANUAL_REVIEW_REQUIRED:
        decision.explanation = "部分条件需要人工复核，请准备相关证明材料"
    else:
        decision.explanation = "初步不符合国际生资格条件"
    
    # 添加通用免责声明
    decision.explanation += "\n\n本结果为基于当前政策与用户提供信息生成的初步资格评估，不替代教育主管部门、联招办或高校的最终资格审核。"
    
    return decision


# =============================================================================
# Overseas Chinese Student Evaluation
# =============================================================================

def evaluate_overseas_chinese_student(input_data: OverseasChineseStudentInput) -> EligibilityDecision:
    """评估华侨生资格"""
    decision = EligibilityDecision(
        result=ResultType.PRELIMINARY_ELIGIBLE,
        category="OVERSEAS_CHINESE",
    )
    
    # OC-007: 华侨身份基本检查
    if not input_data.has_chinese_nationality:
        decision.failed_rules.append(RuleEvaluation(
            rule_id="OC-007",
            passed=False,
            reason="华侨生必须具有中国国籍",
            evidence_source="SRC-003"
        ))
        decision.result = ResultType.PRELIMINARY_INELIGIBLE
    else:
        decision.matched_rules.append(RuleEvaluation(
            rule_id="OC-007",
            passed=True,
            reason="申请人具有中国国籍",
            evidence_source="SRC-003"
        ))
    
    # OC-010: 排除情形
    if input_data.is_study_abroad_period:
        decision.failed_rules.append(RuleEvaluation(
            rule_id="OC-010",
            passed=False,
            reason="出国留学期间不视为华侨",
            evidence_source="SRC-003"
        ))
        decision.result = ResultType.PRELIMINARY_INELIGIBLE
    
    if input_data.is_official_duty_period:
        decision.failed_rules.append(RuleEvaluation(
            rule_id="OC-010",
            passed=False,
            reason="因公务出国期间不视为华侨",
            evidence_source="SRC-003"
        ))
        decision.result = ResultType.PRELIMINARY_INELIGIBLE
    
    # 根据居留权类型选择评估路径
    if input_data.has_permanent_residence:
        # 永久居留路径
        _evaluate_permanent_residence_path(input_data, decision)
    elif input_data.has_long_term_residence:
        # 5年合法居留路径
        _evaluate_five_year_path(input_data, decision)
    else:
        decision.manual_review_rules.append(RuleEvaluation(
            rule_id="OC-001",
            passed=None,
            reason="未提供有效的永久居留或长期居留证明",
            evidence_source="SRC-004"
        ))
        if decision.result == ResultType.PRELIMINARY_ELIGIBLE:
            decision.result = ResultType.MANUAL_REVIEW_REQUIRED
    
    # MR-002: 户籍问题
    if input_data.has_mainland_hukou is True:
        decision.manual_review_rules.append(RuleEvaluation(
            rule_id="MR-002",
            passed=None,
            reason="申请人仍保留中国内地户籍，需向报名机构确认是否需要注销",
            evidence_source="SRC-004"
        ))
        if decision.result == ResultType.PRELIMINARY_ELIGIBLE:
            decision.result = ResultType.MANUAL_REVIEW_REQUIRED
    elif input_data.has_mainland_hukou is False:
        decision.matched_rules.append(RuleEvaluation(
            rule_id="MR-002",
            passed=True,
            reason="申请人已注销中国内地户籍",
            evidence_source="SRC-004"
        ))
    
    # MR-004: 高校额外要求
    if input_data.target_university:
        decision.manual_review_rules.append(RuleEvaluation(
            rule_id="MR-004",
            passed=None,
            reason=f"目标大学 {input_data.target_university} 可能有额外资格要求，请查阅该校招生简章",
            evidence_source="SRC-001"
        ))
        if decision.result == ResultType.PRELIMINARY_ELIGIBLE:
            decision.result = ResultType.MANUAL_REVIEW_REQUIRED
    
    # 生成解释
    if decision.result == ResultType.PRELIMINARY_ELIGIBLE:
        decision.explanation = "初步符合华侨生资格条件，建议进一步确认材料完整性"
    elif decision.result == ResultType.MANUAL_REVIEW_REQUIRED:
        decision.explanation = "部分条件需要人工复核，请准备相关证明材料"
    else:
        decision.explanation = "初步不符合华侨生资格条件"
    
    # 添加通用免责声明
    decision.explanation += "\n\n本结果为基于当前政策与用户提供信息生成的初步资格评估，不替代教育主管部门、联招办或高校的最终资格审核。"
    
    return decision


def _evaluate_permanent_residence_path(
    input_data: OverseasChineseStudentInput,
    decision: EligibilityDecision
) -> None:
    """评估永久居留路径（OC-002, OC-004, OC-006）"""
    required_days = 540
    
    # OC-002: 考生居住要求（双窗口）
    applicant_window1_ok = input_data.applicant_residence_days_2_consecutive_years >= required_days
    applicant_window2_ok = input_data.applicant_residence_days_pre_2_years >= required_days
    
    if applicant_window1_ok and applicant_window2_ok:
        decision.matched_rules.append(RuleEvaluation(
            rule_id="OC-002",
            passed=True,
            reason=f"考生连续两个自然年居住{input_data.applicant_residence_days_2_consecutive_years}天，报名前2年居住{input_data.applicant_residence_days_pre_2_years}天，均满足540天要求",
            evidence_source="SRC-005"
        ))
    else:
        reasons = []
        if not applicant_window1_ok:
            reasons.append(f"连续两个自然年居住{input_data.applicant_residence_days_2_consecutive_years}天，不足540天")
        if not applicant_window2_ok:
            reasons.append(f"报名前2年居住{input_data.applicant_residence_days_pre_2_years}天，不足540天")
        decision.failed_rules.append(RuleEvaluation(
            rule_id="OC-002",
            passed=False,
            reason="；".join(reasons),
            evidence_source="SRC-005"
        ))
        decision.result = ResultType.PRELIMINARY_INELIGIBLE
    
    # OC-004: 父母居住要求（仅连续两个自然年）
    parent_ok = input_data.parent_residence_days_2_consecutive_years >= required_days
    
    if parent_ok:
        decision.matched_rules.append(RuleEvaluation(
            rule_id="OC-004",
            passed=True,
            reason=f"父母一方连续两个自然年居住{input_data.parent_residence_days_2_consecutive_years}天，满足540天要求",
            evidence_source="SRC-005"
        ))
    else:
        decision.failed_rules.append(RuleEvaluation(
            rule_id="OC-004",
            passed=False,
            reason=f"父母一方连续两个自然年居住{input_data.parent_residence_days_2_consecutive_years}天，不足540天",
            evidence_source="SRC-005"
        ))
        decision.result = ResultType.PRELIMINARY_INELIGIBLE
    
    # OC-006: 分别计算
    decision.matched_rules.append(RuleEvaluation(
        rule_id="OC-006",
        passed=True,
        reason="考生与父母居住时间分别计算",
        evidence_source="SRC-005"
    ))


def _evaluate_five_year_path(
    input_data: OverseasChineseStudentInput,
    decision: EligibilityDecision
) -> None:
    """评估5年合法居留路径（OC-003, OC-005, OC-006）"""
    required_days = 900
    
    # OC-003: 考生居住要求（双窗口）
    applicant_window1_ok = input_data.applicant_residence_days_5_consecutive_years >= required_days
    applicant_window2_ok = input_data.applicant_residence_days_pre_5_years >= required_days
    
    if applicant_window1_ok and applicant_window2_ok:
        decision.matched_rules.append(RuleEvaluation(
            rule_id="OC-003",
            passed=True,
            reason=f"考生连续5个自然年居住{input_data.applicant_residence_days_5_consecutive_years}天，报名前5年居住{input_data.applicant_residence_days_pre_5_years}天，均满足900天要求",
            evidence_source="SRC-005"
        ))
    else:
        reasons = []
        if not applicant_window1_ok:
            reasons.append(f"连续5个自然年居住{input_data.applicant_residence_days_5_consecutive_years}天，不足900天")
        if not applicant_window2_ok:
            reasons.append(f"报名前5年居住{input_data.applicant_residence_days_pre_5_years}天，不足900天")
        decision.failed_rules.append(RuleEvaluation(
            rule_id="OC-003",
            passed=False,
            reason="；".join(reasons),
            evidence_source="SRC-005"
        ))
        decision.result = ResultType.PRELIMINARY_INELIGIBLE
    
    # OC-005: 父母居住要求（仅连续5个自然年）
    parent_ok = input_data.parent_residence_days_5_consecutive_years >= required_days
    
    if parent_ok:
        decision.matched_rules.append(RuleEvaluation(
            rule_id="OC-005",
            passed=True,
            reason=f"父母一方连续5个自然年居住{input_data.parent_residence_days_5_consecutive_years}天，满足900天要求",
            evidence_source="SRC-005"
        ))
    else:
        decision.failed_rules.append(RuleEvaluation(
            rule_id="OC-005",
            passed=False,
            reason=f"父母一方连续5个自然年居住{input_data.parent_residence_days_5_consecutive_years}天，不足900天",
            evidence_source="SRC-005"
        ))
        decision.result = ResultType.PRELIMINARY_INELIGIBLE
    
    # OC-006: 分别计算
    decision.matched_rules.append(RuleEvaluation(
        rule_id="OC-006",
        passed=True,
        reason="考生与父母居住时间分别计算",
        evidence_source="SRC-005"
    ))
