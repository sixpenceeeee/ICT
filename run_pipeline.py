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


def round_quality_key(row):
    """Rank only pages meeting generation, review, and release gates as approved."""
    failed_count = row.get("失败项数")
    if failed_count is None:
        failed_count = len(row.get("问题清单") or [])
    return (
        1 if is_release_ready(row) else 0,
        1 if row.get("生成契约通过", True) else 0,
        1 if row.get("结论") == "通过" else 0,
        float(row.get("总分", 0) or 0),
        -int(row.get("严重问题数", 0) or 0),
        -int(failed_count or 0),
        int(row.get("轮次", 0) or 0),
    )


def is_release_ready(row):
    return (row.get("结论") == "通过" and row.get("发布状态") == "可发布" and
            row.get("生成契约通过", True))


def is_awaiting_teacher_review(row):
    return (row.get("结论") == "通过" and row.get("发布状态") == "待教师审核" and
            row.get("生成契约通过", True))


def should_replace_best(best, candidate):
    return best is None or round_quality_key(candidate) > round_quality_key(best)

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

    # 知识覆盖不足时在生成前中止，避免用稀薄或跨主题的知识继续产出页面。
    with open(kb_path, "r", encoding="utf-8") as f:
        pack_doc = json.load(f)
    pack = pack_doc.get("knowledge_pack", {})
    topic = pack_doc.get("主题") or "未识别"
    chunk_count = sum(len(v) for v in pack.values())
    log["知识主题"] = topic
    log["知识片段数"] = chunk_count
    if topic == "未识别":
        raise StageError("知识检索没有识别出可用主题，已停止生成，避免跨主题拼接知识。")
    if chunk_count < 4:
        raise StageError("主题「%s」只检索到 %d 个知识片段（至少需要 4 个），已停止生成。"
                         % (topic, chunk_count))

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

        # 生成侧的场景契约校验与诊断。
        meta_path = os.path.splitext(html_path)[0] + ".meta.json"
        source = "-"
        generation_meta = {}
        download_zip_name = ""
        if os.path.exists(meta_path):
            with open(meta_path, "r", encoding="utf-8") as f:
                generation_doc = json.load(f)
                generation_meta = generation_doc.get("生成信息", {})
                source = generation_meta.get("来源", "-")
                download_zip_name = generation_doc.get("压缩包", "")
            shutil.copy2(meta_path, os.path.join(run_dir, "%02d_生成信息.json" % rnd))
        download_zip_path = ""
        if download_zip_name:
            source_zip = os.path.join(os.path.dirname(html_path), download_zip_name)
            if os.path.exists(source_zip):
                download_zip_path = os.path.join(run_dir, download_zip_name)
                shutil.copy2(source_zip, download_zip_path)
        generation_contract_passed = bool(generation_meta.get("生成契约通过", True))
        generation_contract_issues = generation_meta.get("问题") or []

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
            "发布状态": report.get("发布状态", "待验证"),
            "生成契约通过": generation_contract_passed,
            "生成契约问题数": len(generation_contract_issues),
            "生成契约问题": generation_contract_issues,
            "页面下载包": download_zip_path,
            "严重问题数": report["严重问题数"],
            "失败项数": len(report.get("问题清单") or []),
            "生成耗时秒": gen_cost,
            "审查耗时秒": rev_cost,
            "HTML": html_path,
            "报告": report_path,
        }
        log["轮次"].append(round_info)

        # 通过版本优先；未通过时同分优先严重问题更少、失败项更少的版本。
        if should_replace_best(best, round_info):
            best = dict(round_info, 问题清单=report["问题清单"])

        print("\n    第 %d 轮结果：%s  %.1f 分（严重问题 %d 项）  来源=%s"
              % (rnd, report["结论"], report["总分"], report["严重问题数"], source))

        review_candidate = dict(report, 生成契约通过=generation_contract_passed)
        release_ready = is_release_ready(review_candidate)
        if release_ready:
            print("    生成契约与质量审查均通过且可发布，停止返工")
            break
        if is_awaiting_teacher_review(review_candidate):
            print("    技术审查通过，但发布状态待教师审核，停止自动返工")
            break
        if rnd == args.max_rounds:
            print("    已达最大轮次，保存历史最好候选稿（未满足交付门槛）")
            break

        feedback_parts = [report.get("修改意见") or ""]
        if generation_contract_issues:
            feedback_parts.append("生成器契约校验仍未通过，必须一并修复：\n- " +
                                  "\n- ".join(generation_contract_issues))
        feedback = "\n\n".join(part for part in feedback_parts if part)
        print("    未达到交付门槛，带着审查/生成契约意见返工")

    # ---------- 收尾 ----------
    # 交付物是一个完整目录（html + frame.css + exp.css + logo.png + zip）：
    # 平台外壳是外链样式，只发 html 别人打开会没样式，所以必须连资源一起带走。
    is_passed = is_release_ready(best)
    awaiting_teacher = is_awaiting_teacher_review(best)
    # Keep a non-passing best attempt inspectable, but never label it as a
    # deliverable. The run still exits nonzero and the candidate filename is
    # explicit so downstream users cannot mistake a high score for approval.
    final_basename = ("交付_教学资源.html" if is_passed else
                      "待教师审核_暂不可发布.html" if awaiting_teacher else
                      "待修复_不可交付.html")
    final_html = os.path.join(run_dir, final_basename)
    shutil.copy2(best["HTML"], final_html)
    copy_assets(best["HTML"], run_dir)
    zip_basename = ("交付_教学资源.zip" if is_passed else
                    "待教师审核_暂不可发布.zip" if awaiting_teacher else
                    "待修复_不可交付.zip")
    final_zip = os.path.join(run_dir, zip_basename)
    with zipfile.ZipFile(final_zip, "w", zipfile.ZIP_DEFLATED) as z:
        z.write(final_html, os.path.basename(final_html))
        for res in ("frame.css", "exp.css", "logo.png"):
            p_res = os.path.join(run_dir, res)
            if os.path.exists(p_res):
                z.write(p_res, res)
        page_download_zip = best.get("页面下载包")
        if page_download_zip and os.path.exists(page_download_zip):
            z.write(page_download_zip, os.path.basename(page_download_zip))

    # 写回 03 的 output，保证那个目录里留的永远是最好版本，而不是最后一版
    canonical = best["HTML"]
    if is_passed:
        shutil.copy2(final_html, canonical)

    total_cost = round(time.time() - started_all, 1)
    log["结束时间"] = datetime.now().isoformat(timespec="seconds")
    log["总耗时秒"] = total_cost
    log["最终总分"] = best["总分"]
    log["结论"] = best["结论"]
    log["发布状态"] = best.get("发布状态", "待验证")
    log["生成契约通过"] = best.get("生成契约通过", True)
    log["生成契约问题数"] = best.get("生成契约问题数", 0)
    log["交付文件"] = final_html
    log["交付压缩包"] = final_zip
    log["交付说明"] = (("模型或场景模板生成，生成契约与发布审查均通过")
                       if is_passed else
                       "质量结论通过，但需教师审核后才能发布" if awaiting_teacher else
                       "未通过生成契约或质量审查，仅保存为不可交付候选稿")

    with open(os.path.join(run_dir, "运行日志.json"), "w", encoding="utf-8") as f:
        json.dump(log, f, ensure_ascii=False, indent=2)
    write_markdown(os.path.join(run_dir, "运行报告.md"), log, best)

    print("\n" + "=" * 64)
    print("完成    %s    总分 %.1f / 100    共 %d 轮    总耗时 %.1fs"
          % (best["结论"], best["总分"], len(log["轮次"]), total_cost))
    status_label = ("交付    " if is_passed else
                    "待教师审核（暂不可发布）    " if awaiting_teacher else
                    "候选稿（不可交付）    ")
    print(status_label + final_html)
    print("日志    %s" % os.path.join(run_dir, "运行日志.json"))
    print("报告    %s" % os.path.join(run_dir, "运行报告.md"))
    print("=" * 64)

    if best["问题清单"]:
        print("\n仍需人工确认的问题：")
        for item in best["问题清单"][:5]:
            print("  · [%s] %s：%s" % (item["维度"], item["检查项"], item["说明"]))

    if args.open and os.name == "nt":
        os.startfile(final_html)

    return 0 if is_passed else 1


