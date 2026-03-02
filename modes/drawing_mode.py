"""
Drawing Mode — generates geometric shapes as vector paths → SVG → G-code.

Supported shapes: circle, square, rectangle, triangle, polygon, star.
"""

import math
from core.svg_engine import paths_to_svg
from core.gcode_generator import paths_to_gcode, gcode_to_string
from core.gcode_optimizer import optimize_paths, optimize_gcode
from core.safety import SafetyValidator
from config.machine_config import MachineConfig


def generate_shape(shape_type, params=None):
    """
    Generate a geometric shape as SVG + G-code.

    Args:
        shape_type: One of "circle", "square", "rectangle", "triangle",
                    "polygon", "star".
        params: dict of shape parameters:
            Common: "cx", "cy" (centre), "size" (general dimension)
            circle:    "radius"
            square:    "side"
            rectangle: "width", "height"
            triangle:  "side"
            polygon:   "radius", "sides"
            star:      "outer_radius", "inner_radius", "points"

    Returns:
        dict with "svg", "gcode", "gcode_lines", "paths", "warnings"
    """
    params = params or {}
    cfg = MachineConfig

    cx = float(params.get("cx", cfg.X_MAX / 2))
    cy = float(params.get("cy", cfg.Y_MAX / 2))
    size = float(params.get("size", 50.0))

    shape_type = shape_type.lower().strip()

    generators = {
        "circle": _gen_circle,
        "square": _gen_square,
        "rectangle": _gen_rectangle,
        "triangle": _gen_triangle,
        "polygon": _gen_polygon,
        "star": _gen_star,
    }

    if shape_type not in generators:
        return {
            "svg": "",
            "gcode": "",
            "gcode_lines": [],
            "paths": [],
            "warnings": [f"Unsupported shape: {shape_type}. "
                         f"Supported: {', '.join(generators.keys())}"],
        }

    paths = generators[shape_type](cx, cy, size, params)

    # Validate
    validator = SafetyValidator()
    path_result = validator.validate_paths(paths)
    paths = path_result["paths"]
    warnings = list(path_result["warnings"])

    paths = optimize_paths(paths)

    svg = paths_to_svg(paths, width=cfg.X_MAX, height=cfg.Y_MAX)
    gcode_lines = paths_to_gcode(paths)
    gcode_lines = optimize_gcode(gcode_lines)

    safety_result = validator.validate(gcode_lines)
    gcode_lines = safety_result["gcode"]
    warnings.extend(safety_result["warnings"])

    return {
        "svg": svg,
        "gcode": gcode_to_string(gcode_lines),
        "gcode_lines": gcode_lines,
        "paths": paths,
        "warnings": warnings,
    }


# ---------------------------------------------------------------------------
# Shape Generators
# ---------------------------------------------------------------------------

def _gen_circle(cx, cy, size, params):
    """Generate a circle as a polygon with many segments."""
    radius = float(params.get("radius", size / 2))
    segments = max(36, int(radius * 4))  # more segments for larger circles
    points = []
    for i in range(segments + 1):
        angle = 2 * math.pi * i / segments
        x = cx + radius * math.cos(angle)
        y = cy + radius * math.sin(angle)
        points.append((round(x, 3), round(y, 3)))
    return [points]


def _gen_square(cx, cy, size, params):
    """Generate a square centred at (cx, cy)."""
    side = float(params.get("side", size))
    half = side / 2
    points = [
        (round(cx - half, 3), round(cy - half, 3)),
        (round(cx + half, 3), round(cy - half, 3)),
        (round(cx + half, 3), round(cy + half, 3)),
        (round(cx - half, 3), round(cy + half, 3)),
        (round(cx - half, 3), round(cy - half, 3)),  # close
    ]
    return [points]


def _gen_rectangle(cx, cy, size, params):
    """Generate a rectangle centred at (cx, cy)."""
    w = float(params.get("width", size))
    h = float(params.get("height", size * 0.6))
    hw, hh = w / 2, h / 2
    points = [
        (round(cx - hw, 3), round(cy - hh, 3)),
        (round(cx + hw, 3), round(cy - hh, 3)),
        (round(cx + hw, 3), round(cy + hh, 3)),
        (round(cx - hw, 3), round(cy + hh, 3)),
        (round(cx - hw, 3), round(cy - hh, 3)),  # close
    ]
    return [points]


def _gen_triangle(cx, cy, size, params):
    """Generate an equilateral triangle centred at (cx, cy)."""
    side = float(params.get("side", size))
    # Circumradius of equilateral triangle with given side
    r = side / math.sqrt(3)
    points = []
    for i in range(4):
        angle = math.pi / 2 + 2 * math.pi * i / 3
        x = cx + r * math.cos(angle)
        y = cy + r * math.sin(angle)
        points.append((round(x, 3), round(y, 3)))
    return [points]


def _gen_polygon(cx, cy, size, params):
    """Generate a regular polygon with n sides."""
    sides = int(params.get("sides", 6))
    sides = max(3, min(sides, 100))
    radius = float(params.get("radius", size / 2))
    points = []
    for i in range(sides + 1):
        angle = math.pi / 2 + 2 * math.pi * i / sides
        x = cx + radius * math.cos(angle)
        y = cy + radius * math.sin(angle)
        points.append((round(x, 3), round(y, 3)))
    return [points]


def _gen_star(cx, cy, size, params):
    """Generate a star shape with n points."""
    num_points = int(params.get("points", 5))
    num_points = max(3, min(num_points, 50))
    outer_r = float(params.get("outer_radius", size / 2))
    inner_r = float(params.get("inner_radius", outer_r * 0.4))

    points = []
    total_verts = num_points * 2
    for i in range(total_verts + 1):
        idx = i % total_verts
        angle = math.pi / 2 + 2 * math.pi * idx / total_verts
        r = outer_r if idx % 2 == 0 else inner_r
        x = cx + r * math.cos(angle)
        y = cy + r * math.sin(angle)
        points.append((round(x, 3), round(y, 3)))
    return [points]


def list_shapes():
    """Return list of supported shape types and their parameters."""
    return {
        "circle": {"params": ["cx", "cy", "radius"]},
        "square": {"params": ["cx", "cy", "side"]},
        "rectangle": {"params": ["cx", "cy", "width", "height"]},
        "triangle": {"params": ["cx", "cy", "side"]},
        "polygon": {"params": ["cx", "cy", "radius", "sides"]},
        "star": {"params": ["cx", "cy", "outer_radius", "inner_radius",
                            "points"]},
    }
