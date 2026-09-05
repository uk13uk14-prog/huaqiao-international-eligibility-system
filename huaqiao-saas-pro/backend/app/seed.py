import json
import secrets
from sqlalchemy import text
from sqlalchemy.orm import Session
from .models import AdmissionSchedule, MembershipPlan, PermissionConfig, RechargeCode, Tenant, University, User
from .services.security import hash_password
from .services.university_catalog import DEFAULT_SCHEDULES, FIELD_SCHEDULES, UNIVERSITIES

PLAN_DATA = [
    ("free", "免费版", 0, 0, "基础国际生/华侨生判定；试用到期后有限院校浏览；高阶功能需开通会员。"),
    ("pro_trial", "Pro 完整体验（7天）", 0, 7, "新用户自动开通：7 天内体验当前 Pro 软件功能（全量院校库、学生档案、规划等）。"),
    ("vip_month", "月会员", 799, 30, "全量院校库、一对一专家咨询与报告链、定制专家报告。"),
    ("vip_year", "年会员", 999, 365, "含月会员权益；完整智能时间轴与关键节点提醒。"),
    ("vip_three_year", "三年会员", 1999, 1095, "含年会员权益；长周期证件与资格年限跟踪。"),
    ("lifetime", "终身版", 9999, 36500, "一次性买断，长期有效；权益覆盖全部付费能力（含完整时间轴），适合机构/私有化。"),
    ("monthly", "月度会员（兼容）", 199, 30, "已下架展示；仅供历史卡密兑换，权益与「月会员」一致。"),
    ("yearly", "年度会员（兼容）", 999, 365, "已下架展示；仅供历史卡密兑换，权益与「年会员」一致。"),
]

