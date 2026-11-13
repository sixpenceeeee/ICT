"""Independent reference calculations for the physics teaching pages."""

import math

try:  # 包内导入（scene_registry / reviewer）
    from .thin_lens_solver import solve_thin_lens
except ImportError:  # 直接以模块方式导入（单测）
    from thin_lens_solver import solve_thin_lens


G = 9.8


def quantities(request, *names, positive=(), nonnegative=()):
    if not isinstance(request, dict):
        raise ValueError("需要物理参数对象")
    values = []
    for name in (*names, *positive, *nonnegative):
        value = request.get(name)
        if (type(value) not in (float, int) or not abs(value) <= 1e9
                or (name in positive and value < 1e-9)
                or (name in nonnegative and value < 0)):
            raise ValueError(f"参数超出模型范围：{name}")
        values.append(float(value))
    return values


def solve_buoyancy(request):
    fraction, obj, liquid, volume = quantities(
        request, "fraction", positive=("object_density", "liquid_density", "volume"))
    mode = request.get("mode")
    if mode not in ("hang", "free") or not 0 <= fraction <= 1:
        raise ValueError("浸没比须在 0 至 1 之间，模式须为 hang 或 free")
    weight = obj * volume * G
    if mode == "free":
        fraction = min(obj / liquid, 1)
        state = "上浮后漂浮" if obj < liquid else "下沉" if obj > liquid else "悬浮"
    displaced = volume * fraction
    buoyancy = liquid * G * displaced
    tension = None
    if mode == "hang":
        tension = max(0, weight - buoyancy)
        state = "绳松弛" if fraction > obj / liquid else "悬挂"
    return {"version": 1, "fraction": fraction, "displaced_volume": displaced,
            "weight": weight, "buoyancy": buoyancy, "tension": tension, "state": state}


def solve_lever(request):
    lf, la, rf, ra = quantities(
        request, nonnegative=("left_force", "left_arm", "right_force", "right_arm"))
    left, right = lf * la, rf * ra
    net = math.fsum((left, -right))
    if math.isclose(left, right, rel_tol=1e-12):
        net = 0.0
    state = "左侧下沉" if net > 0 else "右侧下沉" if net < 0 else "平衡"
    return {"version": 1, "left_torque": left, "right_torque": right, "net_torque": net, "state": state}


def solve_liquid_pressure(request):
    density, depth = quantities(request, positive=("density",), nonnegative=("depth",))
    return {"version": 1, "pressure": G * (density * depth)}


def solve_specific_heat(request):
    heat, initial, mass, specific_heat = quantities(
        request, "heat", "initial_temperature", positive=("mass", "specific_heat"))
    change = heat / (mass * specific_heat)
    final = initial + change
    if min(initial, final) < -273.15:
        raise ValueError("温度不能低于绝对零度")
    return {"version": 1, "temperature_change": change, "final_temperature": final}


def solve_uniform_acceleration(request):
    initial, acceleration, duration = quantities(
        request, "initial_velocity", "acceleration", nonnegative=("time",))

    def sample(time):
        velocity = initial + acceleration * time
        displacement = (initial + velocity) / 2 * time
        return [time, displacement, velocity]

    trajectory = [sample(duration * i / 4) for i in range(5)]
    _, displacement, velocity = trajectory[-1]
    distance = abs(displacement)
    if initial * velocity < 0:
        turn = sample(-initial / acceleration)[1]
        distance = abs(turn) + abs(displacement - turn)
    return {"version": 1, "velocity": velocity, "displacement": displacement,
            "distance": distance, "trajectory": trajectory}


def solve_horizontal_projectile(request):
    speed, height, time = quantities(request, nonnegative=("speed", "height", "time"))
    flight = math.sqrt(2 * height / G)
    elapsed = min(time, flight)

    def sample(t):
        y = max(0, height - G * t ** 2 / 2) if t < flight else 0
        return [t, speed * t, y]

    _, x, y = sample(elapsed)
    return {"version": 1, "x": x, "y": y, "vx": speed, "vy": -G * elapsed,
            "flight_time": flight, "range": speed * flight,
            "state": "已到落点" if time >= flight else "飞行中",
            "trajectory": [sample(flight * i / 4) for i in range(5)]}


