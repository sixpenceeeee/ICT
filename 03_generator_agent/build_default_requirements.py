# -*- coding: utf-8 -*-
"""Create default requirement JSON files for every math/physics/chemistry scene."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import scene_registry  # noqa: E402

OUT = ROOT.parent / "runs" / "default_scene_requirements"


# Defaults for solver-backed chemistry scenes.  The generic scene registry
# intentionally does not invent chemistry, so the batch runner must provide a
# reviewed, deterministic example for each solver contract.
CHEMISTRY_DEFAULTS = {
    "chemistry-solubility-ksp": {
        "固体化学式": "CaF2", "Ksp": 4e-11,
        "离子初始浓度": {"Ca": 0.0, "F": 0.0},
    },
    "chemistry-acid-base-titration": {
        "acid": {"formula": "HCl", "concentration_mol_L": 0.1, "volume": 25, "volume_unit": "mL"},
        "base": {"formula": "NaOH", "concentration_mol_L": 0.1, "volume": 0, "volume_unit": "mL"},
    },
    "chemistry-precipitation-quantitative": {
        "solutions": [
            {"formula": "AgNO3", "concentration_mol_L": 0.1, "volume": 50, "volume_unit": "mL"},
            {"formula": "NaCl", "concentration_mol_L": 0.1, "volume": 40, "volume_unit": "mL"},
        ],
        "progress": 1.0,
    },
    "chemistry-gas-collection": {
        "reactants": [{"formula": "Zn", "amount_mol": 0.02}, {"formula": "HCl", "amount_mol": 0.05}],
        "products": [{"formula": "ZnCl2", "phase": "aq"}, {"formula": "H2", "phase": "g"}],
        "gas_formula": "H2", "progress": 1.0, "temperature_c": 25,
        "total_pressure_kpa": 101.325, "collection_method": "over_water",
    },
    "chemistry-stoichiometry-limiting-reagent": {
        "reactants": [{"formula": "Zn", "phase": "s"}, {"formula": "HCl", "phase": "aq"}],
        "products": [{"formula": "ZnCl2", "phase": "aq"}, {"formula": "H2", "phase": "g"}],
        "initial_amounts_mol": [0.02, 0.05], "progress": 1.0,
    },
    "chemistry-equation-balance": {
        "reactants": [{"formula": "Zn", "phase": "s"}, {"formula": "HCl", "phase": "aq"}],
        "products": [{"formula": "ZnCl2", "phase": "aq"}, {"formula": "H2", "phase": "g"}],
    },
    "chemistry-reaction-compare": {
        "reactants": [{"formula": "Zn", "phase": "s"}, {"formula": "HCl", "phase": "aq"}],
        "products": [{"formula": "ZnCl2", "phase": "aq"}, {"formula": "H2", "phase": "g"}],
    },
}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    created = []
    for skeleton in scene_registry.SCENE_SKELETONS:
        subject = skeleton.get("subject")
        if subject not in {"数学", "物理", "化学"}:
            continue
        scene_id = skeleton["id"]
        config = scene_registry.scene_config(scene_id)
        model = skeleton.get("lesson_model") or {}
        inputs = model.get("inputs", {})
        cases = model.get("cases", {})
        default_case = next(iter(cases.values()), {}) if isinstance(cases, dict) else {}
        title = model.get("title") or scene_id
        req = {
            "学科": subject,
            "年级": "高中一年级" if subject == "数学" else ("初中八年级" if subject == "物理" else "高中一年级"),
            "实验名称": title,
            "实验主题": title,
            "学习目标": [f"理解{title}中的核心规律", "改变关键参数并观察结果变化", "根据页面读数验证计算关系"],
            "场景配置": scene_id,
            "页面模块": config.get("components", []),
            "交互要求": config.get("required", []) + ["提供重置、记录和结果反馈"],
            "求解器": config.get("solver_api") or skeleton.get("solver_api"),
            "默认参数": default_case,
            "参数字段": inputs,
            "模式": config.get("mode", "计算型" if config.get("solver_api") else "展示型"),
        }
        if scene_id in CHEMISTRY_DEFAULTS:
            defaults = json.loads(json.dumps(CHEMISTRY_DEFAULTS[scene_id], ensure_ascii=False))
            req["默认参数"] = defaults
            req["参数字段"] = defaults
            # Resolvers consume the normalized request itself.  Keep the
            # nested metadata for inspection, but also expose the reviewed
            # defaults at the top level for deterministic batch generation.
            req.update(defaults)
        path = OUT / f"{scene_id}.json"
        path.write_text(json.dumps(req, ensure_ascii=False, indent=2), encoding="utf-8")
        created.append(str(path))
    print(json.dumps({"output_dir": str(OUT), "count": len(created), "files": created}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
