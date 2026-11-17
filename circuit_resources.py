"""器件目录与 Agent JSON 配置到现有六区域页面的适配器。"""
from html import escape
import json
from pathlib import Path
import math
import re
import shutil
import subprocess

ROOT = Path(__file__).resolve().parent
LIB = ROOT / 'frame' / 'circuit'
TITLES = {'ohm': '欧姆定律', 'resistance': '伏安法测电阻', 'series': '串联电路', 'parallel': '并联电路', 'voltage_divider': '滑动变阻器分压控制实验'}


def default_voltage_divider_config(params=None):
    p = {'voltage': 6, 'maxResistance': 50, 'position': 0.5, 'resistance': 10, 'closed': True, 'ammeterRange': 0.6, 'voltmeterRange': 15}
    if params:
        p.update(params)
    return {
        'schema_version': 1,
        'recipe': 'voltage_divider',
        'title': '滑动变阻器分压控制实验',
        'components': [
            {'id': 'V1', 'type': 'power_supply', 'params': {'voltage': p['voltage']}, 'x': 100, 'y': 100},
            {'id': 'S1', 'type': 'switch', 'params': {'closed': p['closed']}, 'x': 250, 'y': 100},
            {'id': 'RH1', 'type': 'rheostat', 'params': {'maxResistance': p['maxResistance'], 'position': p['position']}, 'x': 420, 'y': 100},
            {'id': 'A1', 'type': 'ammeter', 'params': {'range': p['ammeterRange']}, 'x': 600, 'y': 100},
            {'id': 'M1', 'type': 'voltmeter', 'params': {'range': p['voltmeterRange']}, 'x': 600, 'y': 280},
            {'id': 'R1', 'type': 'resistor', 'params': {'resistance': p['resistance']}, 'x': 750, 'y': 100}
        ],
        'wires': [
            {'id': 'W1', 'from': 'V1.positive', 'to': 'S1.a'},
            {'id': 'W2', 'from': 'S1.b', 'to': 'RH1.a'},
            {'id': 'W3', 'from': 'RH1.b', 'to': 'V1.negative'},
            {'id': 'W4', 'from': 'RH1.slider', 'to': 'A1.positive'},
            {'id': 'W5', 'from': 'A1.negative', 'to': 'R1.a'},
            {'id': 'W6', 'from': 'R1.b', 'to': 'V1.negative'},
            {'id': 'W7', 'from': 'M1.positive', 'to': 'R1.a'},
            {'id': 'W8', 'from': 'M1.negative', 'to': 'R1.b'}
        ]
    }


def is_circuit_request(req):
    subject = req.get('学科', '')
    text = ' '.join(str(req.get(k, '')) for k in ('实验主题', '实验名称', '交互要求'))
    return subject in ('物理', '物理学', '') and bool(re.search(r'电路|欧姆|伏安|电流|电压|电阻|滑动变阻|串联|并联|分压', text))


def template_requirement(text):
    """仅用于显式预设模式/无密钥；保留用户选择的电路主题。"""
    recipe = choose_recipe({'实验主题': text})
    variables = [{'名称': '电源电压', '范围': '0–12', '单位': 'V'}]
    if recipe in ('resistance', 'voltage_divider'):
        variables.append({'名称': '滑动变阻器位置', '范围': '0–1', '单位': ''})
    if recipe == 'voltage_divider':
        variables.append({'名称': '负载电阻', '范围': '1–100', '单位': 'Ω'})
    else:
        variables.append({'名称': '电阻 R1', '范围': '1–100', '单位': 'Ω'})
        if recipe in ('series', 'parallel'):
            variables.append({'名称': '电阻 R2', '范围': '1–100', '单位': 'Ω'})
    return {'学科': '物理', '年级': '初中九年级', '实验名称': TITLES[recipe], '实验主题': text,
            '学习目标': ['能识别电路器材与正确接法', '能调参、读取电表示数并记录数据'], '核心变量': variables,
            '交互要求': ['切换开关', '调节参数并同步电表示数', '放大后调整器材参数、量程和位置', '记录与复位'],
            '技术要点': '使用电路组件目录、实物 SVG 器材和自包含 HTML',
            '风险点': ['预设需求，未调用模型；电表采用理想模型，需要教师复核。']}


def choose_recipe(req):
    if isinstance(req, dict) and req.get('recipe') in TITLES:
        return req['recipe']
    text = ' '.join(str(req.get(k, '')) for k in ('实验主题', '实验名称', 'recipe'))
    if re.search(r'交流|\bRC\b|电容|充放电|二极管|晶体管|小灯泡|非线性|焦耳|热量|电热|电功|功率|电能|磁|电荷|静电|库仑', text, re.I):
        raise ValueError('当前器件模板支持线性直流电阻实验；该需求需要另外的器件模型，不能套用欧姆定律预设。')
    if re.search(r'分压|分压式|分压控制|电位器', text):
        return 'voltage_divider'
    if re.search(r'伏安|测.{0,3}电阻|滑动变阻', text):
        return 'resistance'
    if '并联' in text:
        return 'parallel'
    if '串联' in text:
        return 'series'
    return 'ohm'


