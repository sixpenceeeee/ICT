# -*- coding: utf-8 -*-
"""物理教学模型的第一层自检（结果内部必须成立的恒等式）。

这些检查与求解器使用同一条物理规律，但走不同的计算路径：
例如“滑轮组”由绳路几何得到拉力，这里再用 `拉力 × 拉绳长度 = 输入功` 复核；
“功与功率”由功率积分得到功，这里再用 `F∥ · s` 复核。
只要两边对不上，说明求解器内部已经不自洽，页面不得展示正常读数。
"""

import math

from solver_contract import Audit, G, register

EIGHT = G  # 9.8 N/kg，与 lesson_models.G 保持一致


@register("solveBuoyancy")
def audit_buoyancy(request, result):
    audit = Audit("solveBuoyancy")
    volume = request.get("volume")
    fraction = result.get("fraction")
    audit.need("fraction_range", isinstance(fraction, (int, float)) and 0 <= fraction <= 1 + 1e-12,
               repr(fraction))
    if isinstance(volume, (int, float)):
        audit.same("displaced_volume", result.get("displaced_volume"), volume * (fraction or 0))
        audit.same("weight", result.get("weight"), request.get("object_density", 0) * volume * EIGHT)
    audit.same("buoyancy", result.get("buoyancy"),
               request.get("liquid_density", 0) * EIGHT * result.get("displaced_volume", 0))
    if request.get("mode") == "hang":
        audit.same("tension", result.get("tension"),
                   max(0.0, (result.get("weight") or 0) - (result.get("buoyancy") or 0)))
    else:
        audit.need("tension_absent", result.get("tension") is None, repr(result.get("tension")))
        obj, liquid = request.get("object_density"), request.get("liquid_density")
        expected = ("上浮后漂浮" if obj < liquid else "下沉" if obj > liquid else "悬浮")
        audit.one_of("state", result.get("state"), {expected})
    return audit.result()


@register("solveLever")
def audit_lever(request, result):
    audit = Audit("solveLever")
    left = request.get("left_force", 0) * request.get("left_arm", 0)
    right = request.get("right_force", 0) * request.get("right_arm", 0)
    audit.same("left_torque", result.get("left_torque"), left)
    audit.same("right_torque", result.get("right_torque"), right)
    net = result.get("net_torque")
    expected = "左侧下沉" if net > 0 else "右侧下沉" if net < 0 else "平衡"
    audit.one_of("state", result.get("state"), {expected})
    audit.same("torque_balance", (result.get("left_torque") or 0) - (result.get("right_torque") or 0), net)
    return audit.result()


@register("solveLiquidPressure")
def audit_liquid_pressure(request, result):
    audit = Audit("solveLiquidPressure")
    audit.same("pressure", result.get("pressure"), G * request.get("density", 0) * request.get("depth", 0))
    return audit.result()


@register("solveSpecificHeat")
def audit_specific_heat(request, result):
    audit = Audit("solveSpecificHeat")
    change = request.get("heat", 0) / (request.get("mass") * request.get("specific_heat"))
    audit.same("temperature_change", result.get("temperature_change"), change)
    audit.same("final_temperature", result.get("final_temperature"),
               request.get("initial_temperature", 0) + change)
    audit.need("above_absolute_zero", (result.get("final_temperature") or -273.15) >= -273.15 - 1e-9,
               repr(result.get("final_temperature")))
    return audit.result()


@register("solveUniformAcceleration")
def audit_uniform_acceleration(request, result):
    audit = Audit("solveUniformAcceleration")
    v0, acceleration, duration = (request.get("initial_velocity", 0),
                                  request.get("acceleration", 0),
                                  request.get("time", 0))
    velocity = v0 + acceleration * duration
    displacement = (v0 + velocity) / 2 * duration
    audit.same("velocity", result.get("velocity"), velocity)
    audit.same("displacement", result.get("displacement"), displacement)
    audit.need("distance_covers_displacement",
               abs(result.get("distance", 0)) + 1e-9 >= abs(displacement), repr(result.get("distance")))
    trajectory = result.get("trajectory") or []
    audit.need("trajectory_size", len(trajectory) == 5, str(len(trajectory)))
    if len(trajectory) == 5:
        audit.same("trajectory_start_time", trajectory[0][0], 0)
        audit.same("trajectory_end_time", trajectory[-1][0], duration)
        audit.same("trajectory_end_displacement", trajectory[-1][1], displacement)
        audit.same("trajectory_end_velocity", trajectory[-1][2], velocity)
    return audit.result()


@register("solveHorizontalProjectile")
def audit_horizontal_projectile(request, result):
    audit = Audit("solveHorizontalProjectile")
    speed, height, time = request.get("speed", 0), request.get("height", 0), request.get("time", 0)
    flight = math.sqrt(2 * height / G)
    elapsed = min(time, flight)
    audit.same("flight_time", result.get("flight_time"), flight)
    audit.same("range", result.get("range"), speed * flight)
    audit.same("vx", result.get("vx"), speed)
    audit.same("vy", result.get("vy"), -G * elapsed)
    audit.same("x", result.get("x"), speed * elapsed)
    expected_y = max(0.0, height - G * elapsed * elapsed / 2)
    audit.same("y", result.get("y"), expected_y)
    audit.one_of("state", result.get("state"), {"飞行中", "已到落点"})
    return audit.result()


