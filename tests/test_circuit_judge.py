"""独立 Python 电路复算：真实内核正例与篡改读数反例。"""
import copy
import importlib
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / '04_review_agent'))
from circuit_resources import resolve_plan


class CircuitJudgeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.presets = {}
        for recipe in ('ohm', 'resistance', 'series', 'parallel'):
            config, solution = resolve_plan({'recipe': recipe})
            cls.presets[recipe] = {'config': config, 'solution': solution}

    def verify(self, data):
        self.assertTrue((ROOT / '04_review_agent' / 'circuit_judge.py').exists(),
                        '缺少独立 Python 电路复算器')
        return importlib.import_module('circuit_judge').verify_circuit(data)

    def solved(self, recipe, **params):
        config, solution = resolve_plan({'recipe': recipe, 'params': params})
        return {'config': config, 'solution': solution}

    def assert_rejected(self, data, field=None):
        result = self.verify(data)
        self.assertFalse(result['ok'], result)
        self.assertTrue(result['issues'], result)
        if field:
            self.assertIn(field, ' '.join(result['issues']))
        return result

    def test_all_presets_match_independently_derived_readings(self):
        for recipe, current, voltage in [('ohm', .6, 6), ('resistance', .3, 3),
                                         ('series', .2, 2), ('parallel', .9, 6)]:
            with self.subTest(recipe=recipe):
                result = self.verify(copy.deepcopy(self.presets[recipe]))
                self.assertTrue(result['ok'], result)
                self.assertEqual(result['issues'], [])
                self.assertAlmostEqual(result['expected']['totalCurrent'], current)
                self.assertAlmostEqual(result['expected']['measuredVoltage'], voltage)
                self.assertAlmostEqual(result['expected']['resistorVoltages']['R1'], voltage)
                self.assertAlmostEqual(result['expected']['resistorCurrents']['R1'], voltage / 10)

    def test_parameters_derive_readings_instead_of_using_default_constants(self):
        for recipe, params, current, voltage in [
            ('ohm', {'voltage': 9, 'resistance': 15}, .6, 9),
            ('series', {'voltage': 12, 'resistance': 40, 'resistance2': 20}, .2, 8),
            ('parallel', {'voltage': 3, 'resistance': 5, 'resistance2': 15}, .8, 3),
            ('resistance', {'voltage': 9, 'resistance': 15, 'maxResistance': 60, 'position': .5}, .2, 3),
        ]:
            with self.subTest(recipe=recipe):
                result = self.verify(self.solved(recipe, **params))
                self.assertTrue(result['ok'], result)
                self.assertAlmostEqual(result['expected']['totalCurrent'], current)
                self.assertAlmostEqual(result['expected']['measuredVoltage'], voltage)

    def test_open_switch_has_zero_load_readings_and_source_stays_energized(self):
        for recipe in self.presets:
            with self.subTest(recipe=recipe):
                data = self.solved(recipe, closed=False)
                result = self.verify(data)
                self.assertTrue(result['ok'], result)
                self.assertEqual(result['expected']['totalCurrent'], 0)
                self.assertEqual(result['expected']['measuredVoltage'], 0)
                self.assertEqual(result['expected']['sourceVoltage'], 6)
                self.assertIsNone(result['expected']['equivalentResistance'])
                data['solution']['components']['R1']['voltage'] = 6
                self.assert_rejected(data, 'R1.voltage')

    def test_zero_voltage_is_valid_even_when_status_is_not_used(self):
        for recipe in self.presets:
            with self.subTest(recipe=recipe):
                data = self.solved(recipe, voltage=0)
                data['solution']['status'] = 'open'
                result = self.verify(data)
                self.assertTrue(result['ok'], result)
                self.assertEqual(result['expected']['totalCurrent'], 0)
                self.assertGreater(result['expected']['equivalentResistance'], 0)

    def test_rheostat_endpoints_zero_and_full_resistance(self):
        for position, current in [(0, .6), (1, .1)]:
            with self.subTest(position=position):
                data = self.solved('resistance', position=position)
                result = self.verify(data)
                self.assertTrue(result['ok'], result)
                self.assertAlmostEqual(result['expected']['totalCurrent'], current)

    def test_component_order_wire_order_direction_and_layout_do_not_change_physics(self):
        data = copy.deepcopy(self.presets['resistance'])
        data['config']['components'].reverse()
        for component in data['config']['components']:
            component.update(x=10, y=700)
        data['config']['wires'].reverse()
        for wire in data['config']['wires']:
            wire['from'], wire['to'] = wire['to'], wire['from']
        self.assertTrue(self.verify(data)['ok'])

    def test_pass_does_not_trust_self_reported_ok_or_data_checks(self):
        data = copy.deepcopy(self.presets['ohm'])
        data['solution']['ok'] = False
        data['checks'] = [{'ok': False}]
        with patch('subprocess.run', side_effect=AssertionError('不得调用 JS 内核')):
            self.assertTrue(self.verify(data)['ok'])
        data['solution']['ok'] = True
        data['checks'] = [{'ok': True}]
        data['solution']['totalCurrent'] = 99
        self.assert_rejected(data, 'totalCurrent')

    def test_each_reported_component_quantity_is_checked(self):
        for component, fields in {
            'V1': ('current', 'voltage', 'value'),
            'A1': ('current', 'voltage', 'value', 'range'),
            'M1': ('current', 'voltage', 'value', 'range'),
            'R1': ('current', 'voltage', 'value'),
            'S1': ('voltage', 'value'),
        }.items():
            for field in fields:
                with self.subTest(component=component, field=field):
                    data = copy.deepcopy(self.presets['ohm'])
                    data['solution']['components'][component][field] += 1
                    self.assert_rejected(data, component + '.' + field)
        for recipe, component in [('series', 'R2'), ('parallel', 'R2'), ('resistance', 'RH1')]:
            for field in ('current', 'voltage', 'value'):
                with self.subTest(recipe=recipe, component=component, field=field):
                    data = copy.deepcopy(self.presets[recipe])
                    data['solution']['components'][component][field] += 1
                    self.assert_rejected(data, component + '.' + field)

    def test_total_current_supply_equivalent_and_node_potentials_cannot_be_spoofed(self):
        for field in ('totalCurrent', 'sourceVoltage', 'equivalentResistance'):
            with self.subTest(field=field):
                data = copy.deepcopy(self.presets['series'])
                data['solution'][field] += 1
                self.assert_rejected(data, field)
        data = copy.deepcopy(self.presets['series'])
        data['solution']['nodeVoltages']['R1.b'] += 1
        self.assert_rejected(data, 'nodeVoltages.R1.b')

    def test_source_current_sign_and_meter_polarity_are_checked(self):
        for component, field in [('V1', 'current'), ('A1', 'current'), ('M1', 'voltage')]:
            with self.subTest(component=component):
                data = copy.deepcopy(self.presets['ohm'])
                data['solution']['components'][component][field] *= -1
                self.assert_rejected(data, component + '.' + field)

    def test_meter_overrange_matches_actual_reading_and_range(self):
        data = self.solved('ohm', ammeterRange=.1, voltmeterRange=3)
        result = self.verify(data)
        self.assertTrue(result['ok'], result)
        self.assertEqual(result['expected']['overrange'], {'A1': True, 'M1': True})
        for component in ('A1', 'M1'):
            tampered = copy.deepcopy(data)
            tampered['solution']['components'][component]['overrange'] = False
            self.assert_rejected(tampered, component + '.overrange')
        data = self.solved('ohm', ammeterRange=.6, voltmeterRange=6)
        self.assertEqual(self.verify(data)['expected']['overrange'], {'A1': False, 'M1': False})

    def test_missing_or_disguised_connections_are_rejected_despite_valid_readings(self):
        for mutate in [
            lambda c: c['wires'].pop(),
            lambda c: c['wires'].clear(),
            lambda c: c['wires'].append({'id': 'W99', 'from': 'V1.positive', 'to': 'V1.negative'}),
            lambda c: c['wires'][0].update(to='R1.b'),
            lambda c: c['wires'][0].update(to='unknown.a'),
            lambda c: c['wires'][0].update(to='A1.positive'),
            lambda c: c['wires'].append(dict(c['wires'][0], id='W99')),
            lambda c: c.update(recipe='parallel'),
        ]:
            data = copy.deepcopy(self.presets['ohm'])
            mutate(data['config'])
            self.assert_rejected(data)

    def test_wire_ids_must_be_unique_and_wires_must_be_objects(self):
        for malformed in [None, 'wire', {}, {'id': 'W1', 'from': [], 'to': 'R1.a'}]:
            with self.subTest(wire=malformed):
                data = copy.deepcopy(self.presets['ohm'])
                data['config']['wires'][1] = malformed
                self.assert_rejected(data)
        data = copy.deepcopy(self.presets['ohm'])
        data['config']['wires'][1]['id'] = data['config']['wires'][0]['id']
        self.assert_rejected(data)

    def test_component_type_ids_and_full_membership_cannot_be_disguised(self):
        for mutate in [
            lambda c: c['components'][0].update(type='resistor'),
            lambda c: c['components'][0].update(id='R1'),
            lambda c: c['components'].pop(),
            lambda c: c['components'].append(dict(c['components'][0], id='V2')),
            lambda c: c['components'].__setitem__(0, None),
        ]:
            data = copy.deepcopy(self.presets['ohm'])
            mutate(data['config'])
            self.assert_rejected(data)

    def test_invalid_parameters_are_rejected_before_any_numeric_comparison(self):
        for recipe, component, field, values in [
            ('ohm', 'V1', 'voltage', [-1, True, '6', float('nan'), float('inf')]),
            ('ohm', 'R1', 'resistance', [0, -1, True, None, float('inf')]),
            ('ohm', 'A1', 'range', [0, -1, True, float('nan')]),
            ('ohm', 'M1', 'range', [0, float('inf')]),
            ('ohm', 'S1', 'closed', [0, 1, None, 'true']),
            ('resistance', 'RH1', 'maxResistance', [0, -1, float('nan')]),
            ('resistance', 'RH1', 'position', [-.1, 1.1, True, float('nan')]),
        ]:
            for value in values:
                with self.subTest(recipe=recipe, component=component, field=field, value=value):
                    data = copy.deepcopy(self.presets[recipe])
                    item = next(c for c in data['config']['components'] if c['id'] == component)
                    item['params'][field] = value
                    self.assert_rejected(data)

    def test_nonfinite_or_missing_measurements_never_pass(self):
        for value in (float('nan'), float('inf'), -float('inf'), '0.6', True, None):
            for field in ('totalCurrent', 'sourceVoltage', 'equivalentResistance'):
                with self.subTest(field=field, value=value):
                    data = copy.deepcopy(self.presets['ohm'])
                    data['solution'][field] = value
                    self.assert_rejected(data, field)
            data = copy.deepcopy(self.presets['ohm'])
            data['solution']['components']['R1']['current'] = value
            self.assert_rejected(data, 'R1.current')
        for mutate in [
            lambda s: s.pop('totalCurrent'),
            lambda s: s['components'].pop('A1'),
            lambda s: s['components']['M1'].pop('voltage'),
            lambda s: s['components']['S1'].update(current=1),
            lambda s: s['nodeVoltages'].pop('V1.negative'),
            lambda s: s['components']['M1'].update(overrange=0),
        ]:
            data = copy.deepcopy(self.presets['ohm'])
            mutate(data['solution'])
            self.assert_rejected(data)

    def test_invalid_input_shapes_return_diagnostics_without_raising(self):
        for value in (None, [], 'circuit', {}, {'config': {}},
                      {'config': self.presets['ohm']['config'], 'solution': []}):
            with self.subTest(value=value):
                result = self.assert_rejected(value)
                self.assertIsInstance(result['expected'], dict)

    def test_small_linear_solver_roundoff_is_accepted_without_mutating_input(self):
        data = copy.deepcopy(self.presets['ohm'])
        data['solution']['totalCurrent'] += 1e-9
        before = copy.deepcopy(data)
        self.assertTrue(self.verify(data)['ok'])
        self.assertEqual(data, before)

    def test_voltage_divider_mna_solver_and_verification(self):
        for pos in (0.2, 0.5, 0.8):
            with self.subTest(pos=pos):
                config, solution = resolve_plan({'recipe': 'voltage_divider', 'params': {'position': pos}})
                data = {'config': config, 'solution': solution}
                result = self.verify(data)
                self.assertTrue(result['ok'], result)
                self.assertEqual(result['issues'], [])
                r_a = 50 * pos
                r_b = 50 * (1 - pos)
                r_p = (r_b * 10) / (r_b + 10)
                r_tot = r_a + r_p
                i_tot = 6.0 / r_tot
                v_p = i_tot * r_p
                i_load = v_p / 10.0
                self.assertAlmostEqual(result['expected']['totalCurrent'], i_tot, places=5)
                self.assertAlmostEqual(result['expected']['components']['M1']['voltage'], v_p, places=5)
                self.assertAlmostEqual(result['expected']['components']['A1']['current'], i_load, places=5)

    def test_voltage_divider_tampered_readings_rejected(self):
        config, solution = resolve_plan({'recipe': 'voltage_divider'})
        data = {'config': config, 'solution': solution}
        tampered = copy.deepcopy(data)
        tampered['solution']['totalCurrent'] += 0.5
        self.assert_rejected(tampered, 'totalCurrent')
        tampered = copy.deepcopy(data)
        tampered['solution']['components']['M1']['voltage'] = 5.0
        self.assert_rejected(tampered, 'M1.voltage')
        tampered = copy.deepcopy(data)
        tampered['solution']['components']['A1']['current'] = 0.5
        self.assert_rejected(tampered, 'A1.current')

    def test_python_mna_solver_short_and_floating_fault_diagnostics(self):
        judge = importlib.import_module('circuit_judge')
        short_config = {
            'schema_version': 1,
            'recipe': 'custom_short',
            'components': [
                {'id': 'V1', 'type': 'power_supply', 'params': {'voltage': 6}},
                {'id': 'R1', 'type': 'resistor', 'params': {'resistance': 10}}
            ],
            'wires': [
                {'id': 'W1', 'from': 'V1.positive', 'to': 'V1.negative'},
                {'id': 'W2', 'from': 'V1.positive', 'to': 'R1.a'},
                {'id': 'W3', 'from': 'R1.b', 'to': 'V1.negative'}
            ]
        }
        res_short = judge.verify_circuit({'config': short_config, 'solution': {}})
        self.assertFalse(res_short['ok'])
        self.assertTrue(any('SOURCE_SHORT' in issue for issue in res_short['issues']))

        floating_config = {
            'schema_version': 1,
            'recipe': 'custom_floating',
            'components': [
                {'id': 'V1', 'type': 'power_supply', 'params': {'voltage': 6}},
                {'id': 'R1', 'type': 'resistor', 'params': {'resistance': 10}},
                {'id': 'R2', 'type': 'resistor', 'params': {'resistance': 20}}
            ],
            'wires': [
                {'id': 'W1', 'from': 'V1.positive', 'to': 'R1.a'},
                {'id': 'W2', 'from': 'R1.b', 'to': 'V1.negative'}
            ]
        }
        res_float = judge.verify_circuit({'config': floating_config, 'solution': {}})
        self.assertFalse(res_float['ok'])
        self.assertTrue(any('FLOATING_SUBCIRCUIT' in issue for issue in res_float['issues']))

    def test_pure_python_mna_matches_analytical_presets(self):
        judge = importlib.import_module('circuit_judge')
        for recipe in ('ohm', 'resistance', 'series', 'parallel'):
            with self.subTest(recipe=recipe):
                cfg = self.presets[recipe]['config']
                mna_res = judge._solve_mna_python(cfg)
                analytical_res = judge._derive(recipe, {c['id']: c for c in cfg['components']})
                self.assertAlmostEqual(mna_res['totalCurrent'], analytical_res['totalCurrent'], places=7)
                self.assertAlmostEqual(mna_res['sourceVoltage'], analytical_res['sourceVoltage'], places=7)
                self.assertAlmostEqual(mna_res['components']['A1']['current'], analytical_res['components']['A1']['current'], places=7)
                self.assertAlmostEqual(mna_res['components']['M1']['voltage'], analytical_res['components']['M1']['voltage'], places=7)


if __name__ == '__main__':
    unittest.main()
