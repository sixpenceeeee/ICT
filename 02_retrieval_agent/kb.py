# -*- coding: utf-8 -*-
"""
kb.py —— 本地知识库：加载 → 切块 → 建索引 → 检索（零第三方依赖）

为什么自己写而不装向量库？
因为知识库只有几千字的时候，向量检索并不比关键词检索更准，但会多出三个麻烦：
要装包、要调 embedding 接口、要花钱。先用最简单的办法跑通，量大了再换。

检索算法用 BM25 —— 搜索引擎的经典算法，核心思想就一句话：
"一个词在片段里出现得越多、在整个知识库里越罕见，这个片段就越相关。"
中文没有空格分词，所以这里把相邻两个字组成一个 token（字符二元组），
"欧姆定律" 会变成 欧姆 / 姆定 / 定律 三个 token，效果够用且不依赖分词库。
"""

import math
import os
import re

KNOWLEDGE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "knowledge")

# 切块的目标长度（字符）。太短则上下文不足，太长则检索精度下降。
CHUNK_SIZE = 420


# ============ 1. 分词 ============

def tokenize(text):
    """把一段中文切成 token：英文数字按词切，中文按相邻两字切。"""
    text = text.lower()

    tokens = re.findall(r"[a-z0-9]+", text)

    # 只保留汉字，其它字符（标点、空格、符号）当分隔符
    cn_only = re.sub(r"[^\u4e00-\u9fff]+", " ", text)
    for seg in cn_only.split():
        if len(seg) == 1:
            tokens.append(seg)
        for i in range(len(seg) - 1):
            tokens.append(seg[i:i + 2])

    return tokens


# ============ 2. 加载 + 切块 ============

def parse_markdown(path):
    """解析一个 md 文件，返回 (元信息, 章节列表)。

    文件格式约定：
        ---
        类别: 课标依据
        来源: 人教版九年级物理
        ---
        ## 章节名
        正文……
    """
    with open(path, "r", encoding="utf-8") as f:
        raw = f.read()

    meta = {}
    body = raw
    fm = re.match(r"^---\s*\n(.*?)\n---\s*\n", raw, re.S)
    if fm:
        for line in fm.group(1).splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                meta[k.strip()] = v.strip()
        body = raw[fm.end():]

    sections = []
    parts = re.split(r"^##\s+", body, flags=re.M)
    for part in parts[1:]:
        lines = part.strip().split("\n", 1)
        title = lines[0].strip()
        content = lines[1].strip() if len(lines) > 1 else ""
        if content:
            sections.append((title, content))

    return meta, sections


def split_long(title, content, size=CHUNK_SIZE):
    """章节太长就按自然段合并着切，避免把一句话劈开。"""
    if len(content) <= size:
        return [(title, content)]

    pieces, buf = [], ""
    for para in content.split("\n\n"):
        para = para.strip()
        if not para:
            continue
        if len(buf) + len(para) + 2 <= size:
            buf = (buf + "\n\n" + para).strip()
        else:
            if buf:
                pieces.append(buf)
            buf = para
    if buf:
        pieces.append(buf)

    if len(pieces) == 1:
        return [(title, pieces[0])]

    return [("%s（%d/%d）" % (title, i, len(pieces)), p) for i, p in enumerate(pieces, 1)]


def load_knowledge():
    """把 knowledge/ 下所有 md 读进来，切成片段，每个片段带上出处。"""
    chunks = []

    for filename in sorted(os.listdir(KNOWLEDGE_DIR)):
        if not filename.endswith(".md"):
            continue

        path = os.path.join(KNOWLEDGE_DIR, filename)
        meta, sections = parse_markdown(path)

        for title, content in sections:
            for sub_title, text in split_long(title, content):
                chunks.append({
                    "id": "K%02d" % (len(chunks) + 1),
                    "文件": filename,
                    "类别": meta.get("类别", "未分类"),
                    "主题": meta.get("主题", "通用"),
                    "来源": meta.get("来源", filename),
                    "章节": sub_title,
                    "内容": text,
                    "tokens": tokenize(sub_title + " " + text),
                })

    return chunks


