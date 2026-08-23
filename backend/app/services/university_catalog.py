C9_UNIVERSITIES = {"北京大学", "清华大学", "复旦大学", "上海交通大学", "南京大学", "浙江大学", "中国科学技术大学", "哈尔滨工业大学", "西安交通大学"}

PROJECT_985 = [
    "北京大学", "清华大学", "中国人民大学", "北京航空航天大学", "北京理工大学", "中国农业大学", "北京师范大学", "中央民族大学",
    "南开大学", "天津大学", "大连理工大学", "东北大学", "吉林大学", "哈尔滨工业大学", "复旦大学", "同济大学", "上海交通大学", "华东师范大学",
    "南京大学", "东南大学", "浙江大学", "中国科学技术大学", "厦门大学", "山东大学", "中国海洋大学", "武汉大学", "华中科技大学", "湖南大学",
    "中南大学", "国防科技大学", "中山大学", "华南理工大学", "四川大学", "电子科技大学", "重庆大学", "西安交通大学", "西北工业大学", "兰州大学", "西北农林科技大学",
]

PURE_211 = [
    "北京交通大学", "北京工业大学", "北京科技大学", "北京化工大学", "北京邮电大学", "北京林业大学", "北京中医药大学", "北京外国语大学", "中国传媒大学", "中央财经大学",
    "对外经济贸易大学", "北京体育大学", "中央音乐学院", "中国政法大学", "华北电力大学", "中国矿业大学（北京）", "中国石油大学（北京）", "中国地质大学（北京）", "北京协和医学院",
    "天津医科大学", "河北工业大学", "太原理工大学", "内蒙古大学", "辽宁大学", "大连海事大学", "延边大学", "东北师范大学", "哈尔滨工程大学", "东北农业大学", "东北林业大学",
    "上海财经大学", "上海外国语大学", "华东理工大学", "东华大学", "上海大学", "海军军医大学",
    "苏州大学", "南京航空航天大学", "南京理工大学", "中国矿业大学", "河海大学", "江南大学", "南京农业大学", "中国药科大学", "南京师范大学",
    "安徽大学", "合肥工业大学", "福州大学", "南昌大学", "中国石油大学（华东）", "郑州大学",
    "武汉理工大学", "华中师范大学", "华中农业大学", "中南财经政法大学", "中国地质大学（武汉）", "湖南师范大学", "暨南大学", "华南师范大学", "广西大学", "海南大学",
    "西南交通大学", "四川农业大学", "西南财经大学", "贵州大学", "云南大学", "西藏大学", "西北大学", "西安电子科技大学", "长安大学", "陕西师范大学", "空军军医大学",
    "青海大学", "宁夏大学", "新疆大学", "石河子大学",
]

EXTRA_UNIVERSITIES = [
    "上海体育大学", "中国音乐学院", "上海音乐学院", "中央美术学院", "中国美术学院", "广州美术学院", "华侨大学",
]

