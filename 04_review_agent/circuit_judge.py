"""固定直流教学电路的独立复算器；只依赖 Python 标准库。

不调用浏览器/JavaScript 内核，不读取 solution.ok 或页面自报 checks。
第一阶段仅接受四个预设的器材和端点接线，用解析公式复算全部读数。
"""
import math
import re


_BASE_TYPES = {'V1': 'power_supply', 'A1': 'ammeter', 'M1': 'voltmeter',
               'R1': 'resistor', 'S1': 'switch'}
_PORTS = {'power_supply': ('positive', 'negative'),
          'ammeter': ('positive', 'negative'), 'voltmeter': ('positive', 'negative'),
          'resistor': ('a', 'b'), 'switch': ('a', 'b'),
          'rheostat': ('a', 'slider', 'b')}
_RECIPES = ('ohm', 'resistance', 'series', 'parallel')
_ID = re.compile(r'[A-Za-z][A-Za-z0-9_-]*\Z')
_ABS_TOL = 1e-8
_REL_TOL = 1e-6
_MISSING = object()


def _finite(value):
    # bool 是 int 的子类，但物理参数不接受 true/false 代替数字。
    if type(value) not in (int, float):
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


def _preset_wires(recipe):
    wires = [('V1.positive', 'S1.a'), ('S1.b', 'A1.positive'),
             ('M1.positive', 'R1.a'), ('M1.negative', 'R1.b')]
    if recipe == 'resistance':
        wires += [('A1.negative', 'RH1.a'), ('RH1.slider', 'R1.a'),
                  ('R1.b', 'V1.negative')]
    elif recipe == 'series':
        wires += [('A1.negative', 'R1.a'), ('R1.b', 'R2.a'),
                  ('R2.b', 'V1.negative')]
    else:
        wires += [('A1.negative', 'R1.a'), ('R1.b', 'V1.negative')]
        if recipe == 'parallel':
            wires += [('R1.a', 'R2.a'), ('R1.b', 'R2.b')]
    return {tuple(sorted(pair)) for pair in wires}


def _validate_config(config, issues):
    if not isinstance(config, dict):
        issues.append('config 必须是包含真实器材和接线的对象。')
        return None
    recipe = config.get('recipe')
    if not isinstance(recipe, str) or recipe not in _RECIPES:
        issues.append('config.recipe 仅支持 ohm、resistance、series、parallel。')
        return None
    if type(config.get('schema_version')) is not int or config['schema_version'] != 1:
        issues.append('config.schema_version 必须为整数 1。')
    types = dict(_BASE_TYPES)
    if recipe == 'resistance':
        types['RH1'] = 'rheostat'
    elif recipe in ('series', 'parallel'):
        types['R2'] = 'resistor'
    components = config.get('components')
    if not isinstance(components, list):
        issues.append('config.components 必须是器材数组。')
        return None
    by_id = {}
    ids = set()
    for item in components:
        if not isinstance(item, dict) or not isinstance(item.get('id'), str):
            issues.append('config.components 中每件器材都必须带字符串 id。')
            continue
        cid = item['id']
        if not _ID.fullmatch(cid) or cid in ids:
            issues.append('config.components 器材 id 非法或重复：' + cid)
            continue
        ids.add(cid)
        if cid not in types or item.get('type') != types[cid]:
            issues.append('config.components 器材 id/type 不符合固定预设：' + cid)
            continue
        by_id[cid] = item
        params = item.get('params')
        if not isinstance(params, dict):
            issues.append(cid + '.params 必须为物理参数对象。')
            continue
        fields = {'power_supply': ('voltage',), 'ammeter': ('range',),
                  'voltmeter': ('range',), 'resistor': ('resistance',),
                  'rheostat': ('maxResistance', 'position'), 'switch': ('closed',)}[types[cid]]
        for field in fields:
            value = params.get(field)
            if field == 'closed':
                valid = type(value) is bool
            else:
                valid = _finite(value)
                if valid:
                    valid = (0 <= value <= 1 if field == 'position' else
                             value >= 0 if field == 'voltage' else value > 0)
            if not valid:
                issues.append(cid + '.' + field + ' 不是有效物理参数。')
    if set(by_id) != set(types):
        issues.append('config.components 必须完整且仅包含预设器材：' + '、'.join(types))

    endpoints = {cid + '.' + port for cid, kind in types.items() for port in _PORTS[kind]}
    wires = config.get('wires')
    if not isinstance(wires, list):
        issues.append('config.wires 必须为真实端点接线数组。')
        return None
    connections = set()
    for wire in wires:
        if not isinstance(wire, dict):
            issues.append('config.wires 含非对象导线。')
            continue
        wid = wire.get('id')
        if not isinstance(wid, str) or not _ID.fullmatch(wid) or wid in ids:
            issues.append('config.wires 导线 id 非法或重复。')
        else:
            ids.add(wid)
        a, b = wire.get('from'), wire.get('to')
        if not isinstance(a, str) or not isinstance(b, str) or a not in endpoints or b not in endpoints:
            issues.append('config.wires 导线端点不存在或类型错误。')
            continue
        connection = tuple(sorted((a, b)))
        if connection in connections:
            issues.append('config.wires 存在重复接线：' + ' ↔ '.join(connection))
        connections.add(connection)
    if connections != _preset_wires(recipe):
        issues.append('config.wires 实际端点接线与 ' + recipe + ' 固定预设不符。')
    return None if issues else (recipe, by_id)


