"""Persist regression checks for an exact contract and verified compatible pages."""

import hashlib
import json
import os
from pathlib import Path
import sqlite3
from contextlib import closing

DEFAULT_PATH = Path(__file__).resolve().parent / "runs" / ".teaching_evolution.sqlite3"
BASE_PROBES = (0, 0.5, 1)
REGRESSION_PROBES = (0, 0.25, 0.5, 0.75, 1)
VOLUME_RULES = {"T-03", "T-06"}


def connect():
    filename = Path(os.environ.get("ICT_TEACHING_MEMORY") or DEFAULT_PATH)
    filename.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(filename, timeout=10)
    db.execute("""CREATE TABLE IF NOT EXISTS regressions (
        contract TEXT PRIMARY KEY, failed_hash TEXT NOT NULL, issues TEXT NOT NULL,
        passed_hash TEXT, activated_at TEXT)""")
    db.execute("""CREATE TABLE IF NOT EXISTS regression_sources (
        contract TEXT PRIMARY KEY, scope TEXT NOT NULL, label TEXT NOT NULL)""")
    db.execute("""CREATE TABLE IF NOT EXISTS volume_regressions (
        contract TEXT NOT NULL, scope TEXT, rule TEXT NOT NULL, fraction REAL NOT NULL,
        failed_hash TEXT NOT NULL, passed_hash TEXT,
        PRIMARY KEY (contract, rule, fraction))""")
    return db


def contract_id(contract):
    value = json.dumps(contract, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(value.encode()).hexdigest()


def reuse_scope(contract):
    """Group only checks whose expectations remain valid across configurations."""
    if contract.get("component") == "append-record-row":
        return "append-record-row-v1", contract["scene"], {"G4-42"}
    if contract.get("profile") == "fixed-water-displacement":
        slider = contract["slider"]
        fixed = {key: value for key, value in contract["fixed"].items() if key != "volume"}
        if (slider["min"] == 0 and slider["unit"] == "mL" and slider["max"] > 0
                and contract["fixed"]["volume"] == slider["max"] * 1e-6):
            scope = contract_id({"scene": contract["scene"], "profile": contract["profile"],
                                 "field": slider["field"], "fixed": fixed})
            return scope, f"{slider['max']:g} mL 浮力量程", {"T-03", "T-06"}
    return None, None, set()


def plan(contract):
    key = contract_id(contract)
    result = {"status": "new", "points": list(BASE_PROBES), "issues": [], "cases": []}
    scope, _, shareable = reuse_scope(contract)
    try:
        with closing(connect()) as db:
            row = db.execute("""SELECT issues, passed_hash FROM regressions
                              WHERE contract = ?""", (key,)).fetchone()
            if row:
                result.update(status="active" if row[1] else "candidate",
                              points=list(REGRESSION_PROBES), issues=json.loads(row[0]))
            elif scope:
                for issues, label in db.execute("""SELECT r.issues, s.label FROM regression_sources s
                    JOIN regressions r ON r.contract = s.contract
                    WHERE s.scope = ? AND r.passed_hash IS NOT NULL
                    ORDER BY r.activated_at DESC, r.contract""", (scope,)):
                    matching = sorted(shareable.intersection(json.loads(issues)))
                    if matching:
                        result.update(status="transferred", points=list(REGRESSION_PROBES),
                                      issues=matching, source=label)
                        break
            if shareable & VOLUME_RULES:
                cases = {}
                for owner, rule, fraction, passed_hash in db.execute("""
                    SELECT contract, rule, fraction, passed_hash FROM volume_regressions
                    WHERE contract = ? OR (scope = ? AND passed_hash IS NOT NULL)
                    ORDER BY contract = ?, fraction, rule, contract
                """, (key, scope, key)):
                    status = ("active" if passed_hash else "candidate") if owner == key else "transferred"
                    cases[rule, fraction] = {"rule": rule, "fraction": fraction, "status": status}
                result["cases"] = list(cases.values())
                result["points"] = sorted(set(result["points"]) | {fraction for _, fraction in cases})
    except (OSError, sqlite3.Error, ValueError) as error:
        result["storage_error"] = str(error)
    return result


def observe(contract, memory, html, failures, passed, *, failed_cases=(), verified_points=()):
    """A failed page nominates a rule. A different passing page confirms it."""
    info = dict(memory)
    status = memory["status"]
    info["event"] = {"active": "reused", "transferred": "transferred"}.get(status, "none")
    scope, label, shareable = reuse_scope(contract)
    eligible = scope and shareable.intersection(memory["issues"])
    pending = [case for case in memory["cases"]
               if case["status"] == "candidate" and case["fraction"] in verified_points]
    if not failures and not (passed and (pending or status == "candidate"
                                         or (status == "active" and eligible))):
        return info
    digest = hashlib.sha256(html.encode()).hexdigest()
    key = contract_id(contract)
    try:
        with closing(connect()) as db, db:
            recorded = []
            for rule, fraction in failed_cases:
                if rule not in shareable & VOLUME_RULES or not 0 <= fraction <= 1:
                    continue
                cursor = db.execute("""INSERT OR IGNORE INTO volume_regressions
                    (contract, scope, rule, fraction, failed_hash) VALUES (?, ?, ?, ?, ?)""",
                                    (key, scope, rule, fraction, digest))
                if cursor.rowcount:
                    recorded.append({"rule": rule, "fraction": fraction})
            if recorded:
                info["recorded_cases"] = recorded
            if failures:
                cursor = db.execute("""INSERT OR IGNORE INTO regressions
                    (contract, failed_hash, issues) VALUES (?, ?, ?)""",
                    (key, digest, json.dumps(failures, ensure_ascii=False)))
                if cursor.rowcount:
                    info.update(event="recorded", issues=failures)
            elif passed and status == "candidate":
                cursor = db.execute("""UPDATE regressions SET passed_hash = ?,
                    activated_at = CURRENT_TIMESTAMP WHERE contract = ?
                    AND passed_hash IS NULL AND failed_hash <> ?""", (digest, key, digest))
                if cursor.rowcount:
                    info["event"] = "activated"
            if not failures and passed:
                activated = []
                for case in pending:
                    cursor = db.execute("""UPDATE volume_regressions SET passed_hash = ?
                        WHERE contract = ? AND rule = ? AND fraction = ?
                          AND passed_hash IS NULL AND failed_hash <> ?""",
                        (digest, key, case["rule"], case["fraction"], digest))
                    if cursor.rowcount:
                        activated.append({"rule": case["rule"], "fraction": case["fraction"]})
                if activated:
                    info["activated_cases"] = activated
            if not failures and eligible and (status == "active" or info["event"] == "activated"):
                db.execute("INSERT OR IGNORE INTO regression_sources VALUES (?, ?, ?)", (key, scope, label))
    except (OSError, sqlite3.Error) as error:
        info["storage_error"] = str(error)
    return info