@register("solveRefraction")
def audit_refraction(request, result):
    audit = Audit("solveRefraction")
    n1, n2 = request.get("n1", 0), request.get("n2", 0)
    incident = request.get("incident_angle", 0)
    audit.same("reflected_angle", result.get("reflected_angle"), incident)
    critical = math.degrees(math.asin(n2 / n1)) if n1 > n2 else None
    audit.same("critical_angle", result.get("critical_angle"), critical)
    state = result.get("state")
    refracted = result.get("refracted_angle")
    if state == "全反射":
        audit.need("total_reflection_has_no_image", refracted is None, repr(refracted))
        audit.need("beyond_critical", critical is not None and incident > critical)
    elif state == "临界折射":
        audit.same("critical_refraction_angle", refracted, 90)
    else:
        if refracted is not None:
            left = n1 * math.sin(math.radians(incident))
            right = n2 * math.sin(math.radians(refracted))
            audit.same("snell", left, right, rel=1e-9, abs_tol=1e-9)
    return audit.result()


@register("solveHorizontalForce")
def audit_horizontal_force(request, result):
    audit = Audit("solveHorizontalForce")
    mass = request.get("mass", 0)
    weight = mass * G
    audit.same("weight", result.get("weight"), weight)
    audit.same("normal_force", result.get("normal_force"), weight)
    limit = request.get("static_coefficient", 0) * weight
    audit.same("static_limit", result.get("static_limit"), limit)
    audit.same("acceleration", result.get("acceleration"),
               (result.get("net_force") or 0) / mass if mass else 0)
    state = result.get("state")
    audit.one_of("state", state, {"静止", "临界静止", "开始滑动", "滑动中"})
    if state in ("静止", "临界静止"):
        audit.same("static_no_acceleration", result.get("acceleration"), 0)
        audit.same("static_net_force", result.get("net_force"), 0)
        audit.same("static_contact_force", result.get("friction"), -request.get("applied_force", 0))
        audit.need("within_static_limit",
                   abs(result.get("friction") or 0) <= limit * (1 + 1e-9) + 1e-12,
                   "%r > %r" % (result.get("friction"), limit))
    else:
        audit.same("kinetic_friction", abs(result.get("friction") or 0),
                   request.get("kinetic_coefficient", 0) * weight)
        net = result.get("net_force") or 0
        if abs(net) > 1e-12:
            audit.need("acceleration_follows_net_force",
                       (result.get("acceleration") or 0) * net > 0)
    return audit.result()


@register("solveWorkPower")
def audit_work_power(request, result):
    audit = Audit("solveWorkPower")
    force, distance = request.get("force", 0), request.get("distance", 0)
    angle = request.get("angle", 0)
    duration = request.get("duration", 0)
    parallel = force * math.cos(math.radians(angle))
    audit.same("parallel_force", result.get("parallel_force"), parallel)
    audit.same("work", result.get("work"), parallel * distance)
    audit.same("average_power", result.get("average_power"), (result.get("work") or 0) / duration)
    work = result.get("work") or 0
    expected = "正功" if work > 0 else "负功" if work < 0 else "零功"
    audit.one_of("state", result.get("state"), {expected})
    return audit.result()


@register("solveMechanicalEnergy")
def audit_mechanical_energy(request, result):
    audit = Audit("solveMechanicalEnergy")
    mass = request.get("mass", 0)
    weight = mass * G
    start_kinetic = 0.5 * mass * request.get("initial_speed", 0) ** 2
    start_potential = weight * request.get("start_height", 0)
    audit.same("initial_kinetic", result.get("initial_kinetic"), start_kinetic)
    audit.same("initial_potential", result.get("initial_potential"), start_potential)
    audit.same("initial_energy", result.get("initial_energy"), start_kinetic + start_potential)
    final_kinetic = result.get("final_kinetic")
    if final_kinetic is None:
        audit.need("shortfall_positive", (result.get("energy_shortfall") or 0) > 0)
    else:
        audit.nonnegative("final_kinetic", final_kinetic)
        audit.same("final_potential", result.get("final_potential"),
                   weight * request.get("end_height", 0))
        audit.same("final_energy", result.get("final_energy"),
                   final_kinetic + (result.get("final_potential") or 0))
        audit.same("final_speed", result.get("final_speed"), math.sqrt(2 * final_kinetic / mass))
        audit.same("energy_change", result.get("energy_change"),
                   (result.get("final_energy") or 0) - result.get("initial_energy", 0))
        audit.same("work_energy_theorem", result.get("energy_change"), request.get("nonconservative_work", 0))
    return audit.result()


