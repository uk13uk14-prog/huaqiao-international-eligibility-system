import httpx

from ..config import get_settings


EXPERT_SYSTEM = (
    "你正在起草升学顾问机构使用的正式书面方案初稿，供内部审核后送达客户。\n"
    "强制规则：禁止使用口语化；禁止自称“人工智能”“大模型”“助手”；禁止出现任何暴露自动化身份的措辞。\n"
    "文体：严谨、克制，贴近政策解读与升学规划公函风格；以简体中文输出。\n"
    "结构必须包含以下一级标题（可使用“一、”“二、”序号）：\n"
    "一、客户诉求与约束条件\n"
    "二、资格路径与政策依据要点（仅作一般性提示，须明示以主管部门及高校当年简章为准）\n"
    "三、材料与时间规划建议（分阶段列出，避免空泛）\n"
    "四、风险点与官方核验提示\n"
    "五、下一步行动清单（条列）\n"
    "内容应结合客户问题与个性化说明，条目清晰，可使用分级条列。"
)


def _local_expert_fallback(question: str, personalization: str, profile_hint: str) -> str:
    return (
        "一、客户诉求与约束条件\n"
        f"{question.strip()}\n"
        f"{personalization.strip()}\n"
        f"{profile_hint}\n\n"
        "二、资格路径与政策依据要点\n"
        "鉴于当前为离线生成环境，具体条文引用、适用路径与材料清单须由持牌顾问依据最新官方文件与客户原始凭证逐项核对后确认。\n\n"
        "三、材料与时间规划建议\n"
        "（1）整理身份与国籍状态证明文件；（2）整理海外居住与出入境记录；（3）按目标通道准备学历与成绩材料；（4）关注目标院校国际学生/侨联招生简章发布时间线。\n\n"
        "四、风险点与官方核验提示\n"
        "个案存在差异，须以高校及主管部门最终审核为准；敏感信息仅限授权人员查阅。\n\n"
        "五、下一步行动清单\n"
        "- 由顾问与客户确认适用通道与目标层次院校\n"
        "- 建立材料清单与截止时间表\n"
        "- 安排与客户的复核会议并形成正式稿\n"
    )


async def generate_expert_consult_draft(question: str, personalization: str, profile_json_hint: str = "") -> dict:
    settings = get_settings()
    user_block = (
        f"【客户咨询主题】\n{question}\n\n"
        f"【个性化需求与背景补充】\n{personalization or '（未补充）'}\n\n"
        f"【客户资料库摘要（如为空可忽略）】\n{profile_json_hint or '（无）'}\n"
    )
    if not settings.ai_api_key:
        text = _local_expert_fallback(question, personalization, profile_json_hint[:1200] if profile_json_hint else "")
        return {"text": text, "model": "local-expert-template", "fallback": True}

    payload = {
        "model": settings.ai_model,
        "messages": [
            {"role": "system", "content": EXPERT_SYSTEM},
            {"role": "user", "content": user_block},
        ],
        "temperature": 0.15,
    }
    headers = {"Authorization": f"Bearer {settings.ai_api_key}"}
    async with httpx.AsyncClient(timeout=120) as client:
        res = await client.post(f"{settings.ai_base_url}/chat/completions", json=payload, headers=headers)
        res.raise_for_status()
        data = res.json()
    text = data["choices"][0]["message"]["content"]
    return {"text": text, "model": settings.ai_model, "fallback": False}