def catalog():
    return json.loads((LIB / 'catalog.json').read_text(encoding='utf-8'))


def parse_plan(text):
    text = re.sub(r'^```(?:json)?\s*|\s*```$', '', text.strip(), flags=re.I)
    value = json.loads(text, parse_constant=lambda v: (_ for _ in ()).throw(ValueError('不接受非有限数值')))
    if not isinstance(value, dict):
        raise ValueError('电路配置必须是 JSON 对象')
    return value


def resolve_plan(plan):
    """用真正的浏览器同款内核检查配置，禁止把模型自报读数当结果。"""
    node = shutil.which('node')
    if not node:
        raise ValueError('需要 Node.js 校验电路配置；请安装后重试。')
    if isinstance(plan, dict) and plan.get('recipe') == 'voltage_divider' and 'components' not in plan:
        plan = default_voltage_divider_config(plan.get('params'))
    payload = json.dumps(plan, ensure_ascii=False, allow_nan=False)
    proc = subprocess.run([node, str(ROOT / 'tools' / 'circuit_bridge.js')], input=payload,
                          capture_output=True, text=True, encoding='utf-8', timeout=15, cwd=ROOT)
    try:
        result = json.loads(proc.stdout)
    except ValueError as exc:
        raise ValueError('电路内核未返回有效配置：' + proc.stderr[:300]) from exc
    if proc.returncode or result.get('error'):
        raise ValueError(result.get('error') or proc.stderr[:300])
    for device in result['config']['components']:
        if device['type'] == 'power_supply' and not 0 <= device['params']['voltage'] <= 12:
            raise ValueError('教学电源电压必须在 0–12 V 范围内')
        for axis, limit in (('x', 1000), ('y', 650)):
            value = device.get(axis)
            if value is not None and (isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value) or not 0 <= value <= limit):
                raise ValueError('器件 ' + device['id'] + ' 的位置超出演示范围')
    return result['config'], result['solution']


def build_circuit_prompt(req, pack, feedback=None):
    recipe = choose_recipe(req)
    seed, _ = resolve_plan({'recipe': recipe})
    return ('你负责用现有器件模板设计线性直流教学电路。只输出一个完整 JSON 配置，不输出 HTML、JS 或说明。\n'
            '教学需求：' + json.dumps(req, ensure_ascii=False) + '\n'
            '教研知识：' + json.dumps(pack, ensure_ascii=False) + '\n'
            '器件目录（类型、参数、端子是唯一有效接口）：' + json.dumps(catalog(), ensure_ascii=False) + '\n'
            '可直接使用并改参数的完整配置：' + json.dumps(seed, ensure_ascii=False) + '\n'
            '保留 schema_version、recipe、components、wires；每条线通过 ID.port 连接。'
            '可根据实验教学需要自主选择与组合器件拓扑，或基于示例微调。'
            '电流表串联，电压表并联在被测电阻两端。不要输出电流/电压计算结果，运行时会根据接线求解。'
            '电源 0–12 V，电阻大于0，滑变 position 0–1；电表 range 为正数。所有值必须有限。'
            '如果需求超出目录能力，应返回 {"error":"原因"}，不能编造新器件。\n'
            + ('上一轮修改意见：' + str(feedback) if feedback else ''))