def solve_refraction(request):
    n1, n2, incident = quantities(request, nonnegative=("n1", "n2", "incident_angle"))
    if min(n1, n2) < 1 or incident > 90:
        raise ValueError("折射率至少为 1，入射角须在 0 至 90 度之间")
    critical = math.degrees(math.asin(n2 / n1)) if n1 > n2 else None
    if critical is not None and abs(incident - critical) <= 1e-10:
        state, refracted = "临界折射", 90
    elif critical is not None and incident > critical:
        state, refracted = "全反射", None
    else:
        state = "折射"
        sine = math.sin(math.radians(incident)) * (n1 / n2)
        refracted = incident if n1 == n2 else math.degrees(math.asin(min(1, sine)))
    return {"version": 1, "reflected_angle": incident, "refracted_angle": refracted,
            "critical_angle": critical, "state": state}


def solve_horizontal_force(request):
    """Reconstruct the contact reaction using momentum balance over a unit interval."""
    applied, velocity, mass, static_mu, kinetic_mu = quantities(
        request, "applied_force", "velocity", positive=("mass",),
        nonnegative=("static_coefficient", "kinetic_coefficient"))
    if not kinetic_mu <= static_mu <= 1e3:
        raise ValueError("摩擦系数须满足 0 ≤ 动摩擦系数 ≤ 静摩擦系数 ≤ 1000")

    normal = G * mass
    limit = normal * static_mu
    # A unit interval converts constant forces to impulses without advancing the
    # simulation. The contact impulse required to keep a resting block at rest
    # is the negative of the applied impulse.
    interval = 1.0
    applied_impulse = applied * interval
    required_impulse = -applied_impulse
    static_capacity = limit * interval
    bounded_impulse = min(static_capacity, max(-static_capacity, required_impulse))
    at_limit = static_capacity > 0 and math.isclose(
        abs(required_impulse), static_capacity, rel_tol=1e-12)
    if velocity == 0 and (required_impulse == bounded_impulse or at_limit):
        contact_impulse = required_impulse
        state = "临界静止" if at_limit else "静止"
    else:
        slip = velocity or math.fsum((applied_impulse, bounded_impulse))
        kinetic_impulse = normal * kinetic_mu * interval
        # Of the two kinetic reactions, choose the one opposing slip.
        contact_impulse = -kinetic_impulse if slip > 0 else kinetic_impulse
        state = "开始滑动" if velocity == 0 else "滑动中"
    net_impulse = math.fsum((applied_impulse, contact_impulse))
    return {"version": 1, "weight": normal, "normal_force": normal,
            "static_limit": limit, "friction": contact_impulse / interval,
            "net_force": net_impulse / interval, "acceleration": net_impulse / (mass * interval),
            "state": state}


def solve_work_power(request):
    """Recover signed work from the area under the power–time curve."""
    duration, force, distance, angle = quantities(
        request, positive=("duration",), nonnegative=("force", "distance", "angle"))
    if angle > 180 or 0 < force < 1e-9 or 0 < distance < 1e-9:
        raise ValueError("夹角须在 0 至 180 度之间；非零力和位移至少为 1e-9")

    # Traversing the same straight segment at uniform speed gives the same
    # total work for a constant force. Integrate its signed power over time.
    speed = distance / duration
    parallel_force = force * math.sin(math.radians(90 - angle))
    power = parallel_force * speed
    work = power * duration
    return {"version": 1, "parallel_force": parallel_force, "work": work,
            "average_power": power, "state": "正功" if work > 0 else "负功" if work < 0 else "零功"}


def solve_mechanical_energy(request):
    """Use the work–kinetic energy theorem to reconstruct the final speed."""
    start_height, end_height, work, mass, speed = quantities(
        request, "start_height", "end_height", "nonconservative_work",
        positive=("mass",), nonnegative=("initial_speed",))
    weight = mass * G
    start_kinetic = 0.5 * mass * (speed * speed)
    start_potential = weight * start_height
    gravity_work = weight * (start_height - end_height)
    final_kinetic = math.fsum((start_kinetic, gravity_work, work))
    if abs(final_kinetic) <= 1e-12 * max(start_kinetic, abs(gravity_work), abs(work)):
        final_kinetic = 0.0
    possible = final_kinetic >= 0
    final_potential = weight * end_height if possible else None
    return {
        "version": 1, "initial_kinetic": start_kinetic, "initial_potential": start_potential,
        "initial_energy": start_kinetic + start_potential,
        "final_kinetic": final_kinetic if possible else None, "final_potential": final_potential,
        "final_energy": final_kinetic + final_potential if possible else None,
        "energy_change": work if possible else None,
        "final_speed": math.sqrt(final_kinetic) * math.sqrt(2 / mass) if possible else None,
        "energy_shortfall": max(0.0, -final_kinetic),
        "state": "末速度非零" if final_kinetic > 0 else "末速度为零" if possible else "能量不足",
    }


