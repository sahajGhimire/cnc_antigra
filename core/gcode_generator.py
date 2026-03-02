"""
G-code Generator — converts polyline paths to GRBL-compatible G-code.
"""

from config.machine_config import MachineConfig


def paths_to_gcode(paths, feed_rate=None, plunge_rate=None):
    """
    Convert a list of polyline paths into GRBL G-code.

    Each polyline is drawn with pen-down; pen lifts occur between polylines.

    Args:
        paths: List of polylines, each is [(x, y), ...].
        feed_rate: Drawing feed rate (mm/min). Defaults to config.
        plunge_rate: Plunge feed rate (mm/min). Defaults to config.

    Returns:
        List of G-code lines (strings).
    """
    cfg = MachineConfig
    feed = feed_rate or cfg.FEED_RATE_DRAW
    plunge = plunge_rate or cfg.FEED_RATE_PLUNGE

    gcode = []
    gcode.append("; CNC Operating System — Generated G-code")
    gcode.append(f"{cfg.UNIT_MODE}  ; millimetres")
    gcode.append(f"{cfg.POSITIONING}  ; absolute positioning")
    gcode.append(f"{cfg.PEN_UP_CMD}  ; pen up")
    gcode.append(f"G0 Z{cfg.SAFE_Z:.2f}  ; safe height")
    gcode.append("")

    pen_is_down = False

    for path_idx, path in enumerate(paths):
        if len(path) < 2:
            continue

        # --- Pen up + rapid move to start of path ---
        if pen_is_down:
            gcode.append(f"{cfg.PEN_UP_CMD}  ; pen up")
            gcode.append(f"G0 Z{cfg.SAFE_Z:.2f}")
            pen_is_down = False

        start = path[0]
        gcode.append(f"G0 X{start[0]:.3f} Y{start[1]:.3f}  ; rapid to path {path_idx}")

        # --- Pen down ---
        gcode.append(f"G1 Z{cfg.PEN_DOWN_Z:.2f} F{plunge:.0f}  ; plunge")
        gcode.append(f"{cfg.PEN_DOWN_CMD}  ; pen down")
        pen_is_down = True

        # --- Draw path ---
        for pt in path[1:]:
            gcode.append(f"G1 X{pt[0]:.3f} Y{pt[1]:.3f} F{feed:.0f}")

    # --- Final pen up ---
    if pen_is_down:
        gcode.append(f"{cfg.PEN_UP_CMD}  ; pen up")
        gcode.append(f"G0 Z{cfg.SAFE_Z:.2f}")

    gcode.append("")
    gcode.append("G0 X0.000 Y0.000  ; return to origin")
    gcode.append("M2  ; program end")

    return gcode


def gcode_to_string(gcode_lines):
    """Join G-code lines into a single string."""
    return '\n'.join(gcode_lines)
