"""
G-code Optimizer — path ordering, arc fitting, redundancy removal.
"""

import math
from config.machine_config import MachineConfig


def optimize_paths(paths):
    """
    Optimize path ordering using nearest-neighbour heuristic
    to minimise total rapid travel distance.

    Args:
        paths: List of polylines.

    Returns:
        Reordered list of polylines.
    """
    if len(paths) <= 1:
        return paths

    remaining = list(range(len(paths)))
    ordered = []
    current_pos = (0.0, 0.0)

    while remaining:
        best_idx = None
        best_dist = float('inf')
        for idx in remaining:
            start = paths[idx][0]
            d = _dist(current_pos, start)
            if d < best_dist:
                best_dist = d
                best_idx = idx
        remaining.remove(best_idx)
        ordered.append(paths[best_idx])
        current_pos = paths[best_idx][-1]

    return ordered


def remove_redundant_moves(gcode_lines):
    """
    Remove redundant G-code lines:
    - Consecutive pen up/down without movement
    - Zero-length moves
    - Duplicate consecutive lines
    """
    cfg = MachineConfig
    cleaned = []
    prev_line = None
    prev_x, prev_y = None, None

    for line in gcode_lines:
        stripped = line.strip()

        # Skip empty lines at start
        if not stripped and not cleaned:
            continue

        # Skip exact duplicates
        if stripped == prev_line:
            continue

        # Check for zero-length moves
        if stripped.startswith("G1 ") or stripped.startswith("G0 "):
            x, y = _extract_xy(stripped)
            if x is not None and y is not None:
                if x == prev_x and y == prev_y:
                    continue
                prev_x, prev_y = x, y

        cleaned.append(line)
        prev_line = stripped

    return cleaned


def fit_arcs(paths, tolerance=None):
    """
    Attempt to fit circular arcs (G2/G3) to sequential line segments.

    For each polyline, checks if consecutive points lie on an arc
    within the given tolerance. If so, replaces them with G2/G3 commands.

    Args:
        paths: List of polylines.
        tolerance: Maximum deviation in mm.

    Returns:
        List of "enhanced" path segments, each being either:
          {"type": "line", "points": [(x,y), ...]}
          {"type": "arc", "start": (x,y), "end": (x,y),
           "center": (x,y), "clockwise": bool}
    """
    cfg = MachineConfig
    tol = tolerance or cfg.ARC_TOLERANCE
    result = []

    for path in paths:
        segments = _segment_arcs(path, tol)
        result.append(segments)

    return result


def enhanced_paths_to_gcode(enhanced_paths, feed_rate=None, plunge_rate=None):
    """
    Convert enhanced path segments (lines + arcs) to G-code.

    Args:
        enhanced_paths: Output from fit_arcs().
        feed_rate: Drawing feed rate.
        plunge_rate: Plunge feed rate.

    Returns:
        List of G-code lines.
    """
    cfg = MachineConfig
    feed = feed_rate or cfg.FEED_RATE_DRAW
    plunge = plunge_rate or cfg.FEED_RATE_PLUNGE

    gcode = []
    gcode.append("; CNC Operating System — Optimized G-code")
    gcode.append(f"{cfg.UNIT_MODE}  ; millimetres")
    gcode.append(f"{cfg.POSITIONING}  ; absolute positioning")
    gcode.append(f"{cfg.PEN_UP_CMD}  ; pen up")
    gcode.append(f"G0 Z{cfg.SAFE_Z:.2f}  ; safe height")
    gcode.append("")

    pen_is_down = False

    for path_idx, segments in enumerate(enhanced_paths):
        if not segments:
            continue

        # Get first point of first segment
        first_seg = segments[0]
        if first_seg["type"] == "line":
            start = first_seg["points"][0]
        else:
            start = first_seg["start"]

        # Pen up + rapid move
        if pen_is_down:
            gcode.append(f"{cfg.PEN_UP_CMD}")
            gcode.append(f"G0 Z{cfg.SAFE_Z:.2f}")
            pen_is_down = False

        gcode.append(f"G0 X{start[0]:.3f} Y{start[1]:.3f}")
        gcode.append(f"G1 Z{cfg.PEN_DOWN_Z:.2f} F{plunge:.0f}")
        gcode.append(f"{cfg.PEN_DOWN_CMD}")
        pen_is_down = True

        for seg in segments:
            if seg["type"] == "line":
                for pt in seg["points"][1:]:
                    gcode.append(f"G1 X{pt[0]:.3f} Y{pt[1]:.3f} F{feed:.0f}")
            elif seg["type"] == "arc":
                cmd = "G2" if seg["clockwise"] else "G3"
                ex, ey = seg["end"]
                cx, cy = seg["center"]
                sx, sy = seg["start"]
                i_off = cx - sx
                j_off = cy - sy
                gcode.append(
                    f"{cmd} X{ex:.3f} Y{ey:.3f} "
                    f"I{i_off:.3f} J{j_off:.3f} F{feed:.0f}"
                )

    if pen_is_down:
        gcode.append(f"{cfg.PEN_UP_CMD}")
        gcode.append(f"G0 Z{cfg.SAFE_Z:.2f}")

    gcode.append("")
    gcode.append("G0 X0.000 Y0.000  ; return to origin")
    gcode.append("M2  ; program end")

    return gcode


