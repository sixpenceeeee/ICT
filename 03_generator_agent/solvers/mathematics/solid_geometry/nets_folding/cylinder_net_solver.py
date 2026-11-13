# -*- coding: utf-8 -*-
"""Check a cylinder's rectangular lateral net and two circular caps."""
import math


def solve_cylinder_net(request):
    """Validate measured net dimensions and map the rectangle onto a cylinder.

    Request format::

        {"radius": 2, "height": 5,
         "net": {"lateral_width": 4*pi, "lateral_height": 5,
                 "cap_radii": [2, 2]}, "segments": 32}
    """
    if not isinstance(request, dict):
        raise ValueError("圆柱展开求解请求必须是对象")
    net = request.get("net")
    if not isinstance(net, dict):
        raise ValueError("net 必须包含侧面矩形尺寸和两个底圆半径")
    try:
        radius = float(request.get("radius"))
        height = float(request.get("height"))
        lateral_width = float(net.get("lateral_width"))
        lateral_height = float(net.get("lateral_height"))
        cap_radii = [float(x) for x in net.get("cap_radii", [])]
    except (TypeError, ValueError) as exc:
        raise ValueError("圆柱半径、高、展开尺寸和底圆半径必须是数值") from exc
    try:
        raw_tolerance = request.get("tolerance")
        tolerance = float(1e-8 if raw_tolerance is None else raw_tolerance)
    except (TypeError, ValueError) as exc:
        raise ValueError("几何容差必须为数值") from exc
    segments = request.get("segments", 32)
    if type(segments) is not int:
        raise ValueError("圆周采样段数必须是整数")
    if any(not math.isfinite(x) or x <= 0 for x in (radius, height, lateral_width, lateral_height)):
        raise ValueError("圆柱半径、高和展开矩形尺寸必须为有限正数")
    if len(cap_radii) != 2 or any(not math.isfinite(x) or x <= 0 for x in cap_radii):
        raise ValueError("圆柱展开图必须包含两个有限正数半径的底圆")
    if not math.isfinite(tolerance) or tolerance < 0:
        raise ValueError("几何容差必须为有限非负数")
    if not 8 <= segments <= 128:
        raise ValueError("圆周采样段数必须在 8 到 128 之间")

    circumference = 2*math.pi*radius
    lateral_area = circumference*height
    cap_area = 2*math.pi*radius*radius
    surface_area = lateral_area+cap_area
    net_area = lateral_width*lateral_height + math.pi*sum(r*r for r in cap_radii)
    if not all(math.isfinite(x) for x in (circumference, lateral_area, cap_area, surface_area, net_area)):
        raise ValueError("圆柱展开几何量超出有限数值范围")

    eps = tolerance*max(1.0, radius, height, circumference)
    checks = {
        "lateral_width_matches_circumference": abs(lateral_width-circumference) <= eps,
        "lateral_height_matches_solid_height": abs(lateral_height-height) <= eps,
        "two_caps_match_radius": all(abs(r-radius) <= eps for r in cap_radii),
        "area_conserved": abs(net_area-surface_area) <= max(1e-12, tolerance*max(1.0, surface_area)),
        "finite": True,
    }
    valid = all(checks.values())
    if valid:
        reason = "合法圆柱展开图"
    elif not checks["lateral_width_matches_circumference"]:
        reason = "侧面展开矩形宽度必须等于圆柱底面周长"
    elif not checks["lateral_height_matches_solid_height"]:
        reason = "侧面展开矩形高度必须等于圆柱高"
    elif not checks["two_caps_match_radius"]:
        reason = "两个底圆半径必须等于圆柱底面半径"
    else:
        reason = "展开前后表面积不守恒"

    bottom_z, top_z = -height/2, height/2
    surface_grid = [[], []]
    for i in range(segments+1):
        angle = 2*math.pi*i/segments
        x, y = radius*math.cos(angle), radius*math.sin(angle)
        surface_grid[0].append([x, y, bottom_z])
        surface_grid[1].append([x, y, top_z])
    return {
        "solid": "cylinder", "radius": radius, "height": height,
        "net": {"lateral_width": lateral_width, "lateral_height": lateral_height,
                "cap_radii": cap_radii},
        "circumference": circumference, "lateral_area": lateral_area,
        "cap_area": cap_area, "surface_area": surface_area,
        "net_area": net_area, "area_error": abs(net_area-surface_area),
        "relative_area_error": abs(net_area-surface_area)/surface_area,
        "segments": segments,
        "fold_map": {"angle_per_length": 2*math.pi/lateral_width,
                     "height_min": bottom_z, "height_max": top_z},
        "surface_grid": surface_grid,
        "bottom_cap": {"center": [0, 0, bottom_z], "radius": radius},
        "top_cap": {"center": [0, 0, top_z], "radius": radius},
        "valid": valid, "reason": reason, "checks": checks,
    }