REGION = {
    "北京大学":"北京", "清华大学":"北京", "中国人民大学":"北京", "北京航空航天大学":"北京", "北京理工大学":"北京", "中国农业大学":"北京", "北京师范大学":"北京", "中央民族大学":"北京", "北京交通大学":"北京", "北京工业大学":"北京", "北京科技大学":"北京", "北京化工大学":"北京", "北京邮电大学":"北京", "北京林业大学":"北京", "北京中医药大学":"北京", "北京外国语大学":"北京", "中国传媒大学":"北京", "中央财经大学":"北京", "对外经济贸易大学":"北京", "北京体育大学":"北京", "中央音乐学院":"北京", "中国政法大学":"北京", "华北电力大学":"北京", "中国矿业大学（北京）":"北京", "中国石油大学（北京）":"北京", "中国地质大学（北京）":"北京", "北京协和医学院":"北京", "中央美术学院":"北京", "中国音乐学院":"北京",
    "南开大学":"天津", "天津大学":"天津", "天津医科大学":"天津", "河北工业大学":"河北", "太原理工大学":"山西", "内蒙古大学":"内蒙古",
    "大连理工大学":"辽宁", "东北大学":"辽宁", "辽宁大学":"辽宁", "大连海事大学":"辽宁", "吉林大学":"吉林", "延边大学":"吉林", "东北师范大学":"吉林", "哈尔滨工业大学":"黑龙江", "哈尔滨工程大学":"黑龙江", "东北农业大学":"黑龙江", "东北林业大学":"黑龙江",
    "复旦大学":"上海", "同济大学":"上海", "上海交通大学":"上海", "华东师范大学":"上海", "上海财经大学":"上海", "上海外国语大学":"上海", "华东理工大学":"上海", "东华大学":"上海", "上海大学":"上海", "海军军医大学":"上海", "上海体育大学":"上海", "上海音乐学院":"上海",
    "南京大学":"江苏", "东南大学":"江苏", "苏州大学":"江苏", "南京航空航天大学":"江苏", "南京理工大学":"江苏", "中国矿业大学":"江苏", "河海大学":"江苏", "江南大学":"江苏", "南京农业大学":"江苏", "中国药科大学":"江苏", "南京师范大学":"江苏",
    "浙江大学":"浙江", "中国美术学院":"浙江", "中国科学技术大学":"安徽", "安徽大学":"安徽", "合肥工业大学":"安徽", "厦门大学":"福建", "福州大学":"福建", "华侨大学":"福建", "南昌大学":"江西",
    "山东大学":"山东", "中国海洋大学":"山东", "中国石油大学（华东）":"山东", "郑州大学":"河南", "武汉大学":"湖北", "华中科技大学":"湖北", "武汉理工大学":"湖北", "华中师范大学":"湖北", "华中农业大学":"湖北", "中南财经政法大学":"湖北", "中国地质大学（武汉）":"湖北",
    "湖南大学":"湖南", "中南大学":"湖南", "国防科技大学":"湖南", "湖南师范大学":"湖南", "中山大学":"广东", "华南理工大学":"广东", "暨南大学":"广东", "华南师范大学":"广东", "广州美术学院":"广东", "广西大学":"广西", "海南大学":"海南",
    "四川大学":"四川", "电子科技大学":"四川", "西南交通大学":"四川", "四川农业大学":"四川", "西南财经大学":"四川", "重庆大学":"重庆", "贵州大学":"贵州", "云南大学":"云南", "西藏大学":"西藏",
    "西安交通大学":"陕西", "西北工业大学":"陕西", "西北农林科技大学":"陕西", "西北大学":"陕西", "西安电子科技大学":"陕西", "长安大学":"陕西", "陕西师范大学":"陕西", "空军军医大学":"陕西", "兰州大学":"甘肃", "青海大学":"青海", "宁夏大学":"宁夏", "新疆大学":"新疆", "石河子大学":"新疆",
}

