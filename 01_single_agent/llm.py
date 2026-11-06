# -*- coding: utf-8 -*-
"""
llm.py —— 大模型调用的统一封装（零第三方依赖，只用 Python 自带的库）

这个文件只做一件事：把"一段对话"发给大模型，把"模型的回复"拿回来。
不管你后面用的是 DeepSeek、GLM 还是华为云 MaaS，只要它兼容 OpenAI 的接口格式，
改一下 .env 里的三个值就能切换，业务代码一个字都不用动。
"""

import json
import os
import sys
import urllib.error
import urllib.request

# ============ 1. 配置 ============

# 没有配 API key 时，用这段假数据让流程依然能跑通（方便你先看懂结构）
MOCK_REPLY = """{
  "学科": "物理",
  "年级": "初中九年级",
  "实验名称": "欧姆定律",
  "实验主题": "欧姆定律：电压、电阻与电流的关系",
  "学习目标": [
    "理解电压是推动电流的原因，电阻是对电流的阻碍",
    "能通过调节滑动变阻器改变电阻，观察电流变化",
    "能用 I=U/R 解释观察到的现象"
  ],
  "核心变量": [
    {"名称": "电压 U", "范围": "1~6 V", "单位": "V"},
    {"名称": "电阻 R", "范围": "5~50 Ω", "单位": "Ω"}
  ],
  "交互要求": [
    "拖动滑块改变电压和电阻，实时刷新电流数值",
    "用柱状图直观对比电流大小",
    "电流过大时给出安全提示"
  ],
  "技术要点": "单文件 HTML，用原生 JS 计算并绘制 Canvas 图表，不依赖任何 CDN",
  "风险点": ["电压过高可能烧毁元件，需要上限提示", "避免出现真实导线连接的操作引导"]
}"""


def load_env(path=None):
    """读取同目录下的 .env 文件，把里面的键值对塞进环境变量。

    不装 python-dotenv 也能用，就十几行。已存在的环境变量优先级更高。
    """
    if path is None:
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if not os.path.exists(path):
        return
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            # 不覆盖外部已经设置好的环境变量
            os.environ.setdefault(key, value)


def get_config():
    """从环境变量里读出三样东西：密钥、接口地址、模型名。"""
    return {
        "api_key": os.getenv("LLM_API_KEY", "").strip(),
        # 默认用 DeepSeek 做本地调试（便宜、稳定），换成华为云 MaaS 只改这里
        "base_url": os.getenv("LLM_BASE_URL", "https://api.deepseek.com/v1").rstrip("/"),
        "model": os.getenv("LLM_MODEL", "deepseek-chat").strip(),
    }


# ============ 2. 核心：发一次 HTTP 请求 ============

def call_llm(messages, temperature=0.3, timeout=120, max_tokens=None):
    """把 messages 发给大模型，返回 (文本结果, 是否是假数据)。

    messages 是一个列表，格式就是 OpenAI 的标准格式：
        [{"role": "system", "content": "你是..."},
         {"role": "user",   "content": "帮我..."}]

    max_tokens 一定要在生成大段内容（例如整个 HTML）时显式给足。
    不传的话走平台默认值（DeepSeek 是 4096），一个完整教学页面很容易被截断，
    表现就是"输出到一半没了"，然后校验报"结尾不是 </html>"。
    """
    cfg = get_config()

    # 没配 key → 走假数据模式，保证第一次运行能看到完整效果
    if not cfg["api_key"]:
        return MOCK_REPLY, True

    # 准备请求体：模型名 / 对话内容 / 随机性
    payload = {
        "model": cfg["model"],
        "messages": messages,
        "temperature": temperature,
    }
    if max_tokens:
        payload["max_tokens"] = max_tokens

    req = urllib.request.Request(
        url=cfg["base_url"] + "/chat/completions",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer " + cfg["api_key"],
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "ignore")[:500]
        raise RuntimeError(
            "调用失败，HTTP %s\n返回内容：%s\n\n"
            "常见原因：key 不对 / 模型名写错 / 这个模型没开通 / base_url 少了 /v1" % (e.code, detail)
        )
    except urllib.error.URLError as e:
        raise RuntimeError("网络连不上：%s\n检查一下 base_url，或者有没有开代理" % e.reason)

    # 标准的 OpenAI 返回结构里，正文在 choices[0].message.content
    choice = body["choices"][0]
    content = choice["message"]["content"]

    # 截断是生成类任务最常见的静默失败：接口不报错，但内容只出来一半。
    # 必须把 finish_reason 打出来，否则你只会看到"校验不通过"却不知道为什么。
    if choice.get("finish_reason") == "length":
        usage = body.get("usage") or {}
        sys.stderr.write(
            "   [警告] 输出被截断：finish_reason=length，已输出 %d 字符 / %s tokens。\n"
            "          处理办法：调大 max_tokens，或在提示词里压缩篇幅要求。\n"
            % (len(content), usage.get("completion_tokens", "?"))
        )

    return content, False
