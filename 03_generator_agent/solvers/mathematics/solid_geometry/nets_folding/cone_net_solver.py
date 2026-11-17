# -*- coding: utf-8 -*-
"""Check the sector-and-circle net of a right circular cone."""
import math


def solve_cone_net(request):
    """Validate a cone net and return planar and folded geometry samples.

    Request format::

        {"radius": 3, "height": 4,
         "net": {"sector_radius": 5, "sector_angle_deg": 216,
                 "cap_radius": 3}, "segments": 32}
    """
    if not isinstance(request, dict):
        raise ValueError("圆锥展开求解请求必须是对象")
    net = request.get("net")
    if not isinstance(net, dict):
        raise ValueError("net 必须包含扇形和底圆尺寸")
    try:
        radius = float(request.get("radius"))
        height = float(request.get("height"))
        sector_radius = float(net.get("sector_radius"))
        sector_angle_deg = float(net.get("sector_angle_deg"))
        cap_radius = float(net.get("cap_radius"))
    except (TypeError, ValueError) as exc:
        raise ValueError("圆锥半径、高、扇形和底圆参数必须是数值") from exc
    try:
        raw_tolerance = request.get("tolerance")
        tolerance = float(1e-8 if raw_tolerance is None else raw_tolerance)
    except (TypeError, ValueError) as exc:
        raise ValueError("几何容差必须为数值") from exc
    segments = request.get("segments", 48)
    if type(segments) is not int:
        raise ValueError("圆周采样段数必须是整数")
    if any(not math.isfinite(x) or x <= 0 for x in
           (radius, height, sector_radius, sector_angle_deg, cap_radius)):
        raise ValueError("圆锥半径、高、扇形半径/角度和底圆半径必须为有限正数")
    if not 0 < sector_angle_deg < 360:
        raise ValueError("圆锥展开扇形角必须大于 0° 且小于 360°")
    if not math.isfinite(tolerance) or tolerance < 0:
        raise ValueError("几何容差必须为有限非负数")
    if not 8 <= segments <= 128:
        raise ValueError("圆周采样段数必须在 8 到 128 之间")

    slant_height = math.hypot(radius, height)
    expected_angle_rad = 2*math.pi*radius/slant_height
    expected_angle_deg = math.degrees(expected_angle_rad)
    actual_angle_rad = math.radians(sector_angle_deg)
    lateral_area = math.pi*radius*slant_height
    cap_area = math.pi*radius*radius
    surface_area = lateral_area+cap_area
    sector_area = 0.5*sector_radius*sector_radius*actual_angle_rad
    net_area = sector_area+math.pi*cap_radius*cap_radius
    if not all(math.isfinite(x) for x in
               (slant_height, expected_angle_rad, expected_angle_deg, lateral_area,
                cap_area, surface_area, sector_area, net_area)):
        raise ValueError("圆锥展开几何量超出有限数值范围")

    eps = tolerance*max(1.0, radius, height, slant_height)
    checks = {
        "sector_radius_matches_slant_height": abs(sector_radius-slant_height) <= eps,
        "sector_arc_matches_base_circumference": abs(sector_radius*actual_angle_rad-2*math.pi*radius) <= eps,
        "sector_angle_matches_cone": abs(sector_angle_deg-expected_angle_deg) <= math.degrees(eps/max(1.0, slant_height)),
        "cap_radius_matches_base": abs(cap_radius-radius) <= eps,
        "area_conserved": abs(net_area-surface_area) <= max(1e-12, tolerance*max(1.0, surface_area)),
        "finite": True,
    }
    valid = all(checks.values())
    if valid:
        reason = "合法圆锥展开图"
    elif not checks["sector_radius_matches_slant_height"]:
        reason = "展开扇形半径必须等于圆锥母线长"
    elif not checks["sector_arc_matches_base_circumference"] or not checks["sector_angle_matches_cone"]:
        reason = "展开扇形弧长必须等于圆锥底面周长"
    elif not checks["cap_radius_matches_base"]:
        reason = "底圆半径必须等于圆锥底面半径"
    else:
        reason = "展开前后表面积不守恒"

    sector_boundary = []
    base_boundary = []
    side_grid = [[], []]
    bottom_z, apex_z = -height/2, height/2
    for i in range(segments+1):
        angle = actual_angle_rad*i/segments
        sector_boundary.append([sector_radius*math.cos(angle), sector_radius*math.sin(angle)])
        phi = 2*math.pi*i/segments
        x, y = radius*math.cos(phi), radius*math.sin(phi)
        base_boundary.append([x, y])
        side_grid[0].append([x, y, bottom_z])
        side_grid[1].append([0.0, 0.0, apex_z])
    sector_boundary.append([0.0, 0.0])
    return {
        "solid": "cone", "radius": radius, "height": height,
        "slant_height": slant_height,
        "net": {"sector_radius": sector_radius, "sector_angle_deg": sector_angle_deg,
                "cap_radius": cap_radius},
        "expected_sector_angle_deg": expected_angle_deg,
        "sector_arc_length": sector_radius*actual_angle_rad,
        "base_circumference": 2*math.pi*radius,
        "lateral_area": lateral_area, "cap_area": cap_area,
        "surface_area": surface_area, "sector_area": sector_area,
        "net_area": net_area, "area_error": abs(net_area-surface_area),
        "relative_area_error": abs(net_area-surface_area)/surface_area,
        "segments": segments,
        "sector_boundary": sector_boundary, "base_boundary": base_boundary,
        "side_grid": side_grid,
        "base_cap": {"center": [0, 0, bottom_z], "radius": radius},
        "apex": [0, 0, apex_z],
        "fold_map": {"angle_scale": slant_height/radius,
                     "sector_angle_rad": actual_angle_rad,
                     "base_height": bottom_z, "apex_height": apex_z},
        "valid": valid, "reason": reason, "checks": checks,
    }