URL = {
    "清华大学":"https://www.tsinghua.edu.cn/", "北京大学":"https://www.pku.edu.cn/", "浙江大学":"https://www.zju.edu.cn/", "上海交通大学":"https://www.sjtu.edu.cn/", "复旦大学":"https://www.fudan.edu.cn/", "南京大学":"https://www.nju.edu.cn/", "中国科学技术大学":"https://www.ustc.edu.cn/", "华中科技大学":"https://www.hust.edu.cn/", "武汉大学":"https://www.whu.edu.cn/", "西安交通大学":"https://www.xjtu.edu.cn/", "哈尔滨工业大学":"https://www.hit.edu.cn/", "中山大学":"https://www.sysu.edu.cn/", "北京航空航天大学":"https://www.buaa.edu.cn/", "北京理工大学":"https://www.bit.edu.cn/", "同济大学":"https://www.tongji.edu.cn/", "四川大学":"https://www.scu.edu.cn/", "东南大学":"https://www.seu.edu.cn/", "中国人民大学":"https://www.ruc.edu.cn/", "北京师范大学":"https://www.bnu.edu.cn/", "南开大学":"https://www.nankai.edu.cn/", "天津大学":"https://www.tju.edu.cn/", "山东大学":"https://www.sdu.edu.cn/", "厦门大学":"https://www.xmu.edu.cn/", "吉林大学":"https://www.jlu.edu.cn/", "大连理工大学":"https://www.dlut.edu.cn/", "西北工业大学":"https://www.nwpu.edu.cn/", "华南理工大学":"https://www.scut.edu.cn/", "中南大学":"https://www.csu.edu.cn/", "湖南大学":"https://www.hnu.edu.cn/", "重庆大学":"https://www.cqu.edu.cn/", "电子科技大学":"https://www.uestc.edu.cn/", "兰州大学":"https://www.lzu.edu.cn/", "中国农业大学":"https://www.cau.edu.cn/", "华东师范大学":"https://www.ecnu.edu.cn/", "中国海洋大学":"https://www.ouc.edu.cn/", "中央民族大学":"https://www.muc.edu.cn/", "东北大学":"https://www.neu.edu.cn/", "西北农林科技大学":"https://www.nwafu.edu.cn/", "国防科技大学":"https://www.nudt.edu.cn/",
    "北京交通大学":"https://www.bjtu.edu.cn/", "北京工业大学":"https://www.bjut.edu.cn/", "北京科技大学":"https://www.ustb.edu.cn/", "北京化工大学":"https://www.buct.edu.cn/", "北京邮电大学":"https://www.bupt.edu.cn/", "北京林业大学":"https://www.bjfu.edu.cn/", "北京中医药大学":"https://www.bucm.edu.cn/", "北京外国语大学":"https://www.bfsu.edu.cn/", "中国传媒大学":"https://www.cuc.edu.cn/", "中央财经大学":"https://www.cufe.edu.cn/", "对外经济贸易大学":"https://www.uibe.edu.cn/", "北京体育大学":"https://www.bsu.edu.cn/", "中央音乐学院":"https://www.ccom.edu.cn/", "中国政法大学":"https://www.cupl.edu.cn/", "华北电力大学":"https://www.ncepu.edu.cn/", "中国矿业大学（北京）":"https://www.cumtb.edu.cn/", "中国石油大学（北京）":"https://www.cup.edu.cn/", "中国地质大学（北京）":"https://www.cugb.edu.cn/", "北京协和医学院":"https://www.pumc.edu.cn/",
    "天津医科大学":"https://www.tmu.edu.cn/", "河北工业大学":"https://www.hebut.edu.cn/", "太原理工大学":"https://www.tyut.edu.cn/", "内蒙古大学":"https://www.imu.edu.cn/", "辽宁大学":"https://www.lnu.edu.cn/", "大连海事大学":"https://www.dlmu.edu.cn/", "延边大学":"https://www.ybu.edu.cn/", "东北师范大学":"https://www.nenu.edu.cn/", "哈尔滨工程大学":"https://www.hrbeu.edu.cn/", "东北农业大学":"https://www.neau.edu.cn/", "东北林业大学":"https://www.nefu.edu.cn/",
    "上海财经大学":"https://www.sufe.edu.cn/", "上海外国语大学":"https://www.shisu.edu.cn/", "华东理工大学":"https://www.ecust.edu.cn/", "东华大学":"https://www.dhu.edu.cn/", "上海大学":"https://www.shu.edu.cn/", "海军军医大学":"https://www.smmu.edu.cn/", "上海体育大学":"https://www.sus.edu.cn/", "上海音乐学院":"https://www.shcmusic.edu.cn/",
    "苏州大学":"https://www.suda.edu.cn/", "南京航空航天大学":"https://www.nuaa.edu.cn/", "南京理工大学":"https://www.njust.edu.cn/", "中国矿业大学":"https://www.cumt.edu.cn/", "河海大学":"https://www.hhu.edu.cn/", "江南大学":"https://www.jiangnan.edu.cn/", "南京农业大学":"https://www.njau.edu.cn/", "中国药科大学":"https://www.cpu.edu.cn/", "南京师范大学":"https://www.njnu.edu.cn/",
    "安徽大学":"https://www.ahu.edu.cn/", "合肥工业大学":"https://www.hfut.edu.cn/", "福州大学":"https://www.fzu.edu.cn/", "南昌大学":"https://www.ncu.edu.cn/", "中国石油大学（华东）":"https://www.upc.edu.cn/", "郑州大学":"https://www.zzu.edu.cn/", "武汉理工大学":"https://www.whut.edu.cn/", "华中师范大学":"https://www.ccnu.edu.cn/", "华中农业大学":"https://www.hzau.edu.cn/", "中南财经政法大学":"https://www.zuel.edu.cn/", "中国地质大学（武汉）":"https://www.cug.edu.cn/", "湖南师范大学":"https://www.hunnu.edu.cn/", "暨南大学":"https://www.jnu.edu.cn/", "华南师范大学":"https://www.scnu.edu.cn/", "广西大学":"https://www.gxu.edu.cn/", "海南大学":"https://www.hainanu.edu.cn/", "西南交通大学":"https://www.swjtu.edu.cn/", "四川农业大学":"https://www.sicau.edu.cn/", "西南财经大学":"https://www.swufe.edu.cn/", "贵州大学":"https://www.gzu.edu.cn/", "云南大学":"https://www.ynu.edu.cn/", "西藏大学":"https://www.utibet.edu.cn/", "西北大学":"https://www.nwu.edu.cn/", "西安电子科技大学":"https://www.xidian.edu.cn/", "长安大学":"https://www.chd.edu.cn/", "陕西师范大学":"https://www.snnu.edu.cn/", "空军军医大学":"https://www.fmmu.edu.cn/", "青海大学":"https://www.qhu.edu.cn/", "宁夏大学":"https://www.nxu.edu.cn/", "新疆大学":"https://www.xju.edu.cn/", "石河子大学":"https://www.shzu.edu.cn/", "中国音乐学院":"https://www.ccmusic.edu.cn/", "中央美术学院":"https://www.cafa.edu.cn/", "中国美术学院":"https://www.caa.edu.cn/", "广州美术学院":"https://www.gzarts.edu.cn/", "华侨大学":"https://www.hqu.edu.cn/",
}

