# -*- coding: utf-8 -*-
"""生物、地理、信息科技第一批可复算教学求解器。

这些函数只处理明确的教学模型，不把模型结果扩展成医疗、灾害或现实工程结论。
页面端对应实现位于 frame/supplement_solver.js，测试会对 Python/JS 两端做对拍。
"""

from __future__ import annotations

import math
from statistics import median


def _finite(value, name, minimum=None, maximum=None):
    value = float(value)
    if not math.isfinite(value):
        raise ValueError(f"{name} 必须是有限数")
    if minimum is not None and value < minimum:
        raise ValueError(f"{name} 不能小于 {minimum}")
    if maximum is not None and value > maximum:
        raise ValueError(f"{name} 不能大于 {maximum}")
    return value


def solve_enzyme(request):
    substrate = _finite(request.get("substrate", 50), "底物浓度", 0, 1000)
    temperature = _finite(request.get("temperature", 37), "温度", 0, 100)
    ph = _finite(request.get("ph", 7), "pH", 0, 14)
    # 教学用钟形因子：37℃、pH7 为示例最适点，结果是相对速率。
    temp_factor = max(0.0, 1.0 - ((temperature - 37.0) / 30.0) ** 2)
    ph_factor = max(0.0, 1.0 - ((ph - 7.0) / 5.0) ** 2)
    substrate_factor = substrate / (40.0 + substrate)
    rate = temp_factor * ph_factor * substrate_factor
    return {
        "rate": rate,
        "temp_factor": temp_factor,
        "ph_factor": ph_factor,
        "substrate_factor": substrate_factor,
        "checks": {"ok": True, "bounded": 0 <= rate <= 1},
    }


def solve_respiration(request):
    tidal_volume_l = _finite(request.get("tidal_volume_l", 0.5), "潮气量", 0.05, 3)
    respiratory_rate = _finite(request.get("respiratory_rate", 16), "呼吸频率", 1, 80)
    minute_ventilation_l_min = tidal_volume_l * respiratory_rate
    return {
        "tidal_volume_l": tidal_volume_l,
        "respiratory_rate": respiratory_rate,
        "minute_ventilation_l_min": minute_ventilation_l_min,
        "checks": {"ok": True, "positive": minute_ventilation_l_min > 0},
    }


def solve_food_web(request):
    producer_energy = _finite(request.get("producer_energy", 1000), "生产者能量", 0.001, 1e9)
    transfer_efficiency = _finite(request.get("transfer_efficiency", 0.1), "传递效率", 0.001, 1)
    levels = int(_finite(request.get("levels", 4), "营养级数", 1, 8))
    energies = [producer_energy * transfer_efficiency ** i for i in range(levels)]
    return {
        "producer_energy": producer_energy,
        "transfer_efficiency": transfer_efficiency,
        "levels": levels,
        "energies": energies,
        "checks": {"ok": True, "monotonic_decrease": all(a >= b for a, b in zip(energies, energies[1:]))},
    }


def solve_scale_distance(request):
    map_distance_cm = _finite(request.get("map_distance_cm", 3), "图上距离", 0, 100000)
    scale_denominator = _finite(request.get("scale_denominator", 100000), "比例尺分母", 1, 1e9)
    actual_distance_km = map_distance_cm * scale_denominator / 100000.0
    return {
        "map_distance_cm": map_distance_cm,
        "scale_denominator": scale_denominator,
        "actual_distance_km": actual_distance_km,
        "checks": {"ok": True, "nonnegative": actual_distance_km >= 0},
    }


def solve_climate(request):
    temperatures = [float(x) for x in request.get("monthly_temps", [4, 6, 10, 15, 20, 24, 27, 26, 21, 15, 9, 5])]
    rainfall = [float(x) for x in request.get("monthly_rain", [30] * 12)]
    if len(temperatures) != 12 or len(rainfall) != 12:
        raise ValueError("气温和降水必须各提供 12 个月数据")
    if any(not math.isfinite(x) for x in temperatures + rainfall) or any(x < 0 for x in rainfall):
        raise ValueError("月数据必须为有限数，降水不能为负")
    warmest = max(range(12), key=lambda i: temperatures[i])
    coldest = min(range(12), key=lambda i: temperatures[i])
    annual_range = temperatures[warmest] - temperatures[coldest]
    annual_rain = sum(rainfall)
    mean_temp = sum(temperatures) / 12
    label = "温和型" if annual_range < 15 else ("湿润型" if annual_rain >= 800 else "季节性明显")
    return {
        "warmest_month": warmest + 1,
        "coldest_month": coldest + 1,
        "annual_temperature_range": annual_range,
        "annual_precipitation": annual_rain,
        "mean_temperature": mean_temp,
        "climate_label": label,
        "checks": {"ok": True, "twelve_months": True},
    }


def solve_population_density(request):
    population = _finite(request.get("population", 200000), "人口", 0, 1e12)
    area_km2 = _finite(request.get("area_km2", 500), "面积", 0.0001, 1e12)
    density = population / area_km2
    return {
        "population": population,
        "area_km2": area_km2,
        "density_per_km2": density,
        "checks": {"ok": True, "finite": math.isfinite(density)},
    }


def solve_binary(request):
    bits = str(request.get("bits", "1011")).strip()
    if not bits or any(ch not in "01" for ch in bits) or len(bits) > 32:
        raise ValueError("位串必须由 1~32 个 0/1 组成")
    decimal = int(bits, 2)
    return {
        "bits": bits,
        "decimal": decimal,
        "bit_count": len(bits),
        "bytes": math.ceil(len(bits) / 8),
        "states": 2 ** len(bits),
        "checks": {"ok": True, "round_trip": format(decimal, "b") == bits.lstrip("0") or decimal == 0},
    }


def solve_statistics(request):
    values = [float(x) for x in request.get("values", [2, 4, 6])]
    if not values or len(values) > 200 or any(not math.isfinite(x) for x in values):
        raise ValueError("统计数据必须是 1~200 个有限数")
    ordered = sorted(values)
    mean = sum(values) / len(values)
    return {
        "count": len(values),
        "mean": mean,
        "median": median(values),
        "minimum": ordered[0],
        "maximum": ordered[-1],
        "checks": {"ok": True, "sorted": ordered == sorted(ordered)},
    }


def solve_sensor(request):
    period_s = _finite(request.get("period_s", 0.5), "采样周期", 0.01, 60)
    threshold = _finite(request.get("threshold", 50), "阈值", -1e6, 1e6)
    value = _finite(request.get("value", 60), "传感器读数", -1e6, 1e6)
    frequency_hz = 1.0 / period_s
    state = "触发" if value >= threshold else "未触发"
    return {
        "period_s": period_s,
        "threshold": threshold,
        "value": value,
        "frequency_hz": frequency_hz,
        "state": state,
        "checks": {"ok": True, "frequency_positive": frequency_hz > 0},
    }


SOLVERS = {
    "biology-enzyme": solve_enzyme,
    "biology-respiration": solve_respiration,
    "biology-ecosystem-foodweb": solve_food_web,
    "geography-scale-distance": solve_scale_distance,
    "geography-climate-reading": solve_climate,
    "geography-population-resources": solve_population_density,
    "informatics-binary-representation": solve_binary,
    "informatics-data-visualization": solve_statistics,
    "informatics-sensor-control": solve_sensor,
}
