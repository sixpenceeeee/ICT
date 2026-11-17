# -*- coding: utf-8 -*-
"""并行运行全部生地信页面的浏览器取证检查。"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BATCH = os.path.join(ROOT, "runs", "full_subject_batch")
CHECK = os.path.join(ROOT, "04_review_agent", "checks_browser.js")
NODE = shutil.which("node") or r"C:\Program Files\Tuanjie\Tuanjie AI\Tuanjie Cowork\cli\bin\win32-x64\node.EXE"
NODE_PATH = os.environ.get("NODE_PATH", r"C:\Users\wangq\.workbuddy\binaries\node\workspace\node_modules")
CHROME = os.environ.get("CHROME_PATH", r"C:\Program Files\Google\Chrome\Application\chrome.exe")


def pages():
    out = []
    for scene in sorted(os.listdir(BATCH)):
        folder = os.path.join(BATCH, scene)
        if not os.path.isdir(folder):
            continue
        htmls = [x for x in os.listdir(folder) if x.startswith("教学资源_") and x.endswith(".html") and "待修复" not in x]
        if htmls:
            out.append((scene, os.path.join(folder, sorted(htmls)[0])))
    return out


def audit(item):
    scene, path = item
    env = dict(os.environ)
    env["NODE_PATH"] = NODE_PATH
    env["CHROME_PATH"] = CHROME
    try:
        proc = subprocess.run([NODE, CHECK, path], capture_output=True, text=True,
                              encoding="utf-8", timeout=180, env=env)
        lines = (proc.stdout or "").strip().splitlines()
        data = json.loads(lines[-1]) if lines else {"ok": False, "fatal": proc.stderr[-400:]}
        return {"scene_id": scene, "html": path, "ok": bool(data.get("ok")),
                "errors": data.get("errors", []),
                "network": data.get("network", []),
                "canvas_painted": sum(1 for x in data.get("canvas", []) if x.get("painted", 0) > 0),
                "canvas_count": len(data.get("canvas", [])),
                "reset": data.get("reset", {}), "records": data.get("records", {}),
                "layout": data.get("layout", {}), "metamorphic": data.get("metamorphic", {}),
                "fatal": data.get("fatal")}
    except Exception as exc:  # noqa: BLE001
        return {"scene_id": scene, "html": path, "ok": False, "fatal": str(exc)}


def main():
    global BATCH
    parser = argparse.ArgumentParser()
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--aggregate", action="store_true")
    parser.add_argument("--batch", default=BATCH)
    args = parser.parse_args()
    BATCH = args.batch
    if args.aggregate:
        rows = []
        for name in sorted(os.listdir(BATCH)):
            if not name.startswith("browser_report_") or not name.endswith(".json"):
                continue
            with open(os.path.join(BATCH, name), encoding="utf-8") as f:
                rows.extend(json.load(f).get("pages", []))
        rows.sort(key=lambda x: x["scene_id"])
        report = {"total": len(rows), "passed": sum(1 for x in rows if x["ok"]),
                  "failed": sum(1 for x in rows if not x["ok"]), "pages": rows}
        path = os.path.join(BATCH, "browser_report.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print("REPORT", path)
        return 0 if report["failed"] == 0 else 1
    all_items = pages()
    items = all_items[args.offset:args.offset + args.limit] if args.limit else all_items[args.offset:]
    rows = []
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {pool.submit(audit, item): item[0] for item in items}
        for future in as_completed(futures):
            row = future.result()
            rows.append(row)
            print(row["scene_id"], "PASS" if row["ok"] else "FAIL")
    rows.sort(key=lambda x: x["scene_id"])
    report = {"total": len(rows), "passed": sum(1 for x in rows if x["ok"]),
              "failed": sum(1 for x in rows if not x["ok"]), "pages": rows}
    path = os.path.join(BATCH, "browser_report_%03d.json" % args.offset) if args.offset or args.limit else os.path.join(BATCH, "browser_report.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print("REPORT", path)
    return 0 if report["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