RANK_OVERRIDES = {
    "清华大学": 1, "北京大学": 2, "浙江大学": 3, "上海交通大学": 4, "复旦大学": 5, "南京大学": 6, "中国科学技术大学": 7, "华中科技大学": 8, "武汉大学": 9, "西安交通大学": 10,
    "哈尔滨工业大学": 11, "中山大学": 12, "北京航空航天大学": 13, "北京理工大学": 14, "同济大学": 15, "四川大学": 16, "东南大学": 17, "中国人民大学": 18, "北京师范大学": 19, "南开大学": 20,
    "天津大学": 21, "山东大学": 22, "厦门大学": 23, "吉林大学": 24, "大连理工大学": 25, "西北工业大学": 26, "华南理工大学": 27, "中南大学": 28, "湖南大学": 29, "重庆大学": 30,
    "电子科技大学": 31, "兰州大学": 32, "中国农业大学": 33, "华东师范大学": 34, "中国海洋大学": 35, "中央民族大学": 36, "东北大学": 37, "北京科技大学": 38, "南京航空航天大学": 39, "南京理工大学": 40,
    "北京交通大学": 41, "华东理工大学": 42, "苏州大学": 43, "华中师范大学": 44, "武汉理工大学": 45, "西安电子科技大学": 46, "哈尔滨工程大学": 47, "暨南大学": 48, "上海大学": 49, "郑州大学": 50,
    "北京体育大学": 51, "上海体育大学": 52, "中央音乐学院": 53, "中国音乐学院": 54, "上海音乐学院": 55, "中央美术学院": 56, "中国美术学院": 57, "广州美术学院": 58, "华侨大学": 59,
}

