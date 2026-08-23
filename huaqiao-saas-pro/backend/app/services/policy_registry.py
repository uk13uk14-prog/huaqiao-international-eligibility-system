"""
Policy Rule Registry — R4.1B 确认的官方规则

本文件是系统唯一的政策规则来源。
所有规则必须可追溯到官方政策文件（见 SOURCE_REGISTRY）。
禁止在其他文件中硬编码政策文案。
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class Confidence(Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class ResultType(Enum):
    PRELIMINARY_ELIGIBLE = "PRELIMINARY_ELIGIBLE"
    MANUAL_REVIEW_REQUIRED = "MANUAL_REVIEW_REQUIRED"
    PRELIMINARY_INELIGIBLE = "PRELIMINARY_INELIGIBLE"


@dataclass(frozen=True)
class PolicyRule:
    rule_id: str
    title: str
    description: str
    source_id: str
    confidence: Confidence
    machine_executable: bool
    category: str  # "INTERNATIONAL" | "OVERSEAS_CHINESE" | "MANUAL_REVIEW"


# =============================================================================
# Source Registry — R4.1B-4
# =============================================================================

SOURCE_REGISTRY = {
    "SRC-001": {
        "source_type": "PRIMARY_OFFICIAL",
        "issuing_authority": "教育部",
        "title": "教育部关于规范我高等学校接受国际学生有关工作的通知",
        "document_number": "教外函〔2020〕12号",
        "official_url": "https://www.gov.cn/zhengce/zhengceku/2020-06/10/content_5518369.htm",
        "effective_date": "2021-01-01",
        "last_verified_at": "2026-01-17",
    },
    "SRC-002": {
        "source_type": "PRIMARY_OFFICIAL",
        "issuing_authority": "全国人民代表大会常务委员会",
        "title": "中华人民共和国国籍法",
        "document_number": "主席令第三十五号",
        "official_url": "https://www.gov.cn/zhengce/2020-06/23/content_5521059.htm",
        "effective_date": "1980-01-01",
        "last_verified_at": "2026-01-17",
    },
    "SRC-003": {
        "source_type": "PRIMARY_OFFICIAL",
        "issuing_authority": "国务院侨务办公室",
        "title": "关于界定华侨外籍华人归侨侨眷身份的规定",
        "document_number": "国侨发〔2009〕5号",
        "official_url": "http://www.gqb.gov.cn/news/2016/0505/39044.shtml",
        "effective_date": "2009-04-24",
        "last_verified_at": "2026-01-17",
    },
    "SRC-004": {
        "source_type": "PRIMARY_OFFICIAL",
        "issuing_authority": "广东省教育考试院",
        "title": "2025年中华人民共和国普通高等学校联合招收华侨港澳台学生简章",
        "document_number": "粤考院普〔2024〕51号",
        "official_url": "https://eea.gd.gov.cn/lqtz/content/post_4593960.html",
        "effective_date": "2024-12-01",
        "last_verified_at": "2026-01-17",
    },
    "SRC-005": {
        "source_type": "PRIMARY_OFFICIAL",
        "issuing_authority": "江门市新会区人民政府",
        "title": "2025年全国联考华侨考生居住时间要求FAQ",
        "document_number": "N/A",
        "official_url": "http://www.xinhui.gov.cn/zmhd/hdwtk/jy/content/post_3259446.html",
        "effective_date": "2025-03-07",
        "last_verified_at": "2026-01-17",
    },
}


# =============================================================================
# International Student Rules — R4.1B-1
# =============================================================================

INTERNATIONAL_RULES: dict[str, PolicyRule] = {
    "INT-001": PolicyRule(
        rule_id="INT-001",
        title="有效外国护照/国籍证明持有年限",
        description="截至入学年度4月30日，持有有效外国护照或国籍证明文件满4年（含）以上",
        source_id="SRC-001",
        confidence=Confidence.HIGH,
        machine_executable=True,
        category="INTERNATIONAL",
    ),
    "INT-002": PolicyRule(
        rule_id="INT-002",
        title="最近4年外国实际居住记录",
        description="最近4年（截至入学年度的4月30日前）之内有在外国实际居住2年以上的记录",
        source_id="SRC-001",
        confidence=Confidence.HIGH,
        machine_executable=True,
        category="INTERNATIONAL",
    ),
    "INT-003": PolicyRule(
        rule_id="INT-003",
        title="9个月折算1年规则",
        description="一年中实际在外国居住满9个月可按一年计算，以入境和出境签章为准。注意：9个月不等于270天，须以出入境签章为准",
        source_id="SRC-001",
        confidence=Confidence.HIGH,
        machine_executable=False,  # 需要出入境签章数据，非简单天数换算
        category="INTERNATIONAL",
    ),
    "INT-004": PolicyRule(
        rule_id="INT-004",
        title="国籍法第五条适用",
        description="父母双方或一方为中国公民并定居在外国，本人出生时即具有外国国籍的，不具有中国国籍",
        source_id="SRC-002",
        confidence=Confidence.HIGH,
        machine_executable=True,
        category="INTERNATIONAL",
    ),
    "INT-005": PolicyRule(
        rule_id="INT-005",
        title="原大陆/港澳台居民移民后申请",
        description="祖国大陆（内地）、香港、澳门和台湾居民在移民并获得外国国籍后申请作为国际学生，应满足INT-001至INT-003要求",
        source_id="SRC-001",
        confidence=Confidence.HIGH,
        machine_executable=True,
        category="INTERNATIONAL",
    ),
}


# =============================================================================
# Overseas Chinese Student Rules — R4.1B-1
# =============================================================================

OVERSEAS_CHINESE_RULES: dict[str, PolicyRule] = {
    "OC-001": PolicyRule(
        rule_id="OC-001",
        title="有效身份证件",
        description="考生须持有住在国有效身份证件（外国永久居留证或长期居留证明）",
        source_id="SRC-004",
        confidence=Confidence.HIGH,
        machine_executable=True,
        category="OVERSEAS_CHINESE",
    ),
    "OC-002": PolicyRule(
        rule_id="OC-002",
        title="华侨生永久居留路径 — 考生居住要求",
        description="考生本人取得住在国长期或永久居留权，须同时满足：(1)连续两个自然年在住在国实际累计居留不少于540天；(2)报名前2年内在住在国实际累计居留不少于540天",
        source_id="SRC-005",
        confidence=Confidence.HIGH,
        machine_executable=True,
        category="OVERSEAS_CHINESE",
    ),
    "OC-003": PolicyRule(
        rule_id="OC-003",
        title="华侨生5年合法居留路径 — 考生居住要求",
        description="考生本人取得住在国连续5年合法居留资格，须同时满足：(1)连续5个自然年在住在国实际累计居留不少于900天；(2)报名前5年内在住在国实际累计居留不少于900天",
        source_id="SRC-005",
        confidence=Confidence.HIGH,
        machine_executable=True,
        category="OVERSEAS_CHINESE",
    ),
    "OC-004": PolicyRule(
        rule_id="OC-004",
        title="华侨生永久居留路径 — 父母居住要求",
        description="父母一方取得住在国长期或永久居留权，连续两个自然年在住在国实际累计居留不少于540天。注意：父母无'报名前2年'要求",
        source_id="SRC-005",
        confidence=Confidence.HIGH,
        machine_executable=True,
        category="OVERSEAS_CHINESE",
    ),
    "OC-005": PolicyRule(
        rule_id="OC-005",
        title="华侨生5年合法居留路径 — 父母居住要求",
        description="父母一方取得住在国连续5年合法居留资格，连续5个自然年在住在国实际累计居留不少于900天",
        source_id="SRC-005",
        confidence=Confidence.HIGH,
        machine_executable=True,
        category="OVERSEAS_CHINESE",
    ),
    "OC-006": PolicyRule(
        rule_id="OC-006",
        title="考生与父母分别计算",
        description="考生本人和其父母一方分别计算居住时间，双方须同时满足在住在国的居住时间要求",
        source_id="SRC-005",
        confidence=Confidence.HIGH,
        machine_executable=True,
        category="OVERSEAS_CHINESE",
    ),
    "OC-007": PolicyRule(
        rule_id="OC-007",
        title="华侨定义",
        description="华侨是指定居在国外的中国公民",
        source_id="SRC-003",
        confidence=Confidence.HIGH,
        machine_executable=True,
        category="OVERSEAS_CHINESE",
    ),
    "OC-008": PolicyRule(
        rule_id="OC-008",
        title="华侨定居定义A — 永久居留",
        description="已取得住在国长期或者永久居留权，并已在住在国连续居留2年，2年内累计居留不少于18个月",
        source_id="SRC-003",
        confidence=Confidence.HIGH,
        machine_executable=True,
        category="OVERSEAS_CHINESE",
    ),
    "OC-009": PolicyRule(
        rule_id="OC-009",
        title="华侨定居定义B — 合法居留",
        description="未取得住在国长期或者永久居留权，但已取得住在国连续5年以上（含5年）合法居留资格，5年内在住在国累计居留不少于30个月",
        source_id="SRC-003",
        confidence=Confidence.HIGH,
        machine_executable=True,
        category="OVERSEAS_CHINESE",
    ),
    "OC-010": PolicyRule(
        rule_id="OC-010",
        title="华侨身份排除情形",
        description="中国公民出国留学（包括公派和自费）期间、或因公务出国期间，不视为华侨",
        source_id="SRC-003",
        confidence=Confidence.HIGH,
        machine_executable=True,
        category="OVERSEAS_CHINESE",
    ),
}


# =============================================================================
# Manual Review Rules — R4.1B-2
# =============================================================================

MANUAL_REVIEW_RULES: dict[str, PolicyRule] = {
    "MR-001": PolicyRule(
        rule_id="MR-001",
        title="国籍法第五条'定居'定义不确定",
        description="国侨发〔2009〕5号的'定居'定义用于华侨身份界定，与国籍法第五条中'父母定居外国'的'定居'是否完全等同，无官方明确说明",
        source_id="SRC-003",
        confidence=Confidence.MEDIUM,
        machine_executable=False,
        category="MANUAL_REVIEW",
    ),
    "MR-002": PolicyRule(
        rule_id="MR-002",
        title="华侨生是否需注销内地户籍",
        description="2025年联招简章未明确要求华侨生注销内地户籍（仅要求'具有高中毕业文化程度'和居住时间）。华侨生与港澳台考生的户籍要求可能不同",
        source_id="SRC-004",
        confidence=Confidence.LOW,
        machine_executable=False,
        category="MANUAL_REVIEW",
    ),
    "MR-003": PolicyRule(
        rule_id="MR-003",
        title="'9个月'不可换算为天数",
        description="官方原文为'满9个月'，以出入境签章为准，未给出天数换算。不同月份天数不同（28-31天），无法统一为270天",
        source_id="SRC-001",
        confidence=Confidence.HIGH,
        machine_executable=False,
        category="MANUAL_REVIEW",
    ),
    "MR-004": PolicyRule(
        rule_id="MR-004",
        title="高校额外要求",
        description="教外函〔2020〕12号第三条允许高校'制定本校的规定，对国际学生申请入学的身份资格作出进一步要求'",
        source_id="SRC-001",
        confidence=Confidence.MEDIUM,
        machine_executable=False,
        category="MANUAL_REVIEW",
    ),
}


# =============================================================================
# Rejected Assumptions — R4.1B-3
# =============================================================================

REJECTED_ASSUMPTIONS = [
    {
        "id": "RA-001",
        "assumption": "9个月 = 270天",
        "reason": "官方原文为'满9个月'，以出入境签章为准，未给出天数换算",
    },
    {
        "id": "RA-002",
        "assumption": "华侨生必须注销中国内地户籍",
        "reason": "2025年联招简章对华侨生的报名条件中未明确要求注销内地户籍",
    },
    {
        "id": "RA-003",
        "assumption": "华侨定义中的'定居'必然等于国籍法第五条'定居'",
        "reason": "两者可能相关但不必然等同，无官方明确说明",
    },
    {
        "id": "RA-004",
        "assumption": "华侨生两个时间窗口只需满足其一",
        "reason": "官方FAQ明确：'连续两个自然年'和'报名前2年内'须同时满足",
    },
    {
        "id": "RA-005",
        "assumption": "父母条件与考生条件完全相同",
        "reason": "官方FAQ明确区分：考生需满足双窗口，父母仅需连续两个自然年",
    },
]


# =============================================================================
# Helper Functions
# =============================================================================

def get_rule(rule_id: str) -> Optional[PolicyRule]:
    """获取单个规则定义"""
    all_rules = {**INTERNATIONAL_RULES, **OVERSEAS_CHINESE_RULES, **MANUAL_REVIEW_RULES}
    return all_rules.get(rule_id)


def get_rules_by_category(category: str) -> list[PolicyRule]:
    """按类别获取规则列表"""
    if category == "INTERNATIONAL":
        return list(INTERNATIONAL_RULES.values())
    elif category == "OVERSEAS_CHINESE":
        return list(OVERSEAS_CHINESE_RULES.values())
    elif category == "MANUAL_REVIEW":
        return list(MANUAL_REVIEW_RULES.values())
    return []


def get_source(source_id: str) -> Optional[dict]:
    """获取政策来源信息"""
    return SOURCE_REGISTRY.get(source_id)


def get_all_sources() -> dict:
    """获取所有政策来源"""
    return SOURCE_REGISTRY.copy()
