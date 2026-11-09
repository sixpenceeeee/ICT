# -*- coding: utf-8 -*-
"""Independent DC resistive-network oracle using modified nodal analysis.

Supported elements: resistors, ideal voltage/current sources, and ideal
open/closed switches. Currents are oriented from each branch's ``from`` node
to its ``to`` node. This module is intentionally separate from the browser JS
solver so the reviewer can compare two implementations.
"""

import math


class CircuitError(ValueError):
    """Invalid, unsupported, or unsolvable circuit model."""


def _ends(component):
    start = component.get("from")
    end = component.get("to")
    if start is None:
        start = component.get("positive")
    if end is None:
        end = component.get("negative")
    if start is None or end is None:
        raise CircuitError("元件 %s 缺少 from/to 节点" % component.get("id", "?"))
    return str(start), str(end)


def _value(component, name, fallback=None):
    value = component.get(name)
    if value is None:
        value = fallback
    try:
        value = float(value)
    except (TypeError, ValueError):
        raise CircuitError("元件 %s 的 %s 不是有效数值" % (component.get("id", "?"), name))
    if not math.isfinite(value):
        raise CircuitError("元件 %s 的 %s 必须是有限数值" % (component.get("id", "?"), name))
    return value


def _solve_linear(matrix, rhs):
    """Gaussian elimination with partial pivoting; raises on singular systems."""
    n = len(rhs)
    a = [list(row) + [rhs[i]] for i, row in enumerate(matrix)]
    scale = max([abs(v) for row in matrix for v in row] + [1.0])
    eps = scale * 1e-12
    for col in range(n):
        pivot = max(range(col, n), key=lambda row: abs(a[row][col]))
        if abs(a[pivot][col]) <= eps:
            raise CircuitError("电路方程奇异：存在浮空节点、矛盾电压源或不可求解拓扑")
        a[col], a[pivot] = a[pivot], a[col]
        div = a[col][col]
        for j in range(col, n + 1):
            a[col][j] /= div
        for row in range(n):
            if row == col:
                continue
            factor = a[row][col]
            if abs(factor) <= eps:
                continue
            for j in range(col, n + 1):
                a[row][j] -= factor * a[col][j]
    return [a[i][n] for i in range(n)]


def _kvl_max_residual(components, branches):
    """Check a fundamental cycle basis of the active circuit graph."""
    parent = {}
    tree = {}

    def find(node):
        parent.setdefault(node, node)
        if parent[node] != node:
            parent[node] = find(parent[node])
        return parent[node]

    def path_drop(start, end):
        todo = [start]
        previous = {start: None}
        for node in todo:
            if node == end:
                break
            for neighbor, cid, sign in tree.get(node, []):
                if neighbor not in previous:
                    previous[neighbor] = (node, cid, sign)
                    todo.append(neighbor)
        if end not in previous:
            return None
        total = 0.0
        node = end
        while node != start:
            prev, cid, sign = previous[node]
            total += sign * branches[cid]["voltage"]
            node = prev
        return total

    max_residual = 0.0
    for c in components:
        if not c["active"]:
            continue
        a, b = c["from"], c["to"]
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb
            tree.setdefault(a, []).append((b, c["id"], 1.0))
            tree.setdefault(b, []).append((a, c["id"], -1.0))
        else:
            rest = path_drop(b, a)
            if rest is not None:
                max_residual = max(max_residual, abs(branches[c["id"]]["voltage"] + rest))
    return max_residual