MAJORS = {
    "医药": "临床医学、基础医学、药学、公共卫生、护理学",
    "体育": "体育教育、运动训练、运动康复、体育管理、专项测试",
    "音乐": "音乐表演、作曲、音乐教育、音乐学、艺术管理",
    "美术": "中国画、油画、雕塑、视觉传达、艺术理论",
    "设计": "建筑学、工业设计、视觉传达、环境设计、数字媒体艺术",
    "文史": "法学、经济学、新闻传播、中文、历史学、外国语言文学",
    "理工": "计算机、电子信息、机械工程、材料科学、自动化、土木工程",
    "综合": "经济管理、计算机、法学、中文、基础学科、交叉学科",
}

def _fields(name: str) -> str:
    mapping = []
    if any(k in name for k in ["医", "药", "中医", "协和"]): mapping.append("医药")
    if any(k in name for k in ["体育"]): mapping.append("体育")
    if any(k in name for k in ["音乐"]): mapping.append("音乐")
    if any(k in name for k in ["美术"]): mapping.extend(["美术", "设计"])
    if any(k in name for k in ["外国语", "财经", "政法", "传媒", "师范", "民族"]): mapping.extend(["文史", "综合"])
    if any(k in name for k in ["理工", "工业", "科技", "交通", "航空", "航天", "电子", "邮电", "化工", "矿业", "石油", "地质", "电力", "工程", "海事", "林业", "农业", "农林", "海洋"]): mapping.extend(["理工"])
    if not mapping: mapping.append("综合")
    if name in {"清华大学", "同济大学", "东南大学", "天津大学", "湖南大学", "重庆大学", "厦门大学", "华南理工大学", "上海大学", "苏州大学", "江南大学"}: mapping.append("设计")
    if name in {"北京大学", "复旦大学", "上海交通大学", "浙江大学", "四川大学", "山东大学", "吉林大学", "武汉大学", "中山大学", "华中科技大学", "中南大学", "兰州大学"}: mapping.append("医药")
    order = ["综合", "理工", "文史", "医药", "体育", "音乐", "美术", "设计"]
    return ",".join([x for x in order if x in set(mapping)])

def _type(name: str, fields: str) -> str:
    if "体育" in fields: return "体育类"
    if "音乐" in fields: return "音乐类"
    if "美术" in fields: return "美术类"
    if "医药" in fields and fields == "医药": return "医药类"
    if "文史" in fields and "理工" not in fields: return "文史社科类"
    if "理工" in fields and "综合" not in fields: return "理工类"
    return "综合类"

def _tags(name: str, extra_double_first_class: bool = False) -> str:
    tags = []
    if name in C9_UNIVERSITIES: tags.append("C9")
    if name in PROJECT_985:
        tags.extend(["985", "211", "双一流"])
    elif name in PURE_211:
        tags.extend(["纯211", "双一流"])
    elif extra_double_first_class:
        tags.append("双一流")
    else:
        tags.append("双非")
    tags.extend(["支持国际生招生", "支持华侨生招生"])
    return ",".join(dict.fromkeys(tags))

def _majors(fields: str) -> str:
    return "、".join(MAJORS[f] for f in fields.split(",") if f in MAJORS)