def _derive(recipe, components):
    """从合法拓扑与参数解析复算；电源电流以流入正端为正。"""
    params = {cid: item['params'] for cid, item in components.items()}
    supply = params['V1']['voltage']
    r1 = params['R1']['resistance']
    r2 = params.get('R2', {}).get('resistance')
    rheostat = (params['RH1']['maxResistance'] * params['RH1']['position']
                if recipe == 'resistance' else 0)
    if recipe == 'series':
        resistance = r1 + r2
    elif recipe == 'parallel':
        resistance = 1 / (1 / r1 + 1 / r2)
    else:
        resistance = r1 + rheostat
    closed = params['S1']['closed']
    current = supply / resistance if closed else 0
    load_supply = supply if closed else 0
    measured = current * r1 if recipe in ('series', 'resistance') else load_supply
    r1_current = measured / r1
    r2_voltage = current * r2 if recipe == 'series' else load_supply
    r1_low = r2_voltage if recipe == 'series' else 0
    r1_high = r1_low + measured

    node_voltages = {'V1.positive': supply, 'V1.negative': 0,
                     'S1.a': supply, 'S1.b': load_supply,
                     'A1.positive': load_supply, 'A1.negative': load_supply,
                     'M1.positive': r1_high, 'M1.negative': r1_low,
                     'R1.a': r1_high, 'R1.b': r1_low}
    resistor_currents = {'R1': r1_current}
    resistor_voltages = {'R1': measured}
    readings = {
        'V1': {'current': -current, 'voltage': supply, 'value': supply},
        'A1': {'current': current, 'voltage': 0, 'value': current},
        'M1': {'current': 0, 'voltage': measured, 'value': measured},
        'R1': {'current': r1_current, 'voltage': measured, 'value': r1},
        # 理想闭合开关两端合并，其独立支路电流未作为内核可辨识量输出。
        'S1': {'current': None if closed else 0, 'voltage': 0 if closed else supply,
               'value': 1 if closed else 0},
    }
    if r2 is not None:
        r2_current = r2_voltage / r2
        readings['R2'] = {'current': r2_current, 'voltage': r2_voltage, 'value': r2}
        node_voltages.update({'R2.a': r2_voltage, 'R2.b': 0})
        resistor_currents['R2'] = r2_current
        resistor_voltages['R2'] = r2_voltage
    if recipe == 'resistance':
        drop = current * rheostat
        readings['RH1'] = {'current': current, 'voltage': drop, 'value': rheostat}
        node_voltages.update({'RH1.a': load_supply, 'RH1.slider': measured, 'RH1.b': measured})
        resistor_currents['RH1'] = current
        resistor_voltages['RH1'] = drop
    overrange = {}
    for cid, reading in readings.items():
        meter_range = params[cid].get('range') if cid in ('A1', 'M1') else None
        reading['range'] = meter_range
        reading['overrange'] = (abs(reading['value']) - meter_range >
                                8 * math.ulp(1.0) * max(1, meter_range)
                                if meter_range is not None else False)
        if meter_range is not None:
            overrange[cid] = reading['overrange']
    # Infinity 经 JSON.stringify 传输为 null；仅断路的等效电阻允许 null。
    expected = {'totalCurrent': current, 'sourceVoltage': supply,
                'equivalentResistance': resistance if closed else None,
                'measuredVoltage': measured, 'resistorCurrents': resistor_currents,
                'resistorVoltages': resistor_voltages, 'overrange': overrange,
                'components': readings, 'nodeVoltages': node_voltages}
    values = [resistance, current, measured, *node_voltages.values()]
    values += [value for reading in readings.values() for key, value in reading.items()
               if value is not None and key != 'overrange']
    if not all(_finite(value) for value in values):
        raise ArithmeticError('参数导致复算数值溢出。')
    return expected