UNIVERSITIES = [
    {"ranking": 1, "name": "清华大学", "province": "北京", "university_type": "综合类/理工强校", "tags": "C9,985,211,双一流", "fields": "综合,理工,设计", "advantage_majors": "计算机科学与技术、电子信息、建筑学、工业设计、经济管理", "url": "https://www.tsinghua.edu.cn/"},
    {"ranking": 2, "name": "北京大学", "province": "北京", "university_type": "综合类", "tags": "C9,985,211,双一流", "fields": "综合,文史,医药,理工", "advantage_majors": "中国语言文学、法学、基础医学、数学、经济学", "url": "https://www.pku.edu.cn/"},
    {"ranking": 3, "name": "浙江大学", "province": "浙江", "university_type": "综合类", "tags": "C9,985,211,双一流", "fields": "综合,理工,医药,设计", "advantage_majors": "计算机、控制科学、临床医学、农学、工业设计", "url": "https://www.zju.edu.cn/"},
    {"ranking": 4, "name": "上海交通大学", "province": "上海", "university_type": "综合类/理工医强校", "tags": "C9,985,211,双一流", "fields": "综合,理工,医药", "advantage_majors": "船舶与海洋工程、机械工程、临床医学、电子信息", "url": "https://www.sjtu.edu.cn/"},
    {"ranking": 5, "name": "复旦大学", "province": "上海", "university_type": "综合类", "tags": "C9,985,211,双一流", "fields": "综合,文史,医药,理工", "advantage_majors": "新闻传播、经济学、临床医学、数学、哲学", "url": "https://www.fudan.edu.cn/"},
    {"ranking": 6, "name": "南京大学", "province": "江苏", "university_type": "综合类", "tags": "C9,985,211,双一流", "fields": "综合,文史,理工", "advantage_majors": "物理学、天文学、地质学、中文、计算机", "url": "https://www.nju.edu.cn/"},
    {"ranking": 7, "name": "中国科学技术大学", "province": "安徽", "university_type": "理工类", "tags": "C9,985,211,双一流", "fields": "理工", "advantage_majors": "物理学、量子信息、化学、数学、计算机", "url": "https://www.ustc.edu.cn/"},
    {"ranking": 8, "name": "华中科技大学", "province": "湖北", "university_type": "综合类/理工医强校", "tags": "985,211,双一流", "fields": "综合,理工,医药", "advantage_majors": "机械工程、光电信息、公共卫生、临床医学、电气工程", "url": "https://www.hust.edu.cn/"},
    {"ranking": 9, "name": "武汉大学", "province": "湖北", "university_type": "综合类", "tags": "985,211,双一流", "fields": "综合,文史,理工,设计", "advantage_majors": "测绘工程、法学、图书情报、遥感、设计学", "url": "https://www.whu.edu.cn/"},
    {"ranking": 10, "name": "西安交通大学", "province": "陕西", "university_type": "综合类/理工强校", "tags": "C9,985,211,双一流", "fields": "综合,理工,医药", "advantage_majors": "能源动力、电气工程、机械工程、管理科学、临床医学", "url": "https://www.xjtu.edu.cn/"},
    {"ranking": 11, "name": "哈尔滨工业大学", "province": "黑龙江", "university_type": "理工类", "tags": "C9,985,211,双一流", "fields": "理工", "advantage_majors": "航天、机械、控制科学、计算机、材料", "url": "https://www.hit.edu.cn/"},
    {"ranking": 12, "name": "中山大学", "province": "广东", "university_type": "综合类", "tags": "985,211,双一流", "fields": "综合,文史,医药,理工", "advantage_majors": "临床医学、工商管理、哲学、生态学、公共卫生", "url": "https://www.sysu.edu.cn/"},
    {"ranking": 13, "name": "北京航空航天大学", "province": "北京", "university_type": "理工类", "tags": "985,211,双一流", "fields": "理工", "advantage_majors": "航空宇航、计算机、软件工程、仪器科学、自动化", "url": "https://www.buaa.edu.cn/"},
    {"ranking": 14, "name": "北京理工大学", "province": "北京", "university_type": "理工类", "tags": "985,211,双一流", "fields": "理工,设计", "advantage_majors": "兵器科学、车辆工程、信息工程、工业设计", "url": "https://www.bit.edu.cn/"},
    {"ranking": 15, "name": "同济大学", "province": "上海", "university_type": "综合类/理工强校", "tags": "985,211,双一流", "fields": "综合,理工,设计", "advantage_majors": "土木工程、建筑学、城乡规划、环境科学、设计创意", "url": "https://www.tongji.edu.cn/"},
    {"ranking": 16, "name": "四川大学", "province": "四川", "university_type": "综合类", "tags": "985,211,双一流", "fields": "综合,文史,医药,美术", "advantage_majors": "口腔医学、临床医学、中文、高分子、艺术设计", "url": "https://www.scu.edu.cn/"},
    {"ranking": 17, "name": "东南大学", "province": "江苏", "university_type": "综合类/理工强校", "tags": "985,211,双一流", "fields": "综合,理工,设计", "advantage_majors": "建筑学、土木工程、电子科学、交通运输、艺术学理论", "url": "https://www.seu.edu.cn/"},
    {"ranking": 18, "name": "中国人民大学", "province": "北京", "university_type": "文史社科类", "tags": "985,211,双一流", "fields": "文史,综合", "advantage_majors": "法学、经济学、新闻传播、社会学、公共管理", "url": "https://www.ruc.edu.cn/"},
    {"ranking": 19, "name": "北京师范大学", "province": "北京", "university_type": "师范类/综合", "tags": "985,211,双一流", "fields": "文史,综合,艺术", "advantage_majors": "教育学、心理学、中文、历史学、戏剧影视", "url": "https://www.bnu.edu.cn/"},
    {"ranking": 20, "name": "南开大学", "province": "天津", "university_type": "综合类", "tags": "985,211,双一流", "fields": "综合,文史,理工", "advantage_majors": "经济学、化学、历史学、数学、工商管理", "url": "https://www.nankai.edu.cn/"},
    {"ranking": 21, "name": "天津大学", "province": "天津", "university_type": "理工类", "tags": "985,211,双一流", "fields": "理工,设计", "advantage_majors": "化学工程、建筑学、仪器科学、管理科学、环境设计", "url": "https://www.tju.edu.cn/"},
    {"ranking": 22, "name": "山东大学", "province": "山东", "university_type": "综合类", "tags": "985,211,双一流", "fields": "综合,文史,医药,理工", "advantage_majors": "数学、材料、临床医学、中文、考古学", "url": "https://www.sdu.edu.cn/"},
    {"ranking": 23, "name": "厦门大学", "province": "福建", "university_type": "综合类", "tags": "985,211,双一流", "fields": "综合,文史,理工,设计", "advantage_majors": "会计学、海洋科学、经济学、化学、艺术设计", "url": "https://www.xmu.edu.cn/"},
    {"ranking": 24, "name": "吉林大学", "province": "吉林", "university_type": "综合类", "tags": "985,211,双一流", "fields": "综合,理工,医药,文史", "advantage_majors": "车辆工程、化学、法学、临床医学、考古学", "url": "https://www.jlu.edu.cn/"},
    {"ranking": 25, "name": "大连理工大学", "province": "辽宁", "university_type": "理工类", "tags": "985,211,双一流", "fields": "理工,设计", "advantage_majors": "化学工程、力学、机械、船舶、工业设计", "url": "https://www.dlut.edu.cn/"},
    {"ranking": 26, "name": "西北工业大学", "province": "陕西", "university_type": "理工类", "tags": "985,211,双一流", "fields": "理工", "advantage_majors": "航空、航天、航海、材料、计算机", "url": "https://www.nwpu.edu.cn/"},
    {"ranking": 27, "name": "华南理工大学", "province": "广东", "university_type": "理工类", "tags": "985,211,双一流", "fields": "理工,设计,综合", "advantage_majors": "轻工技术、建筑学、食品科学、材料、工业设计", "url": "https://www.scut.edu.cn/"},
    {"ranking": 28, "name": "中南大学", "province": "湖南", "university_type": "综合类/理工医强校", "tags": "985,211,双一流", "fields": "综合,理工,医药", "advantage_majors": "冶金、矿业、材料、临床医学、交通运输", "url": "https://www.csu.edu.cn/"},
    {"ranking": 29, "name": "湖南大学", "province": "湖南", "university_type": "综合类", "tags": "985,211,双一流", "fields": "综合,理工,设计", "advantage_majors": "土木工程、机械、设计学、工商管理、化学", "url": "https://www.hnu.edu.cn/"},
    {"ranking": 30, "name": "重庆大学", "province": "重庆", "university_type": "综合类/理工强校", "tags": "985,211,双一流", "fields": "综合,理工,设计", "advantage_majors": "建筑学、电气工程、机械、土木、影视与设计", "url": "https://www.cqu.edu.cn/"},
    {"ranking": 31, "name": "电子科技大学", "province": "四川", "university_type": "理工类", "tags": "985,211,双一流", "fields": "理工", "advantage_majors": "电子科学、信息与通信、计算机、集成电路", "url": "https://www.uestc.edu.cn/"},
    {"ranking": 32, "name": "兰州大学", "province": "甘肃", "university_type": "综合类", "tags": "985,211,双一流", "fields": "综合,理工,文史,医药", "advantage_majors": "草学、生态学、化学、物理、民族学", "url": "https://www.lzu.edu.cn/"},
    {"ranking": 33, "name": "中国农业大学", "province": "北京", "university_type": "农林类/综合", "tags": "985,211,双一流", "fields": "综合,理工", "advantage_majors": "农业工程、食品科学、动物医学、生物科学", "url": "https://www.cau.edu.cn/"},
    {"ranking": 34, "name": "华东师范大学", "province": "上海", "university_type": "师范类/综合", "tags": "985,211,双一流", "fields": "文史,综合,理工", "advantage_majors": "教育学、心理学、地理学、统计学、中文", "url": "https://www.ecnu.edu.cn/"},
    {"ranking": 35, "name": "中国海洋大学", "province": "山东", "university_type": "综合类/海洋特色", "tags": "985,211,双一流", "fields": "综合,理工", "advantage_majors": "海洋科学、水产、食品科学、环境科学", "url": "https://www.ouc.edu.cn/"},
    {"ranking": 36, "name": "中央民族大学", "province": "北京", "university_type": "民族类/综合", "tags": "985,211,双一流", "fields": "文史,综合,音乐,美术", "advantage_majors": "民族学、中国少数民族语言文学、音乐舞蹈、美术", "url": "https://www.muc.edu.cn/"},
    {"ranking": 37, "name": "东北大学", "province": "辽宁", "university_type": "理工类", "tags": "985,211,双一流", "fields": "理工", "advantage_majors": "控制科学、计算机、材料、软件工程", "url": "https://www.neu.edu.cn/"},
    {"ranking": 38, "name": "北京科技大学", "province": "北京", "university_type": "理工类", "tags": "211,双一流", "fields": "理工", "advantage_majors": "材料科学、冶金工程、矿业工程、机械", "url": "https://www.ustb.edu.cn/"},
    {"ranking": 39, "name": "南京航空航天大学", "province": "江苏", "university_type": "理工类", "tags": "211,双一流", "fields": "理工", "advantage_majors": "航空宇航、力学、机械、自动化", "url": "https://www.nuaa.edu.cn/"},
    {"ranking": 40, "name": "南京理工大学", "province": "江苏", "university_type": "理工类", "tags": "211,双一流", "fields": "理工", "advantage_majors": "兵器科学、化工、电子信息、计算机", "url": "https://www.njust.edu.cn/"},
    {"ranking": 41, "name": "北京交通大学", "province": "北京", "university_type": "理工类", "tags": "211,双一流", "fields": "理工", "advantage_majors": "交通运输、系统科学、信息工程、经济管理", "url": "https://www.bjtu.edu.cn/"},
    {"ranking": 42, "name": "华东理工大学", "province": "上海", "university_type": "理工类", "tags": "211,双一流", "fields": "理工,设计", "advantage_majors": "化学工程、材料、生物工程、工业设计", "url": "https://www.ecust.edu.cn/"},
    {"ranking": 43, "name": "苏州大学", "province": "江苏", "university_type": "综合类", "tags": "211,双一流", "fields": "综合,文史,医药,设计", "advantage_majors": "纺织、材料、临床医学、设计学、法学", "url": "https://www.suda.edu.cn/"},
    {"ranking": 44, "name": "华中师范大学", "province": "湖北", "university_type": "师范类/综合", "tags": "211,双一流", "fields": "文史,综合,音乐,美术", "advantage_majors": "教育学、心理学、中文、历史、音乐教育", "url": "https://www.ccnu.edu.cn/"},
    {"ranking": 45, "name": "武汉理工大学", "province": "湖北", "university_type": "理工类", "tags": "211,双一流", "fields": "理工,设计", "advantage_majors": "材料、交通运输、车辆工程、船舶、设计学", "url": "https://www.whut.edu.cn/"},
    {"ranking": 46, "name": "西安电子科技大学", "province": "陕西", "university_type": "理工类", "tags": "211,双一流", "fields": "理工", "advantage_majors": "电子信息、通信工程、网络安全、计算机", "url": "https://www.xidian.edu.cn/"},
    {"ranking": 47, "name": "哈尔滨工程大学", "province": "黑龙江", "university_type": "理工类", "tags": "211,双一流", "fields": "理工", "advantage_majors": "船舶与海洋、核科学、自动化、信息工程", "url": "https://www.hrbeu.edu.cn/"},
    {"ranking": 48, "name": "暨南大学", "province": "广东", "university_type": "综合类/侨校", "tags": "211,双一流,华侨特色", "fields": "综合,文史,医药,理工", "advantage_majors": "新闻传播、经济学、华文教育、临床医学、管理学", "url": "https://zsb.jnu.edu.cn/"},
    {"ranking": 49, "name": "上海大学", "province": "上海", "university_type": "综合类", "tags": "211,双一流", "fields": "综合,理工,美术,设计", "advantage_majors": "美术学、设计学、材料、社会学、电影", "url": "https://www.shu.edu.cn/"},
    {"ranking": 50, "name": "郑州大学", "province": "河南", "university_type": "综合类", "tags": "211,双一流", "fields": "综合,医药,理工,文史", "advantage_majors": "临床医学、材料、化学、水利、考古", "url": "https://www.zzu.edu.cn/"},
    {"ranking": 51, "name": "北京体育大学", "province": "北京", "university_type": "体育类", "tags": "211,双一流,体育顶尖", "fields": "体育", "advantage_majors": "体育教育、运动训练、运动人体科学、体育管理", "url": "https://www.bsu.edu.cn/"},
    {"ranking": 52, "name": "上海体育大学", "province": "上海", "university_type": "体育类", "tags": "双一流,体育顶尖", "fields": "体育", "advantage_majors": "体育学、运动康复、武术与民族传统体育、体育新闻", "url": "https://www.sus.edu.cn/"},
    {"ranking": 53, "name": "中央音乐学院", "province": "北京", "university_type": "音乐类", "tags": "211,双一流,音乐顶尖", "fields": "音乐", "advantage_majors": "作曲、钢琴、管弦、民乐、音乐学", "url": "https://www.ccom.edu.cn/"},
    {"ranking": 54, "name": "中国音乐学院", "province": "北京", "university_type": "音乐类", "tags": "双一流,音乐顶尖", "fields": "音乐", "advantage_majors": "中国声乐、中国器乐、作曲、音乐教育", "url": "https://www.ccmusic.edu.cn/"},
    {"ranking": 55, "name": "上海音乐学院", "province": "上海", "university_type": "音乐类", "tags": "双一流,音乐顶尖", "fields": "音乐", "advantage_majors": "音乐表演、作曲、音乐学、音乐工程", "url": "https://www.shcmusic.edu.cn/"},
    {"ranking": 56, "name": "中央美术学院", "province": "北京", "university_type": "美术类", "tags": "双一流,美术顶尖,设计顶尖", "fields": "美术,设计", "advantage_majors": "中国画、油画、雕塑、视觉传达、建筑与设计", "url": "https://www.cafa.edu.cn/"},
    {"ranking": 57, "name": "中国美术学院", "province": "浙江", "university_type": "美术类", "tags": "双一流,美术顶尖,设计顶尖", "fields": "美术,设计", "advantage_majors": "中国画、书法、跨媒体艺术、视觉传达、环境设计", "url": "https://www.caa.edu.cn/"},
    {"ranking": 58, "name": "广州美术学院", "province": "广东", "university_type": "美术类", "tags": "美术特色,设计特色", "fields": "美术,设计", "advantage_majors": "视觉传达、工业设计、绘画、雕塑、服装设计", "url": "https://www.gzarts.edu.cn/"},
    {"ranking": 59, "name": "华侨大学", "province": "福建", "university_type": "综合类/侨校", "tags": "华侨特色", "fields": "综合,文史,理工,设计", "advantage_majors": "华文教育、建筑学、工商管理、旅游管理、设计学", "url": "https://zsc.hqu.edu.cn/"},
]

