from .law import articles


def judge_international(data):
    reasons, suggestions = [], []
    foreign_identity_ok = data.has_foreign_nationality and not data.has_chinese_nationality
    if foreign_identity_ok:
        reasons.append("申请人填报为外国国籍且不具有中国国籍，满足国际生身份初判前提。")
    else:
        reasons.append("国际生通道要求以外国国籍身份报考，且不得同时具有中国国籍。")
        suggestions.append("如曾为中国公民或父母为中国公民，需提供国籍变更、退出或自动丧失依据材料。")
    nationality_loss_ok = False
    if data.has_denationalization_certificate and data.has_foreign_nationality:
        nationality_loss_ok = True
        reasons.append("已勾选具备退籍/国籍状态证明，可作为原中国籍或复杂国籍背景的关键辅助材料。")
    elif data.settled_abroad and data.has_foreign_nationality and data.foreign_nationality_acquired_date:
        nationality_loss_ok = True
        reasons.append("已填报定居外国并取得外国国籍，可关联国籍法第九条进行中国国籍状态解释。")
    elif data.born_abroad and data.parent_chinese_citizen and data.parent_settled_abroad_at_birth and data.has_foreign_nationality:
        nationality_loss_ok = True
        reasons.append("海外出生且父母一方为中国公民并在出生时定居外国、本人出生即具外国国籍，可关联国籍法第五条解释。")
    else:
        reasons.append("未能从填报信息中确认中国国籍不具有或已丧失的完整链条。")
        suggestions.append("请补充出生地、父母国籍与定居状态、外国护照取得时间、退籍证明/国籍状态证明、公安或使领馆证明等材料。")
    residence_ok = data.overseas_residence_months_last_4y >= 24 or data.annual_months_overseas >= 9
    if residence_ok:
        reasons.append("已满足本系统内置国际生学习/居住连续性辅助规则。")
    else:
        reasons.append("近四年海外居住月份或年度居住月份不足，可能不满足部分高校国际生报名要求。")
        suggestions.append("不同高校对国际生居住年限口径不同，请以目标高校当年招生简章为准。")
    if not data.has_denationalization_certificate and (data.parent_chinese_citizen or data.has_chinese_nationality):
        suggestions.append("如存在原中国籍、父母中国籍或曾有户籍背景，建议预留约1年办理退籍/国籍状态证明及相关公证认证材料。")
    qualified = foreign_identity_ok and nationality_loss_ok and residence_ok
    return {"qualified": qualified, "conclusion": "符合国际生资格初判条件" if qualified else "不符合国际生资格初判条件", "reasons": reasons, "basis_articles": articles([3, 5, 9, 14]), "suggestions": suggestions}


def judge_huaqiao(data):
    reasons, suggestions = [], []
    nationality_ok = data.has_chinese_nationality and not data.has_foreign_nationality
    if nationality_ok:
        reasons.append("申请人当前按填报信息属于中国国籍，且未填报外国国籍。")
    else:
        reasons.append("华侨生通道要求以中国国籍身份参加；若已取得外国国籍，需先依据国籍法核验中国国籍状态。")
        suggestions.append("请准备中国护照、户籍注销/保留证明、境外居留许可等材料进行人工复核。")
    residence_ok = data.settled_abroad and data.overseas_residence_months_last_2y >= 18
    if residence_ok:
        reasons.append("已填报定居国外，且近两年海外实际居住不少于18个月，满足本系统内置华侨生居住规则。")
    else:
        reasons.append("未同时满足定居国外和近两年海外实际居住不少于18个月的华侨生居住规则。")
        suggestions.append("补充永久/长期居留证明、出入境记录和近两年居住月份证明。")
    household_ok = not data.has_mainland_household
    if household_ok:
        reasons.append("未填报仍保留内地户籍，有利于华侨身份材料一致性。")
    else:
        reasons.append("仍保留内地户籍，可能与华侨身份认定材料存在冲突。")
        suggestions.append("请向报名机构确认户籍状态是否需要注销或补充说明。")
    qualified = nationality_ok and residence_ok and household_ok
    return {"qualified": qualified, "conclusion": "符合华侨生资格初判条件" if qualified else "不符合华侨生资格初判条件", "reasons": reasons, "basis_articles": articles([1, 2, 3, 9, 14]), "suggestions": suggestions}