def write_markdown(path, log, best):
    """写一份人能直接看的运行报告——录 Demo、写答辩材料都用得上。"""
    lines = [
        "# 教学资源生成运行报告",
        "",
        "- 运行 ID：%s" % log["运行ID"],
        "- 输入需求：%s" % log["输入"],
        "- 模型接入：%s" % log["模型接入"],
        "- 结论：**%s**，总分 %.1f / 100" % (log["结论"], log["最终总分"]),
        "- 发布状态：%s" % log.get("发布状态", "待验证"),
        "- 生成器场景契约：%s（问题 %d 项）" %
        ("通过" if log.get("生成契约通过", True) else "未通过",
         log.get("生成契约问题数", 0)),
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
        "| 轮次 | 生成来源 | 契约 | 字符数 | 总分 | 结论 | 发布状态 | 严重问题 | 失败项 |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for r in log["轮次"]:
        lines.append("| %d | %s | %s | %d | %.1f | %s | %s | %d | %d |"
                     % (r["轮次"], r["生成来源"],
                        "通过" if r.get("生成契约通过", True) else "失败",
                        r["字符数"], r["总分"], r["结论"], r.get("发布状态", "待验证"),
                        r["严重问题数"], r.get("失败项数", 0)))

    approved = is_release_ready(log)
    awaiting_teacher = is_awaiting_teacher_review(log)
    lines += ["", "## 交付状态", "",
              ("- 质量审查通过：第 %d 轮（总分 %.1f）" % (best["轮次"], best["总分"]))
              if approved else
              ("- 质量结论通过，但发布状态为待教师审核；此文件暂不可发布。" if awaiting_teacher else
               "- **生成契约或质量审查未通过：以下仅为不可交付候选稿**（第 %d 轮，总分 %.1f）" % (best["轮次"], best["总分"])),
              "- 生成来源：%s" % best["生成来源"],
              "- 文件：`%s`（同目录下另有每轮草稿和对应审查报告）" % os.path.basename(log.get("交付文件", ""))]

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