@register("solveInclinedPlane")
def audit_inclined_plane(request, result):
    audit = Audit("solveInclinedPlane")
    mass, length, height = request.get("mass", 0), request.get("length", 0), request.get("height", 0)
    weight = mass * G
    run = math.sqrt(max(0.0, (length - height) * (length + height)))
    audit.same("horizontal_run", result.get("horizontal_run"), run)
    audit.same("angle_deg", result.get("angle_deg"), math.degrees(math.atan2(height, run)))
    audit.same("normal_force", result.get("normal_force"), weight * run / length)
    useful = weight * height
    loss = request.get("friction_coefficient", 0) * weight * run
    total = useful + loss
    audit.same("useful_work", result.get("useful_work"), useful)
    audit.same("friction_loss", result.get("friction_loss"), loss)
    audit.same("input_work", result.get("input_work"), total)
    audit.same("friction_force", result.get("friction_force"), loss / length)
    audit.same("pull_force", result.get("pull_force"), total / length)
    audit.same("efficiency", result.get("efficiency"), 100 * useful / total if total > 0 else None)
    return audit.result()


@register("solvePulleySystem")
def audit_pulley_system(request, result):
    audit = Audit("solvePulleySystem")
    strands = result.get("supporting_strands")
    audit.positive("supporting_strands", strands)
    height = request.get("lift_height", 0)
    draw = result.get("pull_distance")
    audit.same("pull_distance", draw, strands * height)
    load, moving, drag = (request.get("load_mass", 0), request.get("moving_mass", 0),
                          request.get("rope_loss_force", 0))
    pull = result.get("pull_force")
    audit.same("pull_from_load", pull,
               (load * G + moving * G + drag * strands) / strands if strands else 0)
    useful = load * G * height
    carrier = moving * G * height
    loss = drag * (draw or 0)
    audit.same("useful_work", result.get("useful_work"), useful)
    audit.same("carrier_work", result.get("carrier_work"), carrier)
    audit.same("friction_loss", result.get("friction_loss"), loss)
    audit.same("input_work", result.get("input_work"), useful + carrier + loss)
    audit.same("input_equals_pull_times_draw", result.get("input_work"), (pull or 0) * (draw or 0))
    audit.same("efficiency", result.get("efficiency"),
               100 * useful / (useful + carrier + loss) if useful + carrier + loss > 0 else None)
    return audit.result()


@register("solvePlaneMirror")
def audit_plane_mirror(request, result):
    audit = Audit("solvePlaneMirror")
    distance = request.get("object_distance", 0)
    audit.same("image_distance", result.get("image_distance"), distance)
    audit.same("image_x_is_behind", result.get("image_x"), -(result.get("image_distance") or 0))
    audit.same("magnification", result.get("magnification"), 1)
    observer, observer_height = request.get("observer_distance", 0), request.get("observer_height", 0)
    height = request.get("object_height", 0)
    separation = observer + distance
    if separation:
        audit.same("base_hit_y", result.get("base_hit_y"), distance * observer_height / separation)
        audit.same("tip_hit_y", result.get("tip_hit_y"),
                   (observer * height + distance * observer_height) / separation)
    audit.one_of("visibility", result.get("visibility"), {"不可见", "整段可见", "部分可见"})
    half = request.get("mirror_half_height", 0)
    for index, ray in enumerate(result.get("visible_rays") or []):
        audit.need("ray_%d_length" % index, isinstance(ray, list) and len(ray) == 2)
        if isinstance(ray, list) and len(ray) == 2:
            audit.need("ray_%d_source" % index, -1e-9 <= ray[0] <= height + 1e-9, repr(ray[0]))
            audit.need("ray_%d_hit" % index, -half - 1e-9 <= ray[1] <= half + 1e-9, repr(ray[1]))
    return audit.result()


@register("solveWavePropagation")
def audit_wave_propagation(request, result):
    audit = Audit("solveWavePropagation")
    frequency = request.get("frequency", 0)
    detector, travel = request.get("detector_distance", 0), request.get("travel_time", 0)
    audit.same("period", result.get("period"), 1 / frequency)
    audit.same("speed", result.get("speed"), detector / travel)
    audit.same("wavelength", result.get("wavelength"), (result.get("speed") or 0) * (result.get("period") or 0))
    audit.same("next_crest_arrival", result.get("next_crest_arrival"), travel + (result.get("period") or 0))
    observation = request.get("observation_time", 0)
    expected_state = ("刚到达" if abs(observation / travel - 1) <= 1e-12
                      else "尚未到达" if observation < travel else "已到达")
    audit.one_of("arrival_state", result.get("arrival_state"), {expected_state})
    crests = result.get("crest_positions") or []
    if crests:
        audit.same("front_distance", result.get("front_distance"), crests[0])
        audit.same("front_distance_from_speed", result.get("front_distance"),
                   (result.get("speed") or 0) * observation)
    return audit.result()
