from dataclasses import dataclass
import json
from pathlib import Path
from .nationality_law import articles


DEFAULT_RULE_CONFIG = {
    "huaqiao": {
        "min_overseas_months_last_2y": 18,
        "requires_chinese_nationality": True,
        "requires_no_foreign_nationality": True,
        "requires_no_mainland_household": True,
    },
    "international": {
        "min_overseas_months_last_4y": 24,
        "min_annual_overseas_months": 9,
        "requires_foreign_nationality": True,
        "requires_no_chinese_nationality": True,
    },
}


def get_rule_config() -> dict:
    config_path = Path(__file__).resolve().parents[2] / "rules_config.json"
    if not config_path.exists():
        return DEFAULT_RULE_CONFIG
    with config_path.open("r", encoding="utf-8-sig") as file:
        loaded = json.load(file)
    return {**DEFAULT_RULE_CONFIG, **loaded}


@dataclass
class RuleResult:
    qualified: bool
    conclusion: str
    reasons: list[str]
    article_numbers: list[int]
    suggestions: list[str]


def determine_huaqiao(data) -> RuleResult:
    """与 SaaS Pro `judge_huaqiao` 对齐：中国国籍且无外国国籍、定居国外且近2年居住≥阈值、无内地户籍。"""
    config = get_rule_config()["huaqiao"]
    reasons: list[str] = []
    suggestions: list[str] = []
    article_numbers = [1, 2, 3, 9, 14]
    min_months = int(config.get("min_overseas_months_last_2y", 18))

    nationality_ok = data.has_chinese_nationality and not data.has_foreign_nationality
    if nationality_ok:
        reasons.append("申请人当前按填报信息属于中国国籍，且未填报外国国籍。")
    else:
        reasons.append("华侨生通道要求以中国国籍身份参加；若已取得外国国籍，需先依据国籍法核验中国国籍状态。")
        suggestions.append("请准备中国护照、户籍注销/保留证明、境外居留许可等材料进行人工复核。")

    residence_ok = data.settled_abroad and data.overseas_residence_months_last_2y >= min_months
    if residence_ok:
        reasons.append(f"已填报定居国外，且近两年海外实际居住不少于{min_months}个月，满足本系统内置华侨生居住规则。")
    else:
        reasons.append(f"未同时满足定居国外和近两年海外实际居住不少于{min_months}个月的华侨生居住规则。")
        suggestions.append("补充永久/长期居留证明、出入境记录和近两年居住月份证明。")

    household_ok = not data.has_mainland_household
    if household_ok:
        reasons.append("未填报仍保留内地户籍，有利于华侨身份材料一致性。")
    else:
        reasons.append("仍保留内地户籍，可能与华侨身份认定材料存在冲突。")
        suggestions.append("请向报名机构确认户籍状态是否需要注销或补充说明。")

    qualified = nationality_ok and residence_ok and household_ok
    conclusion = "符合华侨生资格初判条件" if qualified else "不符合华侨生资格初判条件"
    return RuleResult(qualified, conclusion, reasons, article_numbers, suggestions)


def determine_international(data) -> RuleResult:
    config = get_rule_config()["international"]
    reasons: list[str] = []
    suggestions: list[str] = []
    article_numbers = [3, 5, 9, 14]

    foreign_identity_ok = (
        (data.has_foreign_nationality or not config["requires_foreign_nationality"])
        and (not data.has_chinese_nationality or not config["requires_no_chinese_nationality"])
    )
    if foreign_identity_ok:
        reasons.append("申请人填报为外国国籍且不具有中国国籍，满足国际生身份初判前提。")
    else:
        reasons.append("国际生通道要求以外国国籍身份报考，且不得同时具有中国国籍。")
        suggestions.append("如曾为中国公民或父母为中国公民，需提供国籍变更、退出或自动丧失依据材料。")

    nationality_loss_ok = False
    if data.settled_abroad and data.has_foreign_nationality and data.foreign_nationality_acquired_date:
        nationality_loss_ok = True
        reasons.append("已填报定居外国并取得外国国籍，可关联国籍法第九条进行中国国籍状态解释。")
    elif data.born_abroad and data.parent_chinese_citizen and data.parent_settled_abroad_at_birth and data.has_foreign_nationality:
        nationality_loss_ok = True
        reasons.append("海外出生且父母一方为中国公民并在出生时定居外国、本人出生即具外国国籍，可关联国籍法第五条解释。")
    else:
        reasons.append("未能从填报信息中确认中国国籍不具有或已丧失的完整链条。")
        suggestions.append("请补充出生地、父母国籍与定居状态、外国护照取得时间、公安/使领馆证明等材料。")

    min_four_year_months = config["min_overseas_months_last_4y"]
    min_annual_months = config["min_annual_overseas_months"]
    residence_ok = data.overseas_residence_months_last_4y >= min_four_year_months or data.annual_months_overseas >= min_annual_months
    if residence_ok:
        reasons.append("已满足本系统内置国际生学习/居住连续性辅助规则。")
    else:
        reasons.append("近四年海外居住月份或年度居住月份不足，可能不满足部分高校国际生报名要求。")
        suggestions.append("不同高校对国际生居住年限口径不同，请以目标高校当年招生简章为准。")

    qualified = foreign_identity_ok and nationality_loss_ok and residence_ok
    conclusion = "符合国际生资格初判条件" if qualified else "不符合国际生资格初判条件"
    return RuleResult(qualified, conclusion, reasons, article_numbers, suggestions)


def to_payload(record_id: int, user_id: int, kind: str, result: RuleResult, created_at, recommendations: list[dict] | None = None):
    return {
        "record_id": record_id,
        "user_id": user_id,
        "eligibility_type": kind,
        "qualified": result.qualified,
        "conclusion": result.conclusion,
        "reasons": result.reasons,
        "basis_articles": articles(result.article_numbers),
        "suggestions": result.suggestions,
        "recommendations": recommendations or [],
        "created_at": created_at,
    }
