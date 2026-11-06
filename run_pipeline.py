# -*- coding: utf-8 -*-
"""
run_pipeline.py —— 编排器（第五个角色，也是唯一不生产内容的那一个）

它只做三件事：
    ① 按顺序驱动四个角色，把上一个的产物路径喂给下一个
    ② 审查不通过时，把修改意见带回生成环节重做（最多 N 轮），并留下历史最好版本
    ③ 把整条链路的耗时、来源、分数、文件写成一份可回放的运行日志

为什么用子进程调用，而不是 import 进来直接调函数？
    01 和 03 目录里各有一个 prompts.py，import 会互相覆盖（这个坑已经踩过一次）。
    子进程天然隔离，而且正好模拟"每个角色是独立服务"的形态——
    以后搬到 AgentArts，每个节点就是一次独立调用，行为和本地一致。

用法：
    python run_pipeline.py                                    # 用内置示例需求跑全链路
    python run_pipeline.py "生成一个浮力实验"                   # 提自己的需求
    python run_pipeline.py "..." --max-rounds 3 --open         # 最多返工 3 轮，最后打开结果
    python run_pipeline.py "..." --template-only               # 不调模型，只验证链路通不通
"""

import argparse
import glob
import json
import os
import shutil
import subprocess
import sys
import time
import zipfile
from datetime import datetime

BASE = os.path.dirname(os.path.abspath(__file__))
RUNS_DIR = os.path.join(BASE, "runs")
PY = sys.executable

STAGES = {
    "需求理解": os.path.join(BASE, "01_single_agent"),
    "知识检索": os.path.join(BASE, "02_retrieval_agent"),
    "工具生成": os.path.join(BASE, "03_generator_agent"),
    "质量审查": os.path.join(BASE, "04_review_agent"),
}

DEMO_INPUT = "生成一个可以改变电阻和电压的电路实验"

# 子进程强制 UTF-8：Windows 下管道默认是 GBK，不指定会乱码或解码报错
CHILD_ENV = dict(os.environ)
CHILD_ENV["PYTHONIOENCODING"] = "utf-8"
CHILD_ENV["PYTHONUNBUFFERED"] = "1"

STAGE_TIMEOUT = 900          # 单阶段上限 15 分钟（生成 HTML 是最慢的一步）


class StageError(Exception):
    """某个阶段执行失败。编排器不吞异常，但会把它写进日志再退出。"""


# ============ 工具函数 ============

def snapshot(folder, pattern):
    """记录目录里匹配文件的当前修改时间，用于事后判断"这次新增/覆盖了哪个"。"""
    return {p: os.path.getmtime(p) for p in glob.glob(os.path.join(folder, pattern))}


def diff_new(folder, pattern, before):
    """找出这次运行产生（新增或被覆盖）的文件，取最新的一个。"""
    now = snapshot(folder, pattern)
    changed = [p for p, m in now.items() if p not in before or m > before[p] + 0.001]
    return max(changed, key=os.path.getmtime) if changed else None


def copy_assets(html_path, dst_dir):
    """把平台外壳资源复制到 html 旁边。

    页面通过 <link href="frame.css"> 引用样式，只拷 html 不拷 css，
    拿到手的人打开会是一个没有页眉颜色、没有布局的裸页面。
    """
    src_dir = os.path.dirname(os.path.abspath(html_path))
    for res in ("frame.css", "exp.css", "logo.png"):
        src = os.path.join(src_dir, res)
        if not os.path.exists(src):
            src = os.path.join(BASE, "frame", res)
        if os.path.exists(src):
            shutil.copy2(src, os.path.join(dst_dir, res))


def show_output(text, verbose):
    """把子进程的输出缩进打印。默认只截 30 行，够看清结论；--verbose 全量。"""
    lines = [l.rstrip() for l in (text or "").strip().splitlines() if l.strip()]
    if not lines:
        return
    limit = 400 if verbose else 30
    for line in lines[:limit]:
        print("    " + line)
    if len(lines) > limit:
        print("    …（已省略 %d 行，加 --verbose 看全量）" % (len(lines) - limit))