FIELD_SCHEDULES = {
    "体育": [(2026, 1, "专项报名与资格确认", "2月中旬", "3月至4月专项测试", "体育类需提前准备运动等级、专项成绩与体检材料。")],
    "音乐": [(2026, 1, "校考/作品初审报名", "2月上旬", "2月至3月专业考试", "音乐类请关注曲目、作品集、视频初审和现场复试安排。")],
    "美术": [(2026, 1, "校考/作品集报名", "2月上旬", "2月至3月专业考试", "美术类需准备作品集、素描/色彩/创作等专业材料。")],
    "设计": [(2026, 1, "设计类专业报名", "2月至3月", "校考/作品集审核", "设计类建议同步准备作品集与创意表达材料。")],
}
DEFAULT_SCHEDULES = [(2026, 3, "3月上旬至下旬", "3月底", "5月中下旬", "华侨生重点关注联招报名、材料审核与考试安排。"), (2026, 11, "上一年11月至当年3月", "1月至4月", "校测/面试按学校通知", "国际生重点关注护照、国籍状态、学历和语言材料。")]

from .services.university_catalog import DEFAULT_SCHEDULES, FIELD_SCHEDULES, UNIVERSITIES


FREE_UNIVERSITIES = [
    {"ranking": 901, "name": "深圳大学", "province": "广东", "university_type": "综合类", "tags": "双非,支持国际生招生,支持华侨生招生,免费可查,非核心院校", "fields": "综合,理工,文史,设计", "advantage_majors": "计算机、电子信息、建筑学、设计学、经济管理", "url": "https://www.szu.edu.cn/"},
    {"ranking": 902, "name": "南方科技大学", "province": "广东", "university_type": "理工类", "tags": "双非,支持国际生招生,支持华侨生招生,免费可查,非核心院校", "fields": "理工,综合", "advantage_majors": "数学、物理、材料、电子信息、计算机", "url": "https://www.sustech.edu.cn/"},
    {"ranking": 903, "name": "首都师范大学", "province": "北京", "university_type": "师范类/综合", "tags": "双一流,支持国际生招生,支持华侨生招生,免费可查,非核心院校", "fields": "综合,文史,美术,音乐", "advantage_majors": "教育学、中文、历史学、美术、音乐教育", "url": "https://www.cnu.edu.cn/"},
]
LEGACY_FREE_REPLACEMENTS = {
    "区域国际本科示范学院": {"ranking": 904, "name": "宁波大学", "province": "浙江", "university_type": "综合类", "tags": "双一流,支持国际生招生,支持华侨生招生,免费可查,非核心院校", "fields": "综合,理工,文史", "advantage_majors": "水产、力学、信息科学、国际经济与贸易、法学", "url": "https://www.nbu.edu.cn/"},
    "国际艺术预科学院": {"ranking": 905, "name": "南京艺术学院", "province": "江苏", "university_type": "艺术类", "tags": "双非,支持国际生招生,支持华侨生招生,免费可查,非核心院校", "fields": "音乐,美术,设计", "advantage_majors": "音乐表演、美术学、设计学、传媒艺术、舞蹈", "url": "https://www.nua.edu.cn/"},
    "国际体育教育学院": {"ranking": 906, "name": "成都体育学院", "province": "四川", "university_type": "体育类", "tags": "双非,支持国际生招生,支持华侨生招生,免费可查,非核心院校", "fields": "体育", "advantage_majors": "体育教育、运动训练、运动康复、武术与民族传统体育", "url": "https://www.cdsu.edu.cn/"},
}

