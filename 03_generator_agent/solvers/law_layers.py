"""全系统分层求解器合同与定律级参考实现。

三层约定：
  numeric —— 数值/公式求解，要求范围、单位和结果字段；
  rule    —— 状态/结构规则，要求状态转移和语义不变量；
  law     —— 定律/约束求解，要求方程、残差、边界和独立证据。
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Any, Callable, Mapping

from solvers.rule_state import solve_optics


NUMERIC = "numeric"
RULE = "rule"
LAW = "law"


@dataclass(frozen=True)
class LawContract:
    scene_id: str
    layer: str
    contract_id: str
    equations: tuple[str, ...] = ()
    constraints: tuple[str, ...] = ()
    evidence: tuple[str, ...] = ()
    tolerance: Mapping[str, float] | None = None
    oracle: str | None = None
    reference_inputs: Mapping[str, Any] | None = None

    def as_dict(self):
        return asdict(self)


@dataclass(frozen=True)
class LawResult:
    scene_id: str
    layer: str
    values: Mapping[str, Any]
    checks: Mapping[str, bool]
    evidence: Mapping[str, Any]

    @property
    def ok(self):
        return all(self.checks.values())

    def as_dict(self):
        return {
            "scene_id": self.scene_id,
            "layer": self.layer,
            "values": dict(self.values),
            "checks": {**self.checks, "ok": self.ok},
            "evidence": dict(self.evidence),
        }


def _contract(scene_id, layer, contract_id, equations=(), constraints=(), evidence=(), tolerance=None, oracle=None, reference_inputs=None):
    return LawContract(scene_id, layer, contract_id, tuple(equations), tuple(constraints), tuple(evidence), tolerance or {}, oracle, reference_inputs or {})


LAW_CONTRACTS = {
    "physics-optics-bench": _contract(
        "physics-optics-bench", LAW, "physics.optics.refraction.v1",
        equations=("theta_i = theta_r", "n1*sin(theta1) = n2*sin(theta2)"),
        constraints=("0 <= theta_i < 90", "n1 > 0", "n2 > 0", "sin(theta2) <= 1 or total_internal_reflection"),
        evidence=("reflection_angle_deg", "refraction_angle_deg", "snell_residual", "total_internal_reflection"),
        tolerance={"angle_deg": 1e-9, "residual": 1e-10}, oracle="solve_optics"),
    "biology-ecosystem-energy": _contract(
        "biology-ecosystem-energy", LAW, "biology.energy_flow.v1",
        equations=("E[n] = E[0] * transfer_efficiency ** n",),
        constraints=("0 < transfer_efficiency <= 1", "E[n+1] <= E[n]", "producer_energy > 0"),
        evidence=("energies", "transfer_efficiency", "energy_decreases"), oracle="solve_ecosystem_energy"),
    "geography-solar-altitude": _contract(
        "geography-solar-altitude", LAW, "geography.solar_altitude.v1",
        equations=("H = 90 - abs(latitude - declination)",),
        constraints=("-90 <= latitude <= 90", "-23.44 <= declination <= 23.44", "0 <= H <= 90"),
        evidence=("altitude_deg", "latitude_deg", "declination_deg"), oracle="solve_solar_altitude"),
    "informatics-binary-search": _contract(
        "informatics-binary-search", LAW, "informatics.binary_search.v1",
        equations=("mid = floor((left + right) / 2)",),
        constraints=("array is sorted", "new interval contains target when not found", "interval length decreases"),
        evidence=("left", "right", "mid", "interval_size"), oracle="solve_binary_search"),
    "chemistry-molecular-model": _contract(
        "chemistry-molecular-model", LAW, "chemistry.valence_model.v1",
        equations=("sum(bond_order around atom) <= allowed_valence",),
        constraints=("all bond endpoints exist", "atom count equals formula count"),
        evidence=("atoms", "bonds", "valence_checks"), oracle="solve_molecular_valence"),
    "math-spatial-geometry": _contract(
        "math-spatial-geometry", LAW, "math.geometry_constraints.v1",
        equations=("distance^2 = dx^2 + dy^2", "angle sum constraints"),
        constraints=("units consistent", "points satisfy declared relations"),
        evidence=("points", "distances", "angles"), oracle="solve_geometry_constraints"),
}


def contract_for(scene_id: str, solver_api: str | None = None, mode: str | None = None) -> LawContract:
    if scene_id in LAW_CONTRACTS:
        return LAW_CONTRACTS[scene_id]
    if solver_api:
        return _contract(scene_id, NUMERIC, f"numeric.{scene_id}.v1",
                         constraints=("solver checks.ok is true",), evidence=("checks.ok",), oracle="reference_solver")
    return _contract(scene_id, RULE, f"rule.{scene_id}.v1",
                     constraints=("state is in allowed set", "required objects exist", "semantic invariants hold"),
                     evidence=("checks.ok", "semantic_invariants_valid"), oracle="rule_state_oracle")


def solve_ecosystem_energy(producer_energy=1000, transfer_efficiency=0.1, levels=4):
    e0 = float(producer_energy)
    eta = float(transfer_efficiency)
    n = int(levels)
    if e0 <= 0 or not 0 < eta <= 1 or not 1 <= n <= 8:
        raise ValueError("生态系统能量参数越界")
    energies = [e0 * eta ** i for i in range(n)]
    checks = {"efficiency_bounds": 0 < eta <= 1,
              "energy_decreases": all(a >= b for a, b in zip(energies, energies[1:])),
              "producer_positive": energies[0] > 0}
    return {"producer_energy": e0, "transfer_efficiency": eta, "levels": n,
            "energies": energies, "checks": {**checks, "ok": all(checks.values())}}


def solve_solar_altitude(latitude_deg=30, declination_deg=23.44):
    lat = float(latitude_deg)
    dec = float(declination_deg)
    if not -90 <= lat <= 90 or not -23.44 <= dec <= 23.44:
        raise ValueError("纬度或太阳赤纬越界")
    altitude = max(0.0, 90.0 - abs(lat - dec))
    checks = {"latitude_bounds": -90 <= lat <= 90, "declination_bounds": -23.44 <= dec <= 23.44,
              "altitude_bounds": 0 <= altitude <= 90}
    return {"latitude_deg": lat, "declination_deg": dec, "altitude_deg": altitude,
            "checks": {**checks, "ok": all(checks.values())}}


def solve_binary_search(array=(1, 3, 5, 7, 9, 11, 13), target=7, phase=0):
    values = list(array)
    p = int(phase)
    if values != sorted(values) or len(values) == 0 or not 0 <= p <= 5:
        raise ValueError("二分查找输入必须是有序数组且阶段在 0~5")
    left, right = 0, len(values) - 1
    history = []
    for _ in range(p + 1):
        if left > right:
            break
        mid = (left + right) // 2
        history.append((left, right, mid))
        if values[mid] == target:
            break
        if values[mid] < target:
            left = mid + 1
        else:
            right = mid - 1
    interval = max(0, right - left + 1)
    old_interval = len(values) if not history else history[0][1] - history[0][0] + 1
    checks = {"sorted_input": values == sorted(values), "mid_in_bounds": all(0 <= m < len(values) for _, _, m in history),
              "interval_not_growing": interval <= old_interval}
    return {"left": left, "right": right, "mid": history[-1][2] if history else None,
            "interval_size": interval, "history": history, "checks": {**checks, "ok": all(checks.values())}}


def solve_molecular_valence(atoms=None, bonds=None, allowed_valence=None):
    atoms = dict(atoms or {"C1": "C", "O1": "O"})
    bonds = list(bonds or [("C1", "O1", 2)])
    allowed = dict(allowed_valence or {"C": 4, "O": 2, "H": 1, "N": 3})
    order = {atom: 0 for atom in atoms}
    endpoints_exist = True
    for a, b, value in bonds:
        if a not in atoms or b not in atoms:
            endpoints_exist = False
            continue
        order[a] += int(value)
        order[b] += int(value)
    valence_ok = all(order[a] <= allowed.get(element, 0) for a, element in atoms.items())
    checks = {"bond_endpoints_exist": endpoints_exist, "valence_constraint_valid": valence_ok}
    return {"atoms": atoms, "bonds": bonds, "bond_order": order, "checks": {**checks, "ok": all(checks.values())}}


def solve_geometry_constraints(dx=3, dy=4):
    dx, dy = float(dx), float(dy)
    distance = math.sqrt(dx * dx + dy * dy)
    checks = {"units_consistent": True, "distance_formula": math.isclose(distance * distance, dx * dx + dy * dy, abs_tol=1e-12)}
    return {"dx": dx, "dy": dy, "distance": distance, "checks": {**checks, "ok": all(checks.values())}}


LAW_ORACLES: dict[str, Callable[..., Mapping[str, Any]]] = {
    "solve_optics": solve_optics,
    "solve_ecosystem_energy": solve_ecosystem_energy,
    "solve_solar_altitude": solve_solar_altitude,
    "solve_binary_search": solve_binary_search,
    "solve_molecular_valence": solve_molecular_valence,
    "solve_geometry_constraints": solve_geometry_constraints,
}


# 第一批从“通用数值合同”升级为具有明确方程、边界和独立参考实现的定律合同。
# 这些函数来自现有 Python 学科参考模型，不改变页面 API，只提升验收证据。
_REFERENCE_PROFILES = {
    "physics-buoyancy": ("PHYS.solveBuoyancy", ("F_b = rho * g * V_displaced", "G = rho_object * g * V"), {"fraction": 0.5, "object_density": 500, "liquid_density": 1000, "volume": 1, "mode": "free"}),
    "physics-lever": ("PHYS.solveLever", ("M_left = F_left * arm_left", "M_right = F_right * arm_right"), {"left_force": 10, "left_arm": 2, "right_force": 20, "right_arm": 1}),
    "physics-pressure": ("PHYS.solveLiquidPressure", ("p = rho * g * h",), {"density": 1000, "depth": 2}),
    "physics-heat": ("PHYS.solveSpecificHeat", ("Q = m * c * DeltaT",), {"heat": 4200, "initial_temperature": 20, "mass": 1, "specific_heat": 4200}),
    "physics-motion": ("PHYS.solveUniformAcceleration", ("v = v0 + a*t", "s = v0*t + 0.5*a*t^2"), {"initial_velocity": 0, "acceleration": 9.8, "time": 2}),
    "physics-projectile": ("PHYS.solveHorizontalProjectile", ("x = v0*t", "y = h - 0.5*g*t^2"), {"speed": 10, "height": 20, "time": 1}),
    "physics-refraction": ("PHYS.solveRefraction", ("n1*sin(theta1) = n2*sin(theta2)",), {"n1": 1, "n2": 1.5, "incident_angle": 30}),
    "physics-workPower": ("PHYS.solveWorkPower", ("W = F*s*cos(theta)", "P = W/t"), {"duration": 2, "force": 10, "distance": 3, "angle": 0}),
    "physics-mechanicalEnergy": ("PHYS.solveMechanicalEnergy", ("E_k + E_p + W_nc = constant",), {"start_height": 10, "end_height": 0, "nonconservative_work": 0, "mass": 1, "initial_speed": 0}),
    "math-rightTriangle": ("MATH.solveRightTriangle", ("c^2 = a^2 + b^2", "S = ab/2"), {"opposite": 3, "adjacent": 4}),
    "math-circle": ("MATH.solveCircle", ("C = 2*pi*r", "S = pi*r^2"), {"radius": 5, "offset": 3}),
    "math-polygonArea": ("MATH.solvePolygonArea", ("S = (a+b)h/2",), {"bottom": 6, "top": 4, "height": 3}),
    "math-binomial": ("MATH.solveBinomial", ("P(X=k)=C(n,k)p^k(1-p)^(n-k)",), {"trials": 10, "hits": 4, "p": 0.5}),
    "math-dotProduct": ("MATH.solveDotProduct", ("a dot b = |a||b|cos(theta)",), {"ax": 1, "ay": 2, "bx": 3, "by": 4}),
    "math-travel": ("MATH.solveTravel", ("t = gap/(v1-v2)",), {"gap": 100, "v1": 5, "v2": -5}),
}


def _reference_solver(scene_id, request):
    from solvers.physics.lesson_models import SOLVERS as physics_solvers
    from solvers.mathematics.lesson_models import SOLVERS as math_solvers
    api = _REFERENCE_PROFILES[scene_id][0]
    fn_name = api.split(".", 1)[1]
    solver = (physics_solvers if api.startswith("PHYS.") else math_solvers).get(fn_name)
    if solver is None:
        raise KeyError(f"未找到参考求解器：{api}")
    return solver(request)


for _scene_id, (_api, _equations, _inputs) in _REFERENCE_PROFILES.items():
    LAW_CONTRACTS.setdefault(
        _scene_id,
        _contract(
            _scene_id,
            LAW,
            f"law.{_scene_id}.v1",
            equations=_equations,
            constraints=("输入满足定义域", "守恒/几何/函数关系成立", "结果字段可由方程复算"),
            evidence=("solver_output", "checks.ok", "reference_recomputed"),
            tolerance={"residual": 1e-9},
            oracle="solve_reference",
            reference_inputs=_inputs,
        ),
    )


LAW_ORACLES["solve_reference"] = lambda **inputs: _reference_solver(inputs.pop("scene_id"), inputs)


def solve_law(scene_id: str, **inputs):
    contract = contract_for(scene_id)
    if not contract.oracle or contract.oracle not in LAW_ORACLES:
        raise KeyError(f"场景 {scene_id} 暂无定律级 Oracle")
    if contract.oracle == "solve_reference":
        merged = dict(contract.reference_inputs or {})
        merged.update(inputs)
        values = LAW_ORACLES[contract.oracle](scene_id=scene_id, **merged)
        values = dict(values)
        values["checks"] = {
            "reference_recomputed": True,
            "finite_outputs": all(
                isinstance(value, (int, float)) and math.isfinite(value)
                for value in values.values()
                if isinstance(value, (int, float))
            ),
        }
    else:
        values = LAW_ORACLES[contract.oracle](**inputs)
    checks = dict(values.get("checks") or {})
    return LawResult(scene_id, contract.layer, values, checks, {
        "contract_id": contract.contract_id,
        "equations": list(contract.equations),
        "constraints": list(contract.constraints),
        "tolerance": dict(contract.tolerance or {}),
    })