def solve_inclined_plane(request):
    """Recover the pull from the energy budget for constant-speed ascent."""
    mass, length, height, coefficient = quantities(
        request, positive=("mass", "length"), nonnegative=("height", "friction_coefficient"))
    if height > length or 0 < height < 1e-9 or 0 < coefficient < 1e-9:
        raise ValueError("高度不能超过斜面长度，非零高度和摩擦系数至少为 1e-9")

    run = math.sqrt((length - height) * (length + height))
    weight = mass * G
    useful = weight * height
    # Friction loss is μmg times the horizontal run, since L cos θ = run.
    loss = (coefficient * weight) * run
    total = math.fsum((useful, loss))
    return {
        "version": 1, "horizontal_run": run, "angle_deg": math.degrees(math.atan2(height, run)),
        "normal_force": weight * (run / length), "friction_force": loss / length,
        "pull_force": total / length, "useful_work": useful, "friction_loss": loss,
        "input_work": total, "efficiency": 100 * (useful / total) if total > 0 else None,
    }


PULLEY_ROUTES = {
    "fixed": ("lower_anchor", "fixed_pulley", "free_end"),
    "two_fixed": ("lower_anchor", "fixed_pulley", "fixed_pulley", "free_end"),
    "two_strands": ("upper_anchor", "moving_pulley", "fixed_pulley", "free_end"),
    "three_strands": ("lower_anchor", "fixed_pulley", "moving_pulley", "free_end"),
    "four_strands": ("upper_anchor", "moving_pulley", "fixed_pulley", "moving_pulley",
                     "fixed_pulley", "free_end"),
}


def solve_pulley_system(request):
    """Recover travel by holding the free end and measuring rope shortening."""
    load, moving, height, drag = quantities(
        request, positive=("load_mass",), nonnegative=("moving_mass", "lift_height", "rope_loss_force"))
    layout = request.get("layout")
    if not isinstance(layout, str) or layout not in PULLEY_ROUTES:
        raise ValueError("滑轮组绳路不在支持范围内")
    if any(0 < value < 1e-9 for value in (moving, height, drag)):
        raise ValueError("非零动滑轮组件质量、提升高度和绳端阻力至少为 1e-9")
    route = PULLEY_ROUTES[layout]

    def rope_length(block_height):
        # Segments within a block and wrapped portions keep their lengths.
        heights = [block_height if node in ("lower_anchor", "moving_pulley") else 2 for node in route]
        return sum(abs(end - start) for start, end in zip(heights, heights[1:]))

    strands = rope_length(0) - rope_length(1)
    draw = strands * height
    useful = load * G * height
    carrier_work = moving * G * height
    loss = drag * draw
    work = math.fsum((useful, carrier_work, loss))
    # For one metre of lift, the load, carrier and drag determine the input work.
    pull = math.fsum((load * G, moving * G, drag * strands)) / strands
    return {
        "version": 1, "rope_route": list(route), "supporting_strands": strands,
        "fixed_pulleys": route.count("fixed_pulley"), "moving_pulleys": route.count("moving_pulley"),
        "pull_distance": draw, "pull_force": pull, "useful_work": useful,
        "carrier_work": carrier_work, "friction_loss": loss, "input_work": work,
        "efficiency": 100 * (useful / work) if work > 0 else None,
    }