def _record(name: str, ranking: int, extra_double_first_class: bool = False) -> dict:
    fields = _fields(name)
    province = REGION.get(name, "全国")
    official = URL.get(name, "https://www.chsi.com.cn/")
    tags = _tags(name, extra_double_first_class)
    level = "C9联盟" if "C9" in tags else "985工程" if "985" in tags else "211工程" if "纯211" in tags else "双一流" if "双一流" in tags else "双非"
    return {
        "ranking": RANK_OVERRIDES.get(name, ranking),
        "name": name,
        "province": province,
        "university_type": _type(name, fields),
        "tags": tags,
        "fields": fields,
        "advantage_majors": _majors(fields),
        "url": official,
        "admission_url": official,
        "email": f"请以{name}官方招生网站公布邮箱为准",
        "phone": f"请以{name}官方招生网站公布电话为准",
        "office": f"{name}招生办公室/国际学生招生办公室",
        "description": f"{name}位于{province}，属于{level}院校，系统标注为支持国际生招生与华侨生招生，具体专业和名额以学校当年招生简章为准。",
        "requirements": "国际生以学校国际学生本科招生简章为准，华侨生以联招、两校联招或学校当年相关通道要求为准。",
    }

def build_universities() -> list[dict]:
    seen = set()
    rows = []
    for idx, name in enumerate(PROJECT_985 + PURE_211, start=1):
        if name in seen:
            raise ValueError(f"重复院校：{name}")
        seen.add(name)
        rows.append(_record(name, idx))
    for i, name in enumerate(EXTRA_UNIVERSITIES, start=901):
        if name in seen:
            continue
        # 艺术/体育特色院校中部分为双一流学科建设高校，华侨大学为原有华侨特色院校。
        rows.append(_record(name, i, extra_double_first_class=name not in {"广州美术学院", "华侨大学"}))
    return sorted(rows, key=lambda x: (x["ranking"], x["name"]))

UNIVERSITIES = build_universities()
PROJECT_985_COUNT = len(PROJECT_985)
PROJECT_211_COUNT = len(PROJECT_985) + len(PURE_211)
if PROJECT_985_COUNT != 39:
    raise RuntimeError(f"985 工程高校数量异常：{PROJECT_985_COUNT}")
if PROJECT_211_COUNT != 115:
    raise RuntimeError(f"211 工程高校数量异常：{PROJECT_211_COUNT}")

FIELD_SCHEDULES = {
    "体育": [(2026, 1, "专项报名与资格确认", "2月中旬", "3月至4月专项测试", "体育类需提前准备运动等级、专项成绩与体检材料。")],
    "音乐": [(2026, 1, "校考/作品初审报名", "2月上旬", "2月至3月专业考试", "音乐类请关注曲目、作品集、视频初审和现场复试安排。")],
    "美术": [(2026, 1, "校考/作品集报名", "2月上旬", "2月至3月专业考试", "美术类需准备作品集、素描/色彩/创作等专业材料。")],
    "设计": [(2026, 1, "设计类专业报名", "2月至3月", "校考/作品集审核", "设计类建议同步准备作品集与创意表达材料。")],
}
DEFAULT_SCHEDULES = [
    (2026, 1, "国际生材料预审与目标院校确认", "1月底前", "学校资格初审", "国际生重点准备护照、国籍状态、学历成绩、语言成绩和目标学校招生简章要求材料。"),
    (2026, 3, "国际生网上申请与材料提交", "3月底至4月", "材料审核/补件", "C9、985、211及双一流高校国际生申请通常集中在春季，具体以学校国际学生招生网站为准。"),
    (2026, 5, "国际生校测/面试/专业审核", "5月中下旬", "校测、面试或作品集审核", "理工、医药、艺术、体育等方向可能设置额外专业审核或专项测试。"),
    (2026, 7, "国际生录取确认与入学准备", "7月至8月", "录取确认、签证和住宿安排", "录取后关注缴费、JW材料、签证/居留和新生报到。"),
    (2026, 3, "华侨生联招报名与资格审核", "3月底", "网上报名与材料审核", "华侨生重点关注中国国籍、海外定居、出入境记录和学历材料一致性。"),
    (2026, 5, "华侨生考试或学校审核", "5月中下旬", "联招考试/学校审核", "华侨生路径以联招、两校联招或学校当年相关招生通道为准。"),
    (2026, 6, "华侨生志愿填报与录取", "6月至7月", "志愿填报、投档录取", "按目标院校层级和专业方向确认志愿顺序，优先核对官方招生章程。"),
]