FIELD_SCHEDULES = {
    "体育": [(2026, 1, "专项报名与资格确认", "2月中旬", "3月至4月专项测试", "体育类需提前准备运动等级、专项成绩与体检材料。")],
    "音乐": [(2026, 1, "校考/作品初审报名", "2月上旬", "2月至3月专业考试", "音乐类请关注曲目、作品集、视频初审和现场复试安排。")],
    "美术": [(2026, 1, "校考/作品集报名", "2月上旬", "2月至3月专业考试", "美术类需准备作品集、素描/色彩/创作等专业材料。")],
    "设计": [(2026, 1, "设计类专业报名", "2月至3月", "校考/作品集审核", "设计类建议同步准备作品集与创意表达材料。")],
}
DEFAULT_SCHEDULES = [(2026, 3, "3月上旬至下旬", "3月底", "5月中下旬", "华侨生重点关注联招报名、材料审核与考试安排。"), (2026, 11, "上一年11月至当年3月", "1月至4月", "校测/面试按学校通知", "国际生重点关注护照、国籍状态、学历和语言材料。")]

from .services.university_catalog import DEFAULT_SCHEDULES, FIELD_SCHEDULES, UNIVERSITIES


def ensure_columns(db: Session):
    """Check and add missing columns using SQLAlchemy inspector (PostgreSQL compatible)."""
    from sqlalchemy import inspect
    inspector = inspect(db.get_bind())
    # Columns are now managed by Alembic migrations
    # This function is kept for backward compatibility but does nothing