def render_sections(config, provenance='组件模板'):
    recipe = config['recipe']
    title = TITLES.get(recipe, '直流电路实验')
    encoded = json.dumps(config, ensure_ascii=False, allow_nan=False).replace('<', '\\u003c')
    description = {
        'ohm': '调节电源电压或电阻，观察电流与电压、电阻的关系。',
        'resistance': '保持待测电阻不变，调节滑动变阻器，用电压表与电流表测量并计算 R＝U/I。',
        'series': '比较串联电阻的分压，检验电流相等与总电压等于各段电压之和。',
        'parallel': '比较并联支路电流，检验各支路同压、总电流等于支路电流之和。',
        'voltage_divider': '调节滑动变阻器滑片，观察负载电阻两端分压在 0 V 至电源电压间的连续可调规律。',
    }.get(recipe, '调节参数，观察电路电压与电流分布。')
    principle = {
        'ohm': '理想电阻满足 I＝U/R。改变一个变量时，应控制另一个变量保持不变。',
        'resistance': '电流表串联，电压表并联在待测电阻两端。用被测电阻两端电压除以通过它的电流求阻值；滑动变阻器与它串联。',
        'series': 'I＝U/(R₁＋R₂)，U₁＝IR₁，U₂＝IR₂。',
        'parallel': 'I₁＝U/R₁，I₂＝U/R₂，I＝I₁＋I₂。',
        'voltage_divider': '滑动变阻器接成分压式电路：两端固定接线柱接电源，滑片端与一端接负载，输出电压在 0 到电源电压之间连续可调。',
    }.get(recipe, '各节点电势与支路电流遵循基尔霍夫电压与电流定律。')
    extra_reads = ''
    for index in (1, 2) if recipe == 'parallel' else ((2,) if recipe == 'series' else ()):
        label = '支路 R' + str(index) + ' 电流' if recipe == 'parallel' else 'R₂ 两端电压'
        unit = 'A' if recipe == 'parallel' else 'V'
        extra_reads += '<div class="exp-read"><span class="k">' + label + '</span><span class="v"><b id="read-branch-' + str(index) + '">—</b> <span class="u">' + unit + '</span></span></div>'
    return {
        '1': '<div class="exp-tags"><span class="exp-tag">物理</span><span class="exp-tag">初中九年级</span>'
             '<span class="exp-tag is-plain">' + escape(provenance) + '</span></div>'
             '<div class="exp-goals-title">学习目标</div><ul class="exp-goals"><li>能识别电源、开关、电流表、电压表与正确接线</li>'
             '<li>能通过调参和记录检验电路规律</li><li>' + description + '</li></ul>',
        '2': '<svg id="cv" data-visual-type="apparatus" role="img" aria-label="实物电路实验装置" viewBox="0 0 1000 650"></svg>'
             '<div class="circuit-stage-tools"><span class="exp-canvas-tip">点击放大，可精细调参、选择量程与移动器件</span>'
             '<button class="exp-btn" id="btn-enlarge" type="button">放大调整 ↗</button></div>',
        '3': '<div id="circuit-controls" class="exp-field"></div><div class="exp-btns">'
             '<button class="exp-btn is-primary" id="btn-switch" type="button"></button>'
             '<button class="exp-btn" id="btn-record" type="button">记录当前数据</button>'
             '<button class="exp-btn" id="btn-reset" type="button">重置</button>'
             '<button class="exp-btn" id="btn-csv" type="button">导出 CSV</button></div>',
        '4': '<div class="exp-reads"><div class="exp-read"><span class="k">电流表</span><span class="v"><b id="read-current">—</b> <span class="u">A</span></span></div>'
             '<div class="exp-read"><span class="k">电压表</span><span class="v"><b id="read-voltage">—</b> <span class="u">V</span></span></div>'
             '<div class="exp-read"><span class="k" id="resistance-label">' + ('等效电阻' if recipe == 'parallel' else ('负载电阻' if recipe == 'voltage_divider' else '待测电阻')) + '</span><span class="v"><b id="read-resistance">—</b> <span class="u">Ω</span></span></div>' + extra_reads + '</div>'
             '<div class="exp-formula" id="fml"></div><p class="exp-note" id="hint" aria-live="polite"></p>'
             '<div class="exp-alert" id="alert" role="status" hidden></div>',
        '5': '<table class="exp-table"><thead><tr><th>序号</th><th>电源 / V</th><th>被测电压 / V</th><th>电流 / A</th><th>U/I / Ω</th></tr></thead>'
             '<tbody id="rows"></tbody></table>',
        '6': '<h3>原理</h3><p>' + principle + '</p><h3>易错点</h3><p>电流表应串联，电压表应并联；红接线柱接高电势端。量程不足时应换用合适量程，不能把满偏刻度当成真实值。</p>'
             '<h3>探究问题</h3><p>' + description + '</p><h3>结论</h3><p>用多组测量数据检验规律，控制变量并比较计算结果。</p>'
             '<h3>注意事项</h3><p>本页为线性直流虚拟仿真实验，电表采用理想模型。需要教师复核后用于教学；实物接线应先断开开关。</p>',
        'css': '#cv{display:block;width:100%;height:100%}.exp-stage>h2{display:flex;align-items:center;justify-content:space-between;gap:8px;flex-wrap:wrap}.exp-stage #btn-enlarge{white-space:nowrap;margin-left:auto}.exp-info .exp-tag.is-plain{max-width:100%;box-sizing:border-box;white-space:normal;overflow-wrap:anywhere}@media(max-width:760px){.pf-side .pf-tip{max-width:180px;white-space:normal;text-align:center}}',
        'js': 'window.__CONFIG__={scene_engine:"circuit",scene_id:' + json.dumps('voltmeter_ammeter_resistance' if recipe == 'resistance' else ('voltage_divider' if recipe == 'voltage_divider' else 'ohm')) + '};\n'
              'window.__DATA__={};\nwindow.__CIRCUIT_INITIAL__=' + encoded + ';\n'
              'CIRCUIT_PAGE.mount(document.getElementById("cv"), window.__CIRCUIT_INITIAL__);',
    }
