"""Independent reference for a converging thin lens in the paraxial model."""


def solve_thin_lens(request):
    if not isinstance(request, dict):
        raise ValueError("需要凸透镜参数对象")
    u, f = (request.get(key) for key in ("u", "f"))
    if any(type(value) not in (int, float) or not 1e-6 <= value <= 1e6 for value in (u, f)):
        raise ValueError("物距和焦距必须在 0.000001 至 1000000 cm 之间")

    if u == f:
        return {"version": 1, "u": u, "f": f, "image_distance_cm": None,
                "magnification": None, "state": "无有限像"}

    distance = u * f / (u - f)
    if u < f:
        state = "正立放大的虚像"
    elif u < 2 * f:
        state = "倒立放大的实像"
    elif u == 2 * f:
        state = "倒立等大的实像"
    else:
        state = "倒立缩小的实像"
    return {"version": 1, "u": u, "f": f, "image_distance_cm": distance,
            "magnification": -f / (u - f), "state": state}
