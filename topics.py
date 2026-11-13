# -*- coding: utf-8 -*-
"""
topics.py —— 实验主题配置表（新增实验只改这一个文件）

这套系统里凡是被"某个具体实验"绑定的知识，都集中在这里：
    关键词    —— 从需求文字里认出这是哪个实验
    检索侧重  —— 把"规范 / 安全 / 交互"这些通用类别翻译成这个实验的行话
    单位组    —— 审查时该在页面上看到哪些单位
    数值上限  —— 超过就有安全隐患的阈值
    公式示例  —— 写进生成提示词与审查建议里的标准写法

加第三个实验（比如"大气压"）时要做的事只有两件：
    1. 在 PROFILES 里加一条
    2. 在 02_retrieval_agent/knowledge/ 放一份带「主题: 大气压」的 md
其余代码一律不动。
"""

PROFILES = {
    "电路": {
        "学科": "物理",
        "关键词": ["电路", "电阻", "电压", "电流", "欧姆", "变阻器", "伏安", "电表"],
        "检索侧重": [
            "实验 规范 接线 电表 滑动变阻器",
            "安全 电压 范围 准确性 短路",
            "交互 滑块 图像 学生 易错",
        ],
        "单位组": [
            ("电压", ["V", "伏"]),
            ("电阻", ["Ω", "欧"]),
            ("电流", ["A", "安"]),
        ],
        "数值上限": [
            {"单位": "V", "名称": "电压", "上限": 36},
            {"单位": "A", "名称": "电流", "上限": 10},
        ],
        "核心公式": "I = U / R",
        "公式示例": "I = U / R = 3.0 V ÷ 20 Ω = 0.150 A；"
                    "串联电路写成 I = U / (R + R滑) = 6.0 V ÷ (10 Ω + 10 Ω) = 0.300 A",
    },

    "密度测量": {
        "学科": "物理",
        # 只用"天平/量筒/排水法"这类器材词：单写"密度"会把浮力、液体压强页抢过来
        "关键词": ["密度测量", "测量密度", "测密度", "天平", "量筒", "排水法"],
        "检索侧重": [
            "实验 规范 器材 托盘天平 砝码 量筒 排水法 读数",
            "安全 读数 视线 凹液面 镊子 砝码 量柄",
            "交互 滑块 记录 单位换算 易错",
        ],
        "单位组": [
            ("质量", ["g", "克", "kg"]),
            ("体积", ["cm³", "cm3", "mL", "m³"]),
            ("密度", ["g/cm³", "g/cm3", "kg/m³"]),
        ],
        "数值上限": [],
        "核心公式": "ρ = m / V",
        "公式示例": "ρ = m ÷ V = 20 g ÷ 8 cm³ = 2.5 g/cm³（1 g/cm³ = 1000 kg/m³）",
    },

    "浮力": {
        "学科": "物理",
        "关键词": ["浮力", "阿基米德", "排开", "液体密度", "浮沉", "溢水", "浸没"],
        "检索侧重": [
            "实验 规范 器材 弹簧测力计 溢水杯 步骤",
            "安全 液体 器皿 量程 数值 准确",
            "交互 滑块 图像 学生 易错",
        ],
        "单位组": [
            ("力", ["N", "牛"]),
            ("密度", ["kg/m³", "kg/m3", "g/cm³", "g/cm3"]),
            ("体积", ["m³", "m3", "cm³", "mL"]),
        ],
        # 课堂器材是 0~5 N 的测力计，页面上的力不该超过 20 N
        # 课堂器材是 0~5 N 的测力计，页面上的力不该超过 20 N
        "数值上限": [
            {"单位": "N", "名称": "力", "上限": 20},
        ],
        "核心公式": "F浮 = ρ液 g V排",
        "公式示例": "F浮 = ρ液 g V排 = 1000 kg/m³ × 9.8 N/kg × 0.0002 m³ = 1.96 N"
                    "（求解器取 g=9.8 N/kg，体积先换算成 m³）",
    },
}

# 补充主题配置由 02_retrieval_agent/seed/build_topics.py 生成，
# 与知识库共用同一份源数据（seed/*_kb.py），避免关键词和公式两处漂移。
try:
    from topics_extra import EXTRA_PROFILES

    PROFILES.update(EXTRA_PROFILES)
except ImportError:  # 只拿 topics.py 单独跑时（例如拷到别的目录）也要能用
    EXTRA_PROFILES = {}


# 认不出主题时的兜底：不限定主题，检索全部知识，提示词用通用写法
GENERIC = {
    "关键词": [],
    "检索侧重": [
        "实验 规范 器材 步骤 操作",
        "安全 注意事项 范围 准确",
        "交互 滑块 图像 学生 易错",
    ],
    "单位组": [],
    "数值上限": [],
    "核心公式": "",
    "公式示例": "核心公式 = 数值代入 = 结果（每个量都要带单位）",
}


# 单位的几种写法：审查时要认全，不能因为写出"伏"就判成缺单位
UNIT_ALIASES = {
    "V": ["V", "伏"],
    "A": ["A", "安"],
    "N": ["N", "牛"],
    "Ω": ["Ω", "欧"],
}


def unit_pattern(unit):
    """返回能匹配该单位及其别名的正则片段。"""
    aliases = UNIT_ALIASES.get(unit, [unit])
    return "(?:%s)" % "|".join(aliases)


def detect_topic(text, subject=None, *, title=""):
    """从需求文字里判断实验主题，可选按学科过滤，认不出返回 None。

    只做关键词计分，不调模型：这一步要的是"稳定且可解释"，
    评委问"你怎么知道这是浮力实验"时，能直接指着关键词表回答。
    """
    text = (text or "").lower()
    subject = (subject or "").strip()
    subject = {"物理学": "物理", "生物学": "生物"}.get(subject, subject)
    if subject in ("数学", "物理") and title:
        # Prefer a named topic before scoring terms mentioned as background.
        named = [name for name, profile in PROFILES.items()
                 if profile.get("学科") == subject and len(name) >= 4 and name in title]
        if named:
            return max(named, key=len)
        title_topic = detect_topic(title, subject)
        if title_topic:
            return title_topic
    best, best_score = None, 0
    for name, p in PROFILES.items():
        if subject and p.get("学科") and p["学科"] != subject:
            continue
        # 按关键词长度加权：命中的词越长越具体。
        # 只数个数会让「伏安」和「伏安法」同分，导致「伏安法测电阻」被认成「电路」。
        # 英文缩写（如 Ksp、pH）大小写不应影响主题识别。
        score = sum(len(kw) for kw in p["关键词"] if kw.lower() in text)
        if score > best_score:
            best, best_score = name, score
    return best


def profile_of(topic):
    """取主题配置，未知主题回落到通用配置。"""
    return PROFILES.get(topic, GENERIC)


def all_topics():
    return list(PROFILES.keys())
