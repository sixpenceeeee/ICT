# 单 Agent 最小可运行版本（需求理解 Agent）

这是你参赛项目的第 1 块地基：**一个 Agent = 提示词 + 一次模型调用 + 稳定的输出解析**。
另外三个 Agent（知识检索 / 教学工具生成 / 质量审查）都是照这个模板复制、改提示词。

## 一、文件分工

| 文件 | 作用 | 你以后会改它吗 |
|---|---|---|
| `llm.py` | 把消息发给大模型，拿回文本。屏蔽不同厂商的差异 | 基本不改，只换 `.env` |
| `prompts.py` | 提示词。Agent 的"人格"和"能力"都在这 | **改得最多** |
| `agent.py` | 流程：拼消息 → 调模型 → 抠 JSON → 校验 → 存盘 | 加功能时改 |
| `.env` | 密钥、接口地址、模型名 | 换模型时改 |
| `output/` | 每次运行的 JSON 结果 | — |

## 二、跑起来

```bash
cd 01_single_agent

# 1. 先不填 key 跑一遍，看效果（走内置假数据，0 成本）
python agent.py

# 2. 传自己的需求
python agent.py "生成一个演示大气压存在的实验"

# 3. 换成真实模型
cp .env.example .env        # Windows: copy .env.example .env
# 编辑 .env，填 LLM_API_KEY，再跑一次
```

没装任何第三方库，Python 3.8+ 自带库就够。

## 三、核心逻辑逐行讲解

整个 Agent 只做四件事，`agent.py` 里的 `requirement_agent()` 就是全部：

```python
messages = [
    {"role": "system", "content": REQUIREMENT_SYSTEM_PROMPT},  # 规则：你是谁、输出什么格式
    {"role": "user",   "content": user_input},                 # 老师的原话
]
raw, is_mock = call_llm(messages, temperature=0.2)             # 发出去，拿回字符串
data = extract_json(raw)                                       # 从字符串里抠出 JSON
data, missing = validate(data)                                 # 缺字段就补默认值
```

四个细节，是新手最容易踩坑的地方：

1. **`temperature=0.2`**：需求理解这种"翻译"任务要稳定，不要创造力。生成 HTML 时才调到 0.6~0.8。
2. **`extract_json()`**：模型经常回"好的，结果如下：```json {...}```"。必须清洗，否则 `json.loads` 直接崩。
3. **`validate()`**：模型输出是不可信的。缺字段时给默认值 + 打警告，而不是让整个程序退出。
4. **`meta` 里记耗时和是否假数据**：调试期你能一眼看出是模型慢、还是自己代码慢。

## 四、判断"我写对了吗"

跑完应该看到：

- 终端打印出一张需求清单（学科、年级、变量、交互要求……）
- `output/` 下多一个 JSON 文件，结构和 `prompts.py` 里定义的格式完全一致
- 换一句需求（比如"生成一个浮力实验"），输出字段不变、内容跟着变 —— 说明泛化正常

如果模型返回的字段名变成了英文或者少了字段，**不是代码问题，是提示词问题**：把 `prompts.py` 里的输出格式再强调一遍，或者在 `## 硬性约束` 里加一条"字段名必须与示例完全一致"。

## 五、下一步怎么长成一个"多 Agent"

1. **复制**：新建 `retrieval_agent.py`、`generator_agent.py`、`review_agent.py`，各自一个系统提示词 + 一个函数。
2. **串联**：写一个 `pipeline.py`，把上一个的输出 JSON 直接拼进下一个的 user 消息：

```python
req, _   = requirement_agent(user_input)              # 需求
refs     = retrieval_agent(req)                       # 知识（先返回空列表占位）
html     = generator_agent(req, refs)                 # 生成 HTML
report   = review_agent(req, html)                    # 审查
if not report["通过"] and retry < 2:
    html = generator_agent(req, refs, report["修改意见"])  # 带着意见重写
```

3. **加工具**：当模型需要"真的执行代码 / 读文件"时，才是引入 function calling 或 MCP 的时候。在这之前，纯提示词 + JSON 流转就够了，别提前上框架。

## 六、换华为云 MaaS 时只改三行

打开 MaaS 控制台 → 在线推理 → 找到你开通的模型 → 点"调用说明"，把那三样抄进 `.env`：

```
LLM_BASE_URL=<调用说明里的 base_url，注意结尾不要带 />
LLM_MODEL=<调用说明里的模型名>
LLM_API_KEY=<你的 key>
```

代码一个字都不用改。这就是把调用层单独抽成 `llm.py` 的价值 —— 后面迁到 AgentArts 平台，提示词也是整段复制，逻辑不用重写。
