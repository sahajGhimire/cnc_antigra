"""
Image Vectorizer — converts raster images to stroke-based SVG + G-code.

Pipeline: load → grayscale → threshold → contours → simplify → SVG → G-code
"""

import math
import numpy as np

try:
    import cv2
    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False

from config.machine_config import MachineConfig
from core.svg_engine import paths_to_svg
from core.gcode_generator import paths_to_gcode, gcode_to_string
from core.gcode_optimizer import optimize_paths, optimize_gcode
from core.safety import SafetyValidator


def vectorize_image(image_path=None, image_bytes=None,
                    threshold=None, epsilon=None,
                    max_width=None, max_height=None,
                    offset_x=None, offset_y=None,
                    invert=False):
    """
    Convert a raster image to stroke-based SVG paths and G-code.

    Args:
        image_path: Path to image file.
        image_bytes: Raw image bytes (alternative to path).
        threshold: B/W threshold (0–255).
        epsilon: Douglas-Peucker simplification tolerance.
        max_width: Maximum output width in mm.
        max_height: Maximum output height in mm.
        offset_x: X offset in mm.
        offset_y: Y offset in mm.
        invert: If True, invert B/W (draw white areas).

    Returns:
        dict with "svg", "gcode", "gcode_lines", "paths", "warnings",
                  "contour_count", "point_count"
    """
    if not HAS_CV2:
        return {
            "svg": "",
            "gcode": "",
            "gcode_lines": [],
            "paths": [],
            "warnings": ["OpenCV (cv2) is not installed. "
                         "Install with: pip install opencv-python"],
            "contour_count": 0,
            "point_count": 0,
        }

    cfg = MachineConfig
    threshold = threshold if threshold is not None else cfg.IMAGE_THRESHOLD
    epsilon = epsilon if epsilon is not None else cfg.CONTOUR_SIMPLIFY_EPSILON
    max_width = max_width or cfg.IMAGE_MAX_WIDTH
    max_height = max_height or cfg.IMAGE_MAX_HEIGHT
    offset_x = offset_x if offset_x is not None else cfg.DEFAULT_ORIGIN_X
    offset_y = offset_y if offset_y is not None else cfg.DEFAULT_ORIGIN_Y

    # 1. Load image
    try:
        if image_path:
            img = cv2.imread(image_path)
        elif image_bytes:
            nparr = np.frombuffer(image_bytes, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        else:
            return _error_result("No image provided")

        if img is None:
            return _error_result("Failed to load image")

    except Exception as e:
        return _error_result(f"Image loading error: {str(e)}")

    # 2. Convert to grayscale
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # 3. Apply Gaussian blur to reduce noise
    gray = cv2.GaussianBlur(gray, (5, 5), 0)

    # 4. Threshold to binary B/W
    thresh_type = cv2.THRESH_BINARY_INV if not invert else cv2.THRESH_BINARY
    _, binary = cv2.threshold(gray, threshold, 255, thresh_type)

    # 5. Find contours
    contours, _ = cv2.findContours(
        binary, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE
    )

    if not contours:
        return {
            "svg": "",
            "gcode": "",
            "gcode_lines": [],
            "paths": [],
            "warnings": ["No contours found in image"],
            "contour_count": 0,
            "point_count": 0,
        }

    # 6. Calculate scaling to fit within max dimensions
    img_h, img_w = img.shape[:2]
    scale_x = max_width / img_w
    scale_y = max_height / img_h
    scale = min(scale_x, scale_y)

    # 7. Simplify and convert contours to paths
    paths = []
    total_points = 0
    for contour in contours:
        # Douglas-Peucker simplification
        simplified = cv2.approxPolyDP(contour, epsilon, closed=True)

        if len(simplified) < 3:
            continue

        polyline = []
        for point in simplified:
            px = point[0][0] * scale + offset_x
            # Flip Y axis (image Y is top-down, CNC Y is bottom-up)
            py = (img_h - point[0][1]) * scale + offset_y
            polyline.append((round(px, 3), round(py, 3)))

        # Close the contour
        if polyline and polyline[0] != polyline[-1]:
            polyline.append(polyline[0])

        if len(polyline) >= 3:
            paths.append(polyline)
            total_points += len(polyline)

    if not paths:
        return {
            "svg": "",
            "gcode": "",
            "gcode_lines": [],
            "paths": [],
            "warnings": ["Contours too simple after simplification"],
            "contour_count": len(contours),
            "point_count": 0,
        }

    # 8. Validate + optimize + generate
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
        "contour_count": len(paths),
        "point_count": total_points,
    }


def _error_result(message):
    """Return an error result dict."""
    return {
        "svg": "",
        "gcode": "",
        "gcode_lines": [],
        "paths": [],
        "warnings": [message],
        "contour_count": 0,
        "point_count": 0,
    }