class _UnionFind:
    def __init__(self, elements):
        self.parent = {x: x for x in elements}

    def find(self, x):
        root = x
        while self.parent[root] != root:
            root = self.parent[root]
        curr = x
        while curr != root:
            nxt = self.parent[curr]
            self.parent[curr] = root
            curr = nxt
        return root

    def union(self, a, b):
        ra = self.find(a)
        rb = self.find(b)
        if ra != rb:
            self.parent[ra] = rb


def _solve_linear(matrix, rhs):
    """部分主元高斯消元法。"""
    n = len(rhs)
    rows = [row[:] + [rhs[i]] for i, row in enumerate(matrix)]
    for col in range(n):
        pivot = col
        for row in range(col + 1, n):
            if abs(rows[row][col]) > abs(rows[pivot][col]):
                pivot = row
        if abs(rows[pivot][col]) < 1e-14 or not math.isfinite(rows[pivot][col]):
            raise ArithmeticError('SINGULAR_MATRIX')
        rows[col], rows[pivot] = rows[pivot], rows[col]
        div = rows[col][col]
        for idx in range(col, n + 1):
            rows[col][idx] /= div
        for row in range(n):
            if row == col:
                continue
            factor = rows[row][col]
            if factor == 0:
                continue
            for idx in range(col, n + 1):
                rows[row][idx] -= factor * rows[col][idx]
    result = [row[n] for row in rows]
    if not all(math.isfinite(x) for x in result):
        raise ArithmeticError('NUMERIC_ERROR')
    return result