def schedules_for(fields: str):
    rows = list(DEFAULT_SCHEDULES)
    for key, schedules in FIELD_SCHEDULES.items():
        if key in fields:
            rows.extend(schedules)
    return rows


def contact_for(item: dict):
    admission_url = item.get("admission_url") or item["url"]
    return {
        "admission_url": admission_url,
        "admission_email": item.get("email") or f"请以官方招生网站公布邮箱为准：{admission_url}",
        "admission_phone": item.get("phone") or f"请以官方招生网站公布电话为准：{admission_url}",
        "admissions_office": item.get("office") or f"{item['name']}招生办公室/国际学生招生办公室",
    }


def upsert_university(db: Session, item: dict, is_core: bool):
    university = db.query(University).filter(University.name == item["name"]).first()
    if not university:
        university = University(name=item["name"])
        db.add(university)
        db.flush()
    university.ranking = item["ranking"]
    university.province = item["province"]
    university.university_type = item.get("university_type", "")
    university.tags = item["tags"]
    university.fields = item["fields"]
    university.admission_targets = "international,huaqiao"
    university.advantage_majors = item["advantage_majors"]
    university.description = item.get("description") or f"{item['name']}是{item['province']}重点院校，覆盖{item['fields']}等国际生与华侨生咨询方向。"
    university.requirements = item.get("requirements") or "按当年官方招生简章提交身份、学历、成绩、语言、作品集或专项证明等材料。"
    university.official_url = item["url"]
    contact = contact_for(item)
    university.admission_url = contact["admission_url"]
    university.admission_email = contact["admission_email"]
    university.admission_phone = contact["admission_phone"]
    university.admissions_office = contact["admissions_office"]
    university.is_core = is_core
    db.query(AdmissionSchedule).filter(AdmissionSchedule.university_id == university.id).delete()
    for year, month, reg, deadline, exam, reminder in schedules_for(item["fields"]):
        db.add(AdmissionSchedule(university_id=university.id, year=year, month=month, registration_time=reg, material_deadline=deadline, exam_time=exam, reminder=reminder))


