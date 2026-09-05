"""AI may only organize language — never invent deadline dates."""
from __future__ import annotations
from datetime import date, datetime
from typing import Any

def _fmt_date(value: date | datetime | str | None) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    text = str(value).strip()
    if len(text) >= 10 and text[4] == "-" and text[7] == "-":
        return text[:10]
    return ""

def format_deadline_label(label: str, days_before: int, deadline: date | datetime | str | None) -> tuple[str, str]:
    label = (label or "重要节点").strip()
    deadline_s = _fmt_date(deadline)
    mapping = {
        30: (f"距离{label}还有30天", f"截止日期为{deadline_s}。请提前规划材料与报名节奏。" if deadline_s else "请提前规划材料与报名节奏。"),
        14: (f"距离{label}还有14天", "请确认申请材料是否齐全。"),
        7: (f"申请截止仅剩7天：{label}", f"{label}截止还有7天" + (f"（{deadline_s}）" if deadline_s else "") + "，建议今天完成材料最终核对。"),
        3: (f"申请进入最后3天：{label}", "请立即确认提交状态。"),
        1: (f"明天截止：{label}", "请马上确认是否已提交。"),
        0: (f"今天是截止日：{label}", "请确认提交结果，如有问题立即联系顾问。"),
    }
    if days_before in mapping:
        return mapping[days_before]
    return f"{label}还有{days_before}天", "请查看时间线并完成对应任务" + (f"。截止日期：{deadline_s}" if deadline_s else "。")

def render_template(template: str, *, label: str = "", days: int | None = None, **extra: Any) -> str:
    ctx = {"label": label or "重要节点", "days": days if days is not None else "", **extra}
    try:
        return (template or "").format(**ctx)
    except Exception:
        return template or ""

def ai_organize_copy(*, label: str, days_before: int, deadline: date | datetime | str | None,
                     title_template: str = "", body_template: str = "") -> tuple[str, str]:
    if title_template or body_template:
        return (
            render_template(title_template, label=label, days=days_before),
            render_template(body_template, label=label, days=days_before),
        )
    return format_deadline_label(label, days_before, deadline)

def refuse_invented_date(proposed: str | None, canonical: date | datetime | str | None) -> str:
    canon = _fmt_date(canonical)
    prop = _fmt_date(proposed)
    if not canon:
        return ""
    if prop and prop != canon:
        return canon
    return canon
