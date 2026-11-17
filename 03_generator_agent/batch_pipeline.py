# -*- coding: utf-8 -*-
"""Batch-generate all registered math, physics and chemistry scenes."""

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PROJECT = ROOT.parent
REQ_DIR = PROJECT / "runs" / "default_scene_requirements"
OUT_DIR = PROJECT / "runs" / "all_scene_pages"
KB = next(iter(sorted((PROJECT / "02_retrieval_agent" / "output").glob("知识包_*.json"))), None)
PYTHON = Path(sys.executable)


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    rows = []
    for req in sorted(REQ_DIR.glob("*.json")):
        scene_dir = OUT_DIR / req.stem
        command = [str(PYTHON), str(ROOT / "generator_agent.py"), "--req", str(req),
                   "--kb", str(KB), "--template-only", "--output-dir", str(scene_dir)]
        proc = subprocess.run(command, cwd=PROJECT, capture_output=True, text=True,
                              encoding="utf-8", errors="replace")
        html = next(scene_dir.glob("教学资源_*.html"), None) if scene_dir.exists() else None
        review = None
        if proc.returncode == 0 and html:
            review = subprocess.run([str(PYTHON), str(PROJECT / "04_review_agent" / "reviewer.py"),
                                     "--html", str(html), "--req", str(req)],
                                    cwd=PROJECT, capture_output=True, text=True,
                                    encoding="utf-8", errors="replace")
        rows.append({"scene_id": req.stem, "generated": proc.returncode == 0,
                     "reviewed": bool(review and review.returncode == 0),
                     "html": str(html) if html else None,
                     "review_output": review.stdout[-1600:] if review else None,
                     "output": proc.stdout[-1200:], "error": proc.stderr[-1200:]})
    report = {"total": len(rows), "generated": sum(row["generated"] for row in rows),
              "reviewed": sum(row["reviewed"] for row in rows), "scenes": rows}
    report_path = PROJECT / "04_review_agent" / "output" / "batch_generation_report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"report": str(report_path), "total": report["total"],
                      "generated": report["generated"], "reviewed": report["reviewed"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
