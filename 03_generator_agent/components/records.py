# -*- coding: utf-8 -*-
"""⑤ 实验记录：可追加的记录表（CSV 导出按钮在 ③ 区，由 controls 负责）。

记录表只声明"列"和"每列从 request/result 的哪个字段取"，行由运行时追加；
因此记录值与读数卡必然同源，不会出现"表格比读数少一位小数"这类不一致。
"""

from . import atoms


def render_records(spec):
    if "records" not in (spec.get("components") or []):
        return ""
    records = spec.get("records") or {}
    html = atoms.render_record_table(records.get("headers") or [], records.get("body_id", "lesson-records"))
    if "csv" in (spec.get("components") or []):
        html += atoms.render_note("点击「记录当前数据」逐行追加；「导出 CSV」导出整张表。")
    return html


def markers(spec):
    return []


def headers(spec):
    return list((spec.get("records") or {}).get("headers") or [])