def read_api_key():
    """检查 01 目录下的 .env 有没有真的配 key（没配就只能跑模板）。"""
    path = os.path.join(BASE, "01_single_agent", ".env")
    if not os.path.exists(path):
        return ""
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line.startswith("LLM_API_KEY="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    return ""


# ============ 单个阶段 ============

def run_stage(label, stage_name, script, argv, watch_pattern, log, verbose, timeout=STAGE_TIMEOUT):
    """跑一个角色，返回 (产物绝对路径, 耗时秒)。

    失败就抛 StageError —— 编排器最忌讳"某个环节悄悄失败然后继续往下跑"，
    那样最后交付的东西看着正常，其实整条链路早就断了。
    """
    print("\n%s %s" % (label, stage_name))
    folder = os.path.join(STAGES[stage_name], "output")
    os.makedirs(folder, exist_ok=True)

    before = snapshot(folder, watch_pattern)
    started = time.time()

    try:
        proc = subprocess.run(
            [PY, script] + argv,
            cwd=STAGES[stage_name],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=timeout, env=CHILD_ENV,
        )
    except subprocess.TimeoutExpired:
        raise StageError("「%s」超时（超过 %d 秒）" % (stage_name, timeout))

    elapsed = round(time.time() - started, 1)
    combined = (proc.stdout or "") + (("\n" + proc.stderr) if (proc.stderr or "").strip() else "")
    show_output(combined, verbose)

    if proc.returncode != 0:
        raise StageError("「%s」执行失败（退出码 %d）：\n%s"
                         % (stage_name, proc.returncode, (proc.stderr or proc.stdout or "")[-800:]))

    product = diff_new(folder, watch_pattern, before)
    if not product:
        raise StageError("「%s」跑完了，但没有找到产物（要找 %s）。请检查该模块是否正常写盘。"
                         % (stage_name, watch_pattern))

    print("    完成：%s  耗时 %.1fs" % (os.path.basename(product), elapsed))
    log["阶段"].append({
        "阶段": stage_name,
        "命令": "python %s %s" % (os.path.basename(script), " ".join(argv)),
        "耗时秒": elapsed,
        "退出码": proc.returncode,
        "产物": os.path.basename(product),
    })
    return product, elapsed


# ============ 主流程 ============

def build_argparser():
    p = argparse.ArgumentParser(description="四角色流水线编排器")
    p.add_argument("text", nargs="*", help="一句教学需求（不填用内置示例）")
    p.add_argument("--max-rounds", type=int, default=2, help="生成+审查最多几轮，默认 2")
    p.add_argument("--template-only", action="store_true", help="不调模型，只用内置模板（验证链路用）")
    p.add_argument("--open", action="store_true", help="结束后用浏览器打开最终产物")
    p.add_argument("--verbose", action="store_true", help="打印每个角色的完整输出")
    p.add_argument("--run-dir", help="指定运行目录（默认 runs/时间戳）")
    return p


def main():
    args = build_argparser().parse_args()
    user_input = " ".join(args.text).strip() or DEMO_INPUT

    run_id = datetime.now().strftime("%Y%m%d-%H%M%S")
    run_dir = args.run_dir or os.path.join(RUNS_DIR, run_id)
    os.makedirs(run_dir, exist_ok=True)

    with open(os.path.join(run_dir, "输入.txt"), "w", encoding="utf-8") as f:
        f.write(user_input + "\n")

    key = read_api_key()
    log = {
        "运行ID": run_id,
        "开始时间": datetime.now().isoformat(timespec="seconds"),
        "输入": user_input,
        "模型接入": "已配置" if key else "未配置（走内置模板/假数据）",
        "最大轮次": args.max_rounds,
        "阶段": [],
        "轮次": [],
        "结论": "",
        "交付文件": "",
    }

    print("=" * 64)
    print("教学资源生成流水线    运行 %s" % run_id)
    print("需求：%s" % user_input)
    print("模型：%s" % log["模型接入"])
    if not key and not args.template_only:
        print("警告：没有检测到 API Key，本次只能验证链路，内容不会由模型生成")
    print("=" * 64)

    started_all = time.time()

    # ---------- 阶段 1：需求理解 ----------
    req_path, _ = run_stage("[1/3]", "需求理解", "agent.py", [user_input],
                            "需求_*.json", log, args.verbose)
    shutil.copy2(req_path, os.path.join(run_dir, "01_需求.json"))

    # ---------- 阶段 2：知识检索 ----------
    kb_path, _ = run_stage("[2/3]", "知识检索", "retrieval_agent.py", ["--req", req_path],
                           "知识包_*.json", log, args.verbose)
    shutil.copy2(kb_path, os.path.join(run_dir, "02_知识包.json"))

    # 知识覆盖不足要显式告警：知识库目前覆盖"电路"和"浮力"两个主题，
    # 换到第三个主题时检索几乎命中不到东西，生成质量会明显下降。这种话必须说在前面。
    with open(kb_path, "r", encoding="utf-8") as f:
        pack_doc = json.load(f)
    pack = pack_doc.get("knowledge_pack", {})
    topic = pack_doc.get("主题") or "未识别"
    chunk_count = sum(len(v) for v in pack.values())
    log["知识主题"] = topic
    log["知识片段数"] = chunk_count
    if chunk_count < 4:
        print("\n警告：只检索到 %d 个知识片段（主题：%s）。"
              "知识库目前只覆盖电路与浮力两个实验，其它主题需要先补充知识文件。"
              "这不是模型的问题，是知识库没料。" % (chunk_count, topic))

    # ---------- 阶段 3+4：生成 → 审查 → 返工 ----------
    best = None
    feedback = None
    for rnd in range(1, args.max_rounds + 1):
        gen_argv = ["--req", req_path, "--kb", kb_path]
        if feedback:
            gen_argv += ["--feedback", feedback]
        if args.template_only:
            gen_argv.append("--template-only")

        html_path, gen_cost = run_stage("[3/3] 第 %d 轮" % rnd, "工具生成", "generator_agent.py",
                                        gen_argv, "教学资源_*.html", log, args.verbose)
        shutil.copy2(html_path, os.path.join(run_dir, "%02d_草稿_模型输出.html" % rnd))
        copy_assets(html_path, run_dir)

        # 生成侧自己的校验结果（来源=模板说明模型输出没通过，是重要信号）
        meta_path = os.path.splitext(html_path)[0] + ".meta.json"
        source = "-"
        if os.path.exists(meta_path):
            with open(meta_path, "r", encoding="utf-8") as f:
                source = json.load(f).get("生成信息", {}).get("来源", "-")

        report_path, rev_cost = run_stage("      → 第 %d 轮" % rnd, "质量审查",
                                          "reviewer.py", ["--html", html_path, "--req", req_path],
                                          "审查报告_*.json", log, args.verbose)
        with open(report_path, "r", encoding="utf-8") as f:
            report = json.load(f)
        shutil.copy2(report_path, os.path.join(run_dir, "%02d_审查报告.json" % rnd))

        round_info = {
            "轮次": rnd,
            "生成来源": source,
            "字符数": os.path.getsize(html_path),
            "总分": report["总分"],
            "结论": report["结论"],
            "严重问题数": report["严重问题数"],
            "生成耗时秒": gen_cost,
            "审查耗时秒": rev_cost,
            "HTML": html_path,
            "报告": report_path,
        }
        log["轮次"].append(round_info)

        # 保留历史最高分版本：第 2 轮不一定比第 1 轮好，最后交付的应该是最好那版
        if best is None or report["总分"] > best["总分"]:
            best = dict(round_info, 问题清单=report["问题清单"])

        print("\n    第 %d 轮结果：%s  %.1f 分（严重问题 %d 项）  来源=%s"
              % (rnd, report["结论"], report["总分"], report["严重问题数"], source))

        if report["结论"] == "通过":
            print("    审查通过，停止返工")
            break
        if rnd == args.max_rounds:
            print("    已达最大轮次，交付历史最好版本")
            break

        feedback = report["修改意见"]
        print("    未通过，带着 %d 条意见返工" % len(report["问题清单"]))

    # ---------- 收尾 ----------
    # 交付物是一个完整目录（html + frame.css + exp.css + logo.png + zip）：
    # 平台外壳是外链样式，只发 html 别人打开会没样式，所以必须连资源一起带走。
    final_html = os.path.join(run_dir, "交付_教学资源.html")
    shutil.copy2(best["HTML"], final_html)
    copy_assets(best["HTML"], run_dir)
    final_zip = os.path.join(run_dir, "交付_教学资源.zip")
    with zipfile.ZipFile(final_zip, "w", zipfile.ZIP_DEFLATED) as z:
        z.write(final_html, "交付_教学资源.html")
        for res in ("frame.css", "exp.css", "logo.png"):
            p_res = os.path.join(run_dir, res)
            if os.path.exists(p_res):
                z.write(p_res, res)

    # 写回 03 的 output，保证那个目录里留的永远是最好版本，而不是最后一版
    canonical = best["HTML"]
    shutil.copy2(final_html, canonical)

    total_cost = round(time.time() - started_all, 1)
    log["结束时间"] = datetime.now().isoformat(timespec="seconds")
    log["总耗时秒"] = total_cost
    log["最终总分"] = best["总分"]
    log["结论"] = best["结论"]
    log["交付文件"] = final_html
    log["交付压缩包"] = final_zip
    log["交付说明"] = ("模型生成" if best["生成来源"] == "大模型" else "含兜底模板：%s" % best["生成来源"])

    with open(os.path.join(run_dir, "运行日志.json"), "w", encoding="utf-8") as f:
        json.dump(log, f, ensure_ascii=False, indent=2)
    write_markdown(os.path.join(run_dir, "运行报告.md"), log, best)

    print("\n" + "=" * 64)
    print("完成    %s    总分 %.1f / 100    共 %d 轮    总耗时 %.1fs"
          % (best["结论"], best["总分"], len(log["轮次"]), total_cost))
    print("交付    %s" % final_html)
    print("日志    %s" % os.path.join(run_dir, "运行日志.json"))
    print("报告    %s" % os.path.join(run_dir, "运行报告.md"))
    print("=" * 64)

    if best["问题清单"]:
        print("\n仍需人工确认的问题：")
        for item in best["问题清单"][:5]:
            print("  · [%s] %s：%s" % (item["维度"], item["检查项"], item["说明"]))

    if args.open and os.name == "nt":
        os.startfile(final_html)

    return 0 if best["结论"] == "通过" else 1


def write_markdown(path, log, best):
    """写一份人能直接看的运行报告——录 Demo、写答辩材料都用得上。"""
    lines = [
        "# 教学资源生成运行报告",
        "",
        "- 运行 ID：%s" % log["运行ID"],
        "- 输入需求：%s" % log["输入"],
        "- 模型接入：%s" % log["模型接入"],
        "- 结论：**%s**，总分 %.1f / 100" % (log["结论"], log["最终总分"]),
        "- 总耗时：%.1fs，共 %d 轮" % (log["总耗时秒"], len(log["轮次"])),
        "",
        "## 阶段耗时",
        "",
        "| 阶段 | 耗时 | 产物 |",
        "|---|---|---|",
    ]
    for s in log["阶段"]:
        lines.append("| %s | %.1fs | %s |" % (s["阶段"].strip(), s["耗时秒"], s["产物"]))

    lines += [
        "",
        "## 各轮审查结果",
        "",
        "| 轮次 | 生成来源 | 字符数 | 总分 | 结论 | 严重问题 |",
        "|---|---|---|---|---|---|",
    ]
    for r in log["轮次"]:
        lines.append("| %d | %s | %d | %.1f | %s | %d |"
                     % (r["轮次"], r["生成来源"], r["字符数"], r["总分"], r["结论"], r["严重问题数"]))

    lines += ["", "## 交付版本说明", "",
              "- 交付的是第 %d 轮（历史最高分 %.1f）" % (best["轮次"], best["总分"]),
              "- 生成来源：%s" % best["生成来源"],
              "- 文件：`交付_教学资源.html`（同目录下另有每轮草稿和对应审查报告）"]

    if best["问题清单"]:
        lines += ["", "## 仍需人工确认", ""]
        for item in best["问题清单"]:
            lines.append("- [%s] %s：%s" % (item["维度"], item["检查项"], item["说明"]))
            if item.get("建议"):
                lines.append("  - 建议：%s" % item["建议"])

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    try:
        sys.exit(main())
    except StageError as exc:
        print("\n流水线中止：%s" % exc)
        sys.exit(2)
