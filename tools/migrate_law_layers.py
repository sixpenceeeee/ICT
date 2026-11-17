# -*- coding: utf-8 -*-
"""把三层求解器合同写入所有外部场景 JSON。"""

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GEN = os.path.join(ROOT, "03_generator_agent")
sys.path.insert(0, GEN)
from solvers.law_layers import contract_for  # noqa: E402
import scene_registry  # noqa: E402


def main():
    scene_dir = os.path.join(GEN, "scenes")
    total = 0
    counts = {}
    registry = {scene["id"]: scene for scene in scene_registry.SCENE_SKELETONS}
    for name in sorted(os.listdir(scene_dir)):
        if not name.endswith(".json"):
            continue
        path = os.path.join(scene_dir, name)
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        changed = False
        for scene_id, cfg in data.items():
            registered = registry.get(scene_id, {})
            solver_api = cfg.get("solver_api") or registered.get("solver_api")
            if solver_api and cfg.get("solver_api") != solver_api:
                cfg["solver_api"] = solver_api
                changed = True
            contract = contract_for(scene_id, solver_api, cfg.get("mode"))
            payload = contract.as_dict()
            if cfg.get("solver_layer") != contract.layer or cfg.get("law_contract") != payload:
                cfg["solver_layer"] = contract.layer
                cfg["law_contract"] = payload
                changed = True
            total += 1
            counts[contract.layer] = counts.get(contract.layer, 0) + 1
        if changed:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
                f.write("\n")
    print(json.dumps({"scenes": total, "layers": counts}, ensure_ascii=False))


if __name__ == "__main__":
    main()