def optimize_gcode(gcode_lines):
    """
    Full optimization pipeline on raw G-code lines:
    1. Remove redundant moves
    2. Remove empty consecutive blank lines
    """
    lines = remove_redundant_moves(gcode_lines)
    # Collapse multiple blank lines
    cleaned = []
    prev_blank = False
    for line in lines:
        if not line.strip():
            if prev_blank:
                continue
            prev_blank = True
        else:
            prev_blank = False
        cleaned.append(line)
    return cleaned


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _dist(a, b):
    """Euclidean distance between two points."""
    return math.sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2)


def _extract_xy(line):
    """Extract X and Y values from a G-code line."""
    x, y = None, None
    parts = line.split()
    for part in parts:
        if part.startswith('X'):
            try:
                x = float(part[1:])
            except ValueError:
                pass
        elif part.startswith('Y'):
            try:
                y = float(part[1:])
            except ValueError:
                pass
    return x, y


def _find_circle(p1, p2, p3):
    """
    Find the circle passing through three points.

    Returns:
        (cx, cy, radius) or None if points are collinear.
    """
    ax, ay = p1
    bx, by = p2
    cx, cy = p3

    d = 2 * (ax * (by - cy) + bx * (cy - ay) + cx * (ay - by))
    if abs(d) < 1e-10:
        return None  # collinear

    ux = ((ax ** 2 + ay ** 2) * (by - cy) +
          (bx ** 2 + by ** 2) * (cy - ay) +
          (cx ** 2 + cy ** 2) * (ay - by)) / d
    uy = ((ax ** 2 + ay ** 2) * (cx - bx) +
          (bx ** 2 + by ** 2) * (ax - cx) +
          (cx ** 2 + cy ** 2) * (bx - ax)) / d
    r = math.sqrt((ax - ux) ** 2 + (ay - uy) ** 2)

    return (ux, uy, r)


def _is_clockwise(p1, p2, p3):
    """Determine if three points are in clockwise order."""
    return ((p2[0] - p1[0]) * (p3[1] - p1[1]) -
            (p2[1] - p1[1]) * (p3[0] - p1[0])) < 0


def _segment_arcs(path, tolerance):
    """
    Segment a polyline into line and arc segments.
    """
    cfg = MachineConfig
    if len(path) < cfg.MIN_ARC_POINTS:
        return [{"type": "line", "points": list(path)}]

    segments = []
    i = 0

    while i < len(path):
        # Try to find an arc starting at i
        best_arc_end = -1
        best_center = None
        best_cw = False

        if i + 2 < len(path):
            circle = _find_circle(path[i], path[i + 1], path[i + 2])
            if circle:
                cx, cy, r = circle
                cw = _is_clockwise(path[i], path[i + 1], path[i + 2])

                # Extend arc as far as possible
                j = i + 2
                while j < len(path):
                    pt = path[j]
                    dist_from_center = math.sqrt(
                        (pt[0] - cx) ** 2 + (pt[1] - cy) ** 2
                    )
                    if abs(dist_from_center - r) > tolerance:
                        break
                    j += 1

                arc_len = j - i
                if arc_len >= cfg.MIN_ARC_POINTS:
                    best_arc_end = j - 1
                    best_center = (cx, cy)
                    best_cw = cw

        if best_arc_end > 0:
            segments.append({
                "type": "arc",
                "start": path[i],
                "end": path[best_arc_end],
                "center": best_center,
                "clockwise": best_cw,
            })
            i = best_arc_end + 1
        else:
            # Single line segment
            end = min(i + 1, len(path) - 1)
            if i == end:
                break
            # Collect consecutive line points
            line_pts = [path[i]]
            while end < len(path):
                line_pts.append(path[end])
                # Check if next 3 points form an arc
                if end + 2 < len(path):
                    circle = _find_circle(
                        path[end], path[end + 1], path[end + 2]
                    )
                    if circle:
                        cx, cy, r = circle
                        # Check if enough points on this arc
                        k = end + 2
                        while k < len(path):
                            pt = path[k]
                            d = math.sqrt(
                                (pt[0] - cx) ** 2 + (pt[1] - cy) ** 2
                            )
                            if abs(d - r) > tolerance:
                                break
                            k += 1
                        if k - end >= cfg.MIN_ARC_POINTS:
                            break
                end += 1

            if len(line_pts) >= 2:
                segments.append({"type": "line", "points": line_pts})
            i = end

    return segments