# ============ 3. BM25 检索 ============

class BM25:
    """标准 BM25 实现，约 40 行。"""

    def __init__(self, chunks, k1=1.5, b=0.75):
        self.chunks = chunks
        self.k1 = k1
        self.b = b

        self.N = len(chunks)
        self.doc_len = [len(c["tokens"]) for c in chunks]
        self.avg_len = sum(self.doc_len) / max(self.N, 1)

        # 每个 token 出现在多少个片段里（算 IDF 用）
        self.df = {}
        for c in chunks:
            for t in set(c["tokens"]):
                self.df[t] = self.df.get(t, 0) + 1

        # 预先统计每个片段的词频，避免每次查询都重算
        self.tf = []
        for c in chunks:
            counter = {}
            for t in c["tokens"]:
                counter[t] = counter.get(t, 0) + 1
            self.tf.append(counter)

    def idf(self, token):
        df = self.df.get(token, 0)
        # +0.5 平滑，防止除零；加 1 保证 IDF 非负
        return math.log(1 + (self.N - df + 0.5) / (df + 0.5))

    def score(self, query_tokens):
        """返回每条知识片段相对这个查询的得分列表。"""
        scores = [0.0] * self.N
        for token in query_tokens:
            if token not in self.df:
                continue
            idf = self.idf(token)
            for i in range(self.N):
                f = self.tf[i].get(token, 0)
                if f == 0:
                    continue
                denom = f + self.k1 * (1 - self.b + self.b * self.doc_len[i] / self.avg_len)
                scores[i] += idf * f * (self.k1 + 1) / denom
        return scores


# ============ 4. 对外接口 ============

class KnowledgeBase:
    """多主题知识库。

    为什么要按主题分开建索引：
    知识库里现在同时有"电路"和"浮力"两套材料。如果混在一起检索，
    浮力实验的查询会命中"实验规范""学生易错点"这类两套材料都有的通用片段，
    知识包就会被另一个实验的内容污染，生成出来的页面会半电学半浮力。
    所以每个主题各自一份 BM25 索引，检索前先按主题过滤。
    """

    def __init__(self):
        self.chunks = load_knowledge()

        # 全库索引：认不出主题时的兜底
        self.bm25 = BM25(self.chunks)

        # 每个主题一份独立索引
        self.by_topic = {}
        for chunk in self.chunks:
            self.by_topic.setdefault(chunk["主题"], []).append(chunk)
        self.index = {t: BM25(cs) for t, cs in self.by_topic.items()}

    def topics(self):
        return sorted(self.by_topic.keys())

    def search(self, query, top_k=8, topic=None):
        """单次检索，返回 [(片段dict, 得分)]，按分数从高到低。

        topic 给定时只在该主题的知识里检索；主题不存在则回落到全库。
        """
        if topic and topic in self.index:
            chunks, bm25 = self.by_topic[topic], self.index[topic]
        else:
            chunks, bm25 = self.chunks, self.bm25

        scores = bm25.score(tokenize(query))
        ranked = sorted(zip(chunks, scores), key=lambda x: x[1], reverse=True)
        return [(c, s) for c, s in ranked[:top_k]]


if __name__ == "__main__":
    # 直接运行这个文件可以做一次自检：看看切块结果和检索效果
    kb = KnowledgeBase()
    print("知识库共 %d 个片段，主题：%s\n" % (len(kb.chunks), "、".join(kb.topics())))
    for c in kb.chunks:
        print("%s [%s][%s] %s / %s（%d 字）"
              % (c["id"], c["主题"], c["类别"], c["文件"], c["章节"], len(c["内容"])))

    for topic, q in (("电路", "电阻一定时电流与电压成正比"),
                     ("浮力", "浮力大小与排开液体的体积有关")):
        print("\n试检索［%s］%s" % (topic, q))
        for c, s in kb.search(q, top_k=3, topic=topic):
            print("  %.3f  %s  %s" % (s, c["id"], c["章节"]))