def solve_circuit(model):
    """Solve a circuit model and return node/branch values plus law residuals.

    Example component fields:
      {"id":"V1","type":"voltage_source","positive":"n1","negative":"0","volts":6}
      {"id":"R1","type":"resistor","from":"n1","to":"0","ohms":10}
      {"id":"S1","type":"switch","from":"n1","to":"0","closed":false}
    """
    if not isinstance(model, dict):
        raise CircuitError("电路模型必须是对象")
    components = model.get("components")
    if not isinstance(components, list) or not components:
        raise CircuitError("电路模型 components 必须是非空数组")
    if len(components) > 80:
        raise CircuitError("第一版求解器最多支持 80 个元件")
    ground = str(model.get("ground", "0"))

    normalized = []
    nodes = {ground}
    ids = set()
    source_count = 0
    for raw in components:
        if not isinstance(raw, dict):
            raise CircuitError("每个电路元件都必须是对象")
        cid = str(raw.get("id", "")).strip()
        if not cid or cid in ids:
            raise CircuitError("每个元件必须有不重复的 id")
        ids.add(cid)
        kind = str(raw.get("type", "")).lower().replace("-", "_")
        aliases = {"voltagesource": "voltage_source", "currentsource": "current_source",
                   "switch": "switch", "resistor": "resistor", "ammeter": "ammeter",
                   "voltmeter": "voltmeter"}
        kind = aliases.get(kind, kind)
        if kind not in ("resistor", "voltage_source", "current_source", "switch", "ammeter", "voltmeter"):
            raise CircuitError("不支持的元件类型：%s" % raw.get("type", ""))
        a, b = _ends(raw)
        nodes.update((a, b))
        item = {"id": cid, "type": kind, "from": a, "to": b,
                "active": not (kind == "switch" and not bool(raw.get("closed", False)))}
        if kind == "resistor":
            ohms = _value(raw, "ohms", raw.get("resistance"))
            if ohms < 0:
                raise CircuitError("电阻不能为负值：%s" % cid)
            item["ohms"] = ohms
            if ohms == 0:
                item["type"] = "voltage_source"
                item["volts"] = 0.0
        elif kind == "voltage_source":
            item["volts"] = _value(raw, "volts", raw.get("value"))
        elif kind == "ammeter":
            item["volts"] = 0.0
        elif kind == "voltmeter":
            item["ohms"] = _value(raw, "inputOhms", raw.get("ohms", 1e7))
        elif kind == "current_source":
            item["amps"] = _value(raw, "amps", raw.get("value"))
        elif kind == "switch" and bool(raw.get("closed", False)):
            item["type"] = "voltage_source"
            item["volts"] = 0.0
        if item["active"] and item["type"] in ("voltage_source", "ammeter"):
            source_count += 1
        normalized.append(item)

    ordered_nodes = sorted(nodes - {ground})
    if len(nodes) > 80:
        raise CircuitError("第一版求解器最多支持 80 个节点")
    node_index = {node: i for i, node in enumerate(ordered_nodes)}
    voltage_branches = [c for c in normalized if c["active"] and c["type"] in ("voltage_source", "ammeter")]
    size = len(ordered_nodes) + len(voltage_branches)
    matrix = [[0.0] * size for _ in range(size)]
    rhs = [0.0] * size

    def stamp_node(i, j, value):
        if i is not None:
            matrix[i][i] += value
        if j is not None:
            matrix[j][j] += value
        if i is not None and j is not None:
            matrix[i][j] -= value
            matrix[j][i] -= value

    def node_of(name):
        return None if name == ground else node_index[name]

    source_index = {}
    for c in normalized:
        if not c["active"]:
            continue
        i, j = node_of(c["from"]), node_of(c["to"])
        if c["type"] in ("resistor", "voltmeter"):
            if c["ohms"] <= 0:
                raise CircuitError("电阻必须大于 0 Ω：%s" % c["id"])
            stamp_node(i, j, 1.0 / c["ohms"])
        elif c["type"] == "current_source":
            amps = c["amps"]
            if i is not None:
                rhs[i] -= amps
            if j is not None:
                rhs[j] += amps
        elif c["type"] in ("voltage_source", "ammeter"):
            k = len(ordered_nodes) + len(source_index)
            source_index[c["id"]] = k
            if i is not None:
                matrix[i][k] += 1.0
                matrix[k][i] += 1.0
            if j is not None:
                matrix[j][k] -= 1.0
                matrix[k][j] -= 1.0
            rhs[k] = c.get("volts", 0.0)

    solution = _solve_linear(matrix, rhs)
    node_voltages = {ground: 0.0}
    node_voltages.update({node: solution[idx] for node, idx in node_index.items()})
    branch_values = {}
    kcl = {node: 0.0 for node in nodes}
    total_power = 0.0
    max_source_residual = 0.0
    for c in normalized:
        va, vb = node_voltages[c["from"]], node_voltages[c["to"]]
        voltage = va - vb
        if not c["active"]:
            current = 0.0
        elif c["type"] in ("resistor", "voltmeter"):
            current = voltage / c["ohms"]
        elif c["type"] == "current_source":
            current = c["amps"]
        else:
            current = solution[source_index[c["id"]]]
            max_source_residual = max(max_source_residual, abs(voltage - c.get("volts", 0.0)))
        power = voltage * current
        kcl[c["from"]] += current
        kcl[c["to"]] -= current
        total_power += power
        branch_values[c["id"]] = {
            "type": c["type"], "voltage": voltage, "current": current,
            "power": power, "active": c["active"]
        }

    kcl_max = max([abs(v) for v in kcl.values()] + [0.0])
    kvl_max = _kvl_max_residual(normalized, branch_values)
    scale_i = max([abs(v["current"]) for v in branch_values.values()] + [1.0])
    scale_p = max([abs(v["power"]) for v in branch_values.values()] + [1.0])
    return {
        "nodes": node_voltages,
        "branches": branch_values,
        "checks": {
            "kclMaxResidual": kcl_max,
            "kvlMaxResidual": kvl_max,
            "voltageSourceMaxResidual": max_source_residual,
            "powerBalanceResidual": total_power,
            "kcl": kcl_max <= 1e-9 * scale_i,
            "kvl": kvl_max <= 1e-9 * max([abs(v["voltage"]) for v in branch_values.values()] + [1.0]),
            "voltageSources": max_source_residual <= 1e-9,
            "powerBalance": abs(total_power) <= 1e-9 * scale_p,
            "ok": kcl_max <= 1e-9 * scale_i
                  and kvl_max <= 1e-9 * max([abs(v["voltage"]) for v in branch_values.values()] + [1.0])
                  and max_source_residual <= 1e-9
                  and abs(total_power) <= 1e-9 * scale_p,
            "ground": ground,
            "activeVoltageSources": source_count,
        }
    }