def _solve_mna_python(config):
    """标准库纯 Python MNA 求解器。"""
    components = {c['id']: c for c in config['components']}
    endpoints = [c['id'] + '.' + port for c in config['components'] for port in _PORTS[c['type']]]
    uf = _UnionFind(endpoints)
    for wire in config['wires']:
        uf.union(wire['from'], wire['to'])
    for c in config['components']:
        if c['type'] == 'switch' and c['params'].get('closed', False):
            uf.union(c['id'] + '.a', c['id'] + '.b')

    sources = []
    resistors = []

    def add_branch(bid, frm, to, r):
        if r == 0:
            sources.append({'id': bid, 'from': uf.find(frm), 'to': uf.find(to), 'v': 0.0})
        else:
            resistors.append({'id': bid, 'from': uf.find(frm), 'to': uf.find(to), 'r': r})

    supply = None
    for c in config['components']:
        cid = c['id']
        p = c['params']
        ctype = c['type']
        if ctype == 'power_supply':
            supply = {'id': cid, 'from': uf.find(cid + '.positive'), 'to': uf.find(cid + '.negative'), 'v': float(p['voltage'])}
            sources.insert(0, supply)
        elif ctype == 'ammeter':
            sources.append({'id': cid, 'from': uf.find(cid + '.positive'), 'to': uf.find(cid + '.negative'), 'v': 0.0})
        elif ctype == 'resistor':
            add_branch(cid, cid + '.a', cid + '.b', float(p['resistance']))
        elif ctype == 'rheostat':
            ra = float(p['maxResistance']) * float(p['position'])
            rb = float(p['maxResistance']) * (1.0 - float(p['position']))
            add_branch(cid + ':a', cid + '.a', cid + '.slider', ra)
            add_branch(cid + ':b', cid + '.slider', cid + '.b', rb)

    if not supply:
        raise ValueError('MISSING_SOURCE: 缺少直流电源。')

    roots = list({uf.find(ep) for ep in endpoints})

    # 短路保护 (SOURCE_SHORT)
    conductive = _UnionFind(roots)
    for s in sources:
        if s is not supply:
            conductive.union(s['from'], s['to'])
    if conductive.find(supply['from']) == conductive.find(supply['to']):
        raise ValueError('SOURCE_SHORT: 电源正负端经导线、闭合开关或理想电流表短接。')

    # 悬空节点检查 (FLOATING_SUBCIRCUIT)
    connected = _UnionFind(roots)
    for b in sources + resistors:
        connected.union(b['from'], b['to'])
    floating = [node for node in roots if connected.find(node) != connected.find(supply['to'])]
    if floating:
        raise ValueError('FLOATING_SUBCIRCUIT: 存在未参考电源负端的悬空端口/子电路：' + '、'.join(floating))

    # 开路状态判断
    load_connected = _UnionFind(roots)
    for b in [s for s in sources if s is not supply] + resistors:
        load_connected.union(b['from'], b['to'])
    is_open = (load_connected.find(supply['from']) != load_connected.find(supply['to']))

    nodes = [node for node in roots if node != supply['to']]
    node_indices = {node: i for i, node in enumerate(nodes)}
    active_sources = [s for s in sources if s['from'] != s['to']]
    size = len(nodes) + len(active_sources)
    matrix = [[0.0] * size for _ in range(size)]
    rhs = [0.0] * size

    for r in resistors:
        a = node_indices.get(r['from'])
        b = node_indices.get(r['to'])
        g = 1.0 / r['r']
        if a is not None:
            matrix[a][a] += g
        if b is not None:
            matrix[b][b] += g
        if a is not None and b is not None:
            matrix[a][b] -= g
            matrix[b][a] -= g

    for k, s in enumerate(active_sources):
        branch_idx = len(nodes) + k
        a = node_indices.get(s['from'])
        b = node_indices.get(s['to'])
        if a is not None:
            matrix[a][branch_idx] += 1.0
            matrix[branch_idx][a] += 1.0
        if b is not None:
            matrix[b][branch_idx] -= 1.0
            matrix[branch_idx][b] -= 1.0
        rhs[branch_idx] = s['v']

    supply_idx = len(nodes) + active_sources.index(supply)
    try:
        solution = _solve_linear(matrix, rhs)
        if is_open:
            equivalent = None
        elif supply['v'] != 0:
            equivalent = supply['v'] / -solution[supply_idx]
        else:
            unit_rhs = rhs[:]
            unit_rhs[supply_idx] = 1.0
            equivalent = 1.0 / -_solve_linear(matrix, unit_rhs)[supply_idx]
    except ArithmeticError as err:
        raise ValueError('UNSOLVABLE_TOPOLOGY: 电路无法数值求解：' + str(err))

    def potential(node):
        return 0.0 if node == supply['to'] else solution[node_indices[node]]

    def norm(v):
        return 0.0 if v is None or v == 0.0 or abs(v) < 1e-15 else v

    node_voltages = {ep: norm(potential(uf.find(ep))) for ep in endpoints}

    def get_voltage(cid, a, b):
        return norm(potential(uf.find(cid + '.' + a)) - potential(uf.find(cid + '.' + b)))

    def get_source_current(sid):
        for idx, s in enumerate(active_sources):
            if s['id'] == sid:
                return norm(solution[len(nodes) + idx])
        return 0.0

    readings = {}
    resistor_currents = {}
    resistor_voltages = {}
    overrange = {}

    for cid, c in components.items():
        p = c['params']
        ctype = c['type']
        if ctype == 'power_supply':
            u = get_voltage(cid, 'positive', 'negative')
            i = get_source_current(cid)
            readings[cid] = {'current': i, 'voltage': u, 'value': u, 'range': None}
        elif ctype == 'ammeter':
            u = get_voltage(cid, 'positive', 'negative')
            i = get_source_current(cid)
            rng = p.get('range')
            readings[cid] = {'current': i, 'voltage': u, 'value': i, 'range': rng}
        elif ctype == 'voltmeter':
            u = get_voltage(cid, 'positive', 'negative')
            rng = p.get('range')
            readings[cid] = {'current': 0.0, 'voltage': u, 'value': u, 'range': rng}
        elif ctype == 'resistor':
            u = get_voltage(cid, 'a', 'b')
            r_val = float(p['resistance'])
            i = norm(u / r_val)
            readings[cid] = {'current': i, 'voltage': u, 'value': r_val, 'range': None}
            resistor_voltages[cid] = u
            resistor_currents[cid] = i
        elif ctype == 'rheostat':
            u = get_voltage(cid, 'a', 'slider')
            r_val = float(p['maxResistance']) * float(p['position'])
            i = get_source_current(cid + ':a') if r_val == 0 else norm(u / r_val)
            readings[cid] = {'current': i, 'voltage': u, 'value': r_val, 'range': None}
            resistor_voltages[cid] = u
            resistor_currents[cid] = i
        elif ctype == 'switch':
            u = get_voltage(cid, 'a', 'b')
            closed = p.get('closed', False)
            readings[cid] = {'current': None if closed else 0.0, 'voltage': u, 'value': 1 if closed else 0, 'range': None}

    for cid, reading in readings.items():
        rng = reading.get('range')
        reading['overrange'] = (abs(reading['value']) - rng > 8 * math.ulp(1.0) * max(1, rng)) if rng is not None else False
        if rng is not None:
            overrange[cid] = reading['overrange']

    total_current = 0.0 if is_open else norm(-solution[supply_idx])
    measured_voltage = next((r['voltage'] for cid, r in readings.items() if components[cid]['type'] == 'voltmeter'), 0.0)

    return {
        'totalCurrent': total_current,
        'sourceVoltage': supply['v'],
        'equivalentResistance': equivalent,
        'measuredVoltage': measured_voltage,
        'resistorCurrents': resistor_currents,
        'resistorVoltages': resistor_voltages,
        'overrange': overrange,
        'components': readings,
        'nodeVoltages': node_voltages
    }