def solve_plane_mirror(request):
    """Use equal-angle reflection and backward ray intersections."""
    observer_height, distance, observer, half, height = quantities(
        request, "observer_height", positive=("object_distance", "observer_distance", "mirror_half_height"),
        nonnegative=("object_height",))

    # Two probe rays hit at offsets ±distance from each source point's foot
    # on the extended mirror. Their reflected slopes intersect behind it.
    left_hit, right_hit = -distance, distance
    left_slope, right_slope = left_hit / distance, right_hit / distance
    image_x = (left_hit - right_hit) / (right_slope - left_slope)
    separation = observer + distance

    def hit_at(source_y):
        # Equal incident and outgoing slopes relative to the normal:
        # (hit-source_y)/distance = (observer_height-hit)/observer.
        return math.fsum((observer * source_y, distance * observer_height)) / separation

    base_hit, tip_hit = hit_at(0), hit_at(height)
    first_hit, last_hit = max(base_hit, -half), min(tip_hit, half)
    tolerance = 1e-12 * half
    visible_from = visible_to = None
    rays = []
    visibility = "不可见"
    if first_hit <= last_hit + tolerance:
        def source_at(edge):
            return max(0.0, min(height, (edge * separation - distance * observer_height) / observer))

        full = base_hit >= -half - tolerance and tip_hit <= half + tolerance
        visibility = "整段可见" if full else "部分可见"
        visible_from = 0.0 if full else source_at(-half)
        visible_to = height if full else source_at(half)
        for source in dict.fromkeys((visible_from, visible_to)):
            rays.append([source, max(-half, min(half, hit_at(source)))])

    return {
        "version": 1, "object_distance": distance, "image_distance": -image_x,
        "image_x": image_x, "image_height": height, "magnification": 1,
        "image_kind": "正立等大虚像",
        "base_hit_y": base_hit, "tip_hit_y": tip_hit,
        "visibility": visibility, "visible_from": visible_from, "visible_to": visible_to,
        "visible_rays": rays,
    }


def solve_wave_propagation(request):
    """Trace emitted crests through a measured point on their space–time lines."""
    frequency, detector, travel, observation = quantities(
        request, positive=("frequency", "detector_distance", "travel_time"),
        nonnegative=("observation_time",))
    if 0 < observation < 1e-9:
        raise ValueError("非零观察时间至少为 1e-9 秒")

    period = 1 / frequency

    def trace(clock, emission):
        # Similar triangles along a crest's line through its emission point
        # and the detector event, separated by the measured travel time.
        return detector * ((clock - emission) / travel)

    wavelength = trace(period, 0) - trace(period, period)
    crests = [trace(observation, i * period) for i in range(3) if observation >= i * period]
    progress = observation / travel
    state = "刚到达" if abs(progress - 1) <= 1e-12 else "尚未到达" if progress < 1 else "已到达"
    return {
        "version": 1, "frequency": frequency, "speed": trace(1, 0), "period": period,
        "wavelength": wavelength, "arrival_time": travel, "next_crest_arrival": period + travel,
        "front_distance": crests[0], "arrival_state": state, "crest_positions": crests,
    }


SOLVERS = {
    "solveBuoyancy": solve_buoyancy,
    "solveLever": solve_lever,
    "solveLiquidPressure": solve_liquid_pressure,
    "solveSpecificHeat": solve_specific_heat,
    "solveUniformAcceleration": solve_uniform_acceleration,
    "solveHorizontalProjectile": solve_horizontal_projectile,
    "solveRefraction": solve_refraction,
    "solveHorizontalForce": solve_horizontal_force,
    "solveWorkPower": solve_work_power,
    "solveMechanicalEnergy": solve_mechanical_energy,
    "solveInclinedPlane": solve_inclined_plane,
    "solvePulleySystem": solve_pulley_system,
    "solvePlaneMirror": solve_plane_mirror,
    "solveWavePropagation": solve_wave_propagation,
}


def solve_reflection(request):
    """镜面反射：反射角等于入射角，两光线夹角为入射角的两倍。"""
    angle = request.get("incident_angle")
    if type(angle) not in (int, float) or not 0 <= angle <= 89.9:
        raise ValueError("入射角须在 0 至 89.9 度之间")
    return {"version": 1, "incident_angle": angle, "reflected_angle": angle,
            "angle_between": 2 * angle,
            "state": "垂直入射，原路返回" if angle < 0.5 else "反射，反射角等于入射角"}


SOLVERS["solveThinLens"] = solve_thin_lens
SOLVERS["solveReflection"] = solve_reflection
