"""
Writing Mode — converts text input into stroke-based SVG and optimized G-code.
"""

from core.fonts.stroke_font import get_text_paths
from core.svg_engine import paths_to_svg
from core.gcode_generator import paths_to_gcode, gcode_to_string
from core.gcode_optimizer import optimize_paths, optimize_gcode
from core.safety import SafetyValidator
from config.machine_config import MachineConfig


def generate(text, x=None, y=None, font_size=None, line_spacing=None,
             feed_rate=None):
    """
    Full writing pipeline: text → stroke paths → SVG → G-code.

    Args:
        text: Input text string (supports multi-line).
        x: Starting X position (mm).
        y: Starting Y position (mm).
        font_size: Font height in mm.
        line_spacing: Line spacing multiplier.
        feed_rate: Drawing feed rate (mm/min).

    Returns:
        dict with:
            "svg": SVG document string
            "gcode": G-code string
            "gcode_lines": list of G-code lines
            "paths": raw polyline paths
            "warnings": safety warnings
            "char_count": number of characters
            "line_count": number of lines
    """
    cfg = MachineConfig
    x = x if x is not None else cfg.DEFAULT_ORIGIN_X
    y = y if y is not None else cfg.DEFAULT_ORIGIN_Y
    font_size = font_size or cfg.DEFAULT_FONT_SIZE
    line_spacing = line_spacing or cfg.DEFAULT_LINE_SPACING

    if not text or not text.strip():
        return {
            "svg": "",
            "gcode": "",
            "gcode_lines": [],
            "paths": [],
            "warnings": ["Empty text input"],
            "char_count": 0,
            "line_count": 0,
        }

    # 1. Convert text to stroke paths
    paths = get_text_paths(text, x=x, y=y, size=font_size,
                           line_spacing=line_spacing)

    if not paths:
        return {
            "svg": "",
            "gcode": "",
            "gcode_lines": [],
            "paths": [],
            "warnings": ["No renderable characters found"],
            "char_count": len(text),
            "line_count": text.count('\n') + 1,
        }

    # 2. Validate paths against machine boundaries
    validator = SafetyValidator()
    path_result = validator.validate_paths(paths)
    paths = path_result["paths"]
    warnings = list(path_result["warnings"])

    # 3. Optimize path ordering
    paths = optimize_paths(paths)

    # 4. Generate SVG
    svg = paths_to_svg(paths, width=cfg.X_MAX, height=cfg.Y_MAX)

    # 5. Generate G-code
    gcode_lines = paths_to_gcode(paths, feed_rate=feed_rate)

    # 6. Optimize G-code
    gcode_lines = optimize_gcode(gcode_lines)

    # 7. Safety validate G-code
    safety_result = validator.validate(gcode_lines)
    gcode_lines = safety_result["gcode"]
    warnings.extend(safety_result["warnings"])

    return {
        "svg": svg,
        "gcode": gcode_to_string(gcode_lines),
        "gcode_lines": gcode_lines,
        "paths": paths,
        "warnings": warnings,
        "char_count": len(text),
        "line_count": text.count('\n') + 1,
    }