def _validate_general_config(config, issues):
    if not isinstance(config, dict):
        issues.append('config 必须是包含真实器材和接线的对象。')
        return None
    if type(config.get('schema_version')) is not int or config['schema_version'] != 1:
        issues.append('config.schema_version 必须为整数 1。')
    components = config.get('components')
    if not isinstance(components, list) or not components:
        issues.append('config.components 必须是器材数组。')
        return None
    by_id = {}
    ids = set()
    sources = []
    for item in components:
        if not isinstance(item, dict) or not isinstance(item.get('id'), str):
            issues.append('config.components 中每件器材都必须带字符串 id。')
            continue
        cid = item['id']
        if not _ID.fullmatch(cid) or cid in ids:
            issues.append('config.components 器材 id 非法或重复：' + cid)
            continue
        ids.add(cid)
        ctype = item.get('type')
        if ctype not in _PORTS:
            issues.append('config.components 器材 id/type 未知：' + cid)
            continue
        by_id[cid] = item
        if ctype == 'power_supply':
            sources.append(item)
        params = item.get('params')
        if not isinstance(params, dict):
            issues.append(cid + '.params 必须为物理参数对象。')
            continue
        fields = {'power_supply': ('voltage',), 'ammeter': ('range',),
                  'voltmeter': ('range',), 'resistor': ('resistance',),
                  'rheostat': ('maxResistance', 'position'), 'switch': ('closed',)}[ctype]
        for field in fields:
            value = params.get(field)
            if field == 'closed':
                valid = type(value) is bool
            else:
                valid = _finite(value)
                if valid:
                    valid = (0 <= value <= 1 if field == 'position' else
                             value >= 0 if field == 'voltage' else value > 0)
            if not valid:
                issues.append(cid + '.' + field + ' 不是有效物理参数。')
    if not sources:
        issues.append('电路缺少直流电源。')
    elif len(sources) > 1:
        issues.append('当前仅支持单个直流电源。')

    endpoints = {cid + '.' + port for cid, item in by_id.items() for port in _PORTS[item['type']]}
    wires = config.get('wires')
    if not isinstance(wires, list):
        issues.append('config.wires 必须为真实端点接线数组。')
        return None
    connections = set()
    for wire in wires:
        if not isinstance(wire, dict):
            issues.append('config.wires 含非对象导线。')
            continue
        wid = wire.get('id')
        if not isinstance(wid, str) or not _ID.fullmatch(wid) or wid in ids:
            issues.append('config.wires 导线 id 非法或重复。')
        else:
            ids.add(wid)
        a, b = wire.get('from'), wire.get('to')
        if not isinstance(a, str) or not isinstance(b, str) or a not in endpoints or b not in endpoints:
            issues.append('config.wires 导线端点不存在或类型错误。')
            continue
        connection = tuple(sorted((a, b)))
        if connection in connections:
            issues.append('config.wires 存在重复接线：' + ' ↔ '.join(connection))
        connections.add(connection)
    if issues:
        return None
    return by_id


