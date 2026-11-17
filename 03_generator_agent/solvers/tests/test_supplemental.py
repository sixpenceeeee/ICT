# -*- coding: utf-8 -*-
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from supplemental import (
    solve_binary,
    solve_climate,
    solve_enzyme,
    solve_food_web,
    solve_population_density,
    solve_respiration,
    solve_scale_distance,
    solve_sensor,
    solve_statistics,
)


class SupplementalSolverTests(unittest.TestCase):
    def test_biology_metamorphic(self):
        self.assertGreater(solve_respiration({"tidal_volume_l": 1, "respiratory_rate": 20})["minute_ventilation_l_min"],
                           solve_respiration({"tidal_volume_l": .5, "respiratory_rate": 20})["minute_ventilation_l_min"])
        low = solve_food_web({"producer_energy": 1000, "transfer_efficiency": .1, "levels": 4})["energies"]
        self.assertTrue(all(a >= b for a, b in zip(low, low[1:])))
        self.assertGreater(solve_enzyme({"substrate": 80, "temperature": 37, "ph": 7})["rate"],
                           solve_enzyme({"substrate": 10, "temperature": 37, "ph": 7})["rate"])

    def test_geography_metamorphic(self):
        self.assertAlmostEqual(solve_scale_distance({"map_distance_cm": 6, "scale_denominator": 100000})["actual_distance_km"], 2 * solve_scale_distance({"map_distance_cm": 3, "scale_denominator": 100000})["actual_distance_km"])
        climate = solve_climate({"monthly_temps": [0] * 12, "monthly_rain": [100] * 12})
        self.assertEqual(climate["annual_precipitation"], 1200)
        self.assertAlmostEqual(solve_population_density({"population": 200000, "area_km2": 250})["density_per_km2"], 800)

    def test_informatics_metamorphic(self):
        b = solve_binary({"bits": "1011"})
        self.assertEqual((b["decimal"], b["bit_count"], b["bytes"]), (11, 4, 1))
        s = solve_statistics({"values": [2, 4, 6]})
        self.assertEqual((s["mean"], s["median"]), (4, 4))
        self.assertEqual(solve_sensor({"period_s": .5, "threshold": 50, "value": 60})["state"], "触发")
        self.assertEqual(solve_sensor({"period_s": .5, "threshold": 70, "value": 60})["state"], "未触发")


if __name__ == "__main__":
    unittest.main()