def seed_data(db: Session):
    ensure_columns(db)
    for code, name, price, days, desc in PLAN_DATA:
        plan = db.query(MembershipPlan).filter(MembershipPlan.code == code).first()
        if not plan:
            plan = MembershipPlan(code=code)
            db.add(plan)
        plan.name, plan.price, plan.duration_days, plan.description = name, price, days, desc
        plan.is_active = code not in {"monthly", "yearly", "pro_trial"}
        plan.features = json.dumps(
            {
                "international_core": True,
                "full_library": code not in {"free"},
                "report_export": code not in {"free"},
                "one_on_one_expert": code not in {"free"},
                "smart_timeline": code in {"vip_year", "vip_three_year", "yearly", "lifetime", "pro_trial"},
                "pro_trial": code == "pro_trial",
            },
            ensure_ascii=False,
        )
        perm = db.query(PermissionConfig).filter(PermissionConfig.plan_code == code).first()
        if not perm:
            db.add(PermissionConfig(plan_code=code, config=plan.features))
        else:
            perm.config = plan.features
    if db.query(Tenant).count() == 0:
        tenant = Tenant(name="SaaS Pro 管理后台", tenant_type="platform")
        db.add(tenant); db.flush()
        db.add(User(tenant_id=tenant.id, email="admin@example.com", name="平台管理员", password_hash=hash_password("admin123456"), role="admin", plan_code="lifetime"))
        demo = Tenant(name="国际生规划示范机构", tenant_type="agency")
        db.add(demo); db.flush()
        db.add(User(tenant_id=demo.id, email="demo@example.com", name="示范顾问", password_hash=hash_password("demo123456"), role="member", plan_code="free"))
    for item in UNIVERSITIES:
        upsert_university(db, item, True)
    for old_name, item in LEGACY_FREE_REPLACEMENTS.items():
        legacy = db.query(University).filter(University.name == old_name).first()
        if legacy and not db.query(University).filter(University.name == item["name"]).first():
            legacy.name = item["name"]
            db.flush()
        if legacy:
            upsert_university(db, item, False)
    for item in FREE_UNIVERSITIES:
        upsert_university(db, item, False)
    if db.query(RechargeCode).count() == 0:
        for plan_code, days in [
            ("vip_month", 30),
            ("vip_year", 365),
            ("vip_three_year", 1095),
            ("monthly", 30),
            ("yearly", 365),
            ("lifetime", 36500),
        ]:
            db.add(RechargeCode(code=f"PRO-{plan_code.upper()}-{secrets.token_hex(3).upper()}", plan_code=plan_code, duration_days=days))
    db.commit()