def _compare(actual, expected, path, issues):
    if expected is None:
        valid = actual is None
    elif type(expected) is bool:
        valid = type(actual) is bool and actual == expected
    else:
        valid = _finite(actual) and math.isclose(actual, expected, rel_tol=_REL_TOL, abs_tol=_ABS_TOL)
    if not valid:
        value = '缺失' if actual is _MISSING else repr(actual)
        issues.append('%s：应为 %r，实际 %s。' % (path, expected, value))


def verify_circuit(data):
    """核对 {config, solution}，返回 {ok: bool, issues: [str], expected: dict}。

    expected 提供 totalCurrent、sourceVoltage、equivalentResistance、
    measuredVoltage、resistorCurrents/Voltages、overrange，以及逐器材/端点期望值。
    无效配置不能复算，expected 为空；无效读数仍返回独立期望值供审查报告使用。
    """
    issues = []
    result = {'ok': False, 'issues': issues, 'expected': {}}
    if not isinstance(data, dict):
        issues.append('电路审查输入必须为 {config, solution} 对象。')
        return result
    config = data.get('config')
    recipe = config.get('recipe') if isinstance(config, dict) else None
    if recipe in _RECIPES:
        checked = _validate_config(config, issues)
        if checked is None:
            return result
        try:
            expected = _derive(*checked)
        except (ArithmeticError, OverflowError, ValueError) as exc:
            issues.append('独立电路复算失败：' + str(exc))
            return result
    else:
        checked = _validate_general_config(config, issues)
        if checked is None:
            return result
        try:
            expected = _solve_mna_python(config)
        except (ArithmeticError, OverflowError, ValueError) as exc:
            issues.append('独立电路复算失败：' + str(exc))
            return result

    result['expected'] = expected
    solution = data.get('solution')
    if not isinstance(solution, dict):
        issues.append('solution 必须包含内核运行时的逐器材和端点读数。')
        return result
    for key in ('totalCurrent', 'sourceVoltage', 'equivalentResistance'):
        _compare(solution.get(key, _MISSING), expected[key], key, issues)
    for group in ('components', 'nodeVoltages'):
        actual_group = solution.get(group)
        if not isinstance(actual_group, dict):
            issues.append('solution.' + group + ' 必须为完整读数对象。')
            continue
        expected_group = expected[group]
        if set(actual_group) != set(expected_group):
            issues.append('solution.' + group + ' 的器材或端点清单与真实配置不一致。')
        for key, value in expected_group.items():
            actual = actual_group.get(key, _MISSING)
            path = group + '.' + key
            if group == 'nodeVoltages':
                _compare(actual, value, path, issues)
            elif not isinstance(actual, dict):
                issues.append(path + ' 缺少逐器材读数。')
            else:
                for field, quantity in value.items():
                    _compare(actual.get(field, _MISSING), quantity, path + '.' + field, issues)
    result['ok'] = not issues
    return result
