# -*- coding: utf-8 -*-
"""组件层公共出口。

上层只应该 `from components import ...`，不要直接引用 registry 内部结构，
这样以后换实现（例如把组件树换成前端模板）不会波及调用方。
"""

from . import atoms, controls, readouts, records, registry, runtime, stage, teaching

from .registry import COMPONENT_CSS, LESSON_CSS, STAGE_CSS, PARTS, Rendered, Part, assemble, contract
from .runtime import mount_script, presentation_js

__all__ = [
    "atoms", "controls", "readouts", "records", "registry", "runtime", "stage", "teaching",
    "COMPONENT_CSS", "LESSON_CSS", "STAGE_CSS", "PARTS", "Rendered", "Part",
    "assemble", "contract", "mount_script", "presentation_js",
]
