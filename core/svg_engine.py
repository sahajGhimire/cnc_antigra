"""
SVG Engine — builds SVG documents from stroke paths and parses SVG path data.
"""

import re
import math


def paths_to_svg(paths, width=300.0, height=400.0, stroke_width=0.5,
                 stroke_color="#000000", margin=5.0):
    """
    Convert a list of polyline paths into an SVG document string.

    Args:
        paths: List of polylines. Each polyline is [(x, y), (x, y), ...].
        width: SVG canvas width in mm.
        height: SVG canvas height in mm.
        stroke_width: Line width.
        stroke_color: Stroke colour.
        margin: Margin added around bounding box.

    Returns:
        SVG document as a string.
    """
    if not paths:
        return _empty_svg(width, height)

    # Calculate bounding box
    all_x = [p[0] for path in paths for p in path]
    all_y = [p[1] for path in paths for p in path]
    min_x, max_x = min(all_x), max(all_x)
    min_y, max_y = min(all_y), max(all_y)

    # For SVG we need Y‑down coordinates. Compute an offset that flips Y around the vertical centre.
    y_offset = max_y + min_y  # sum of extremes; y_svg = y_offset - y_original

    vb_x = min_x - margin
    vb_y = min_y - margin
    vb_w = (max_x - min_x) + 2 * margin
    vb_h = (max_y - min_y) + 2 * margin

    svg_lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{width}mm" height="{height}mm" '
        f'viewBox="{vb_x:.2f} {vb_y:.2f} {vb_w:.2f} {vb_h:.2f}">',
        f'  <g fill="none" stroke="{stroke_color}" '
        f'stroke-width="{stroke_width}" stroke-linecap="round" '
        f'stroke-linejoin="round">',
    ]

    for path in paths:
        if len(path) < 2:
            continue
        # Flip Y for SVG (Y‑down) using the pre‑computed offset
        d = f"M {path[0][0]:.3f},{(y_offset - path[0][1]):.3f}"
        for pt in path[1:]:
            d += f" L {pt[0]:.3f},{(y_offset - pt[1]):.3f}"
        svg_lines.append(f'    <path d="{d}"/>')

    svg_lines.append('  </g>')
    svg_lines.append('</svg>')
    return '\n'.join(svg_lines)


def _empty_svg(width, height):
    """Return an empty SVG document."""
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{width}mm" height="{height}mm" '
        f'viewBox="0 0 {width} {height}"></svg>'
    )


def parse_svg_paths(svg_string):
    """
    Extract polyline path data from an SVG string.

    Supports M (moveto) and L (lineto) commands.

    Args:
        svg_string: SVG document string.

    Returns:
        List of polylines, each is [(x, y), ...].
    """
    paths = []
    # Find all path d attributes
    d_attrs = re.findall(r'<path[^>]*\sd="([^"]+)"', svg_string)
    for d in d_attrs:
        polylines = _parse_d_attribute(d)
        paths.extend(polylines)
    return paths


def _parse_d_attribute(d):
    """Parse an SVG path d attribute into polylines."""
    polylines = []
    current = []
    # Tokenize: split on commands and extract numbers
    tokens = re.findall(r'[MLCZQHVAmlczqhva]|[-+]?\d*\.?\d+', d)

    i = 0
    cmd = 'M'
    cx, cy = 0.0, 0.0

    while i < len(tokens):
        token = tokens[i]
        if token.isalpha():
            cmd = token
            i += 1
            continue

        if cmd in ('M', 'm'):
            if current and len(current) >= 2:
                polylines.append(current)
            x, y = float(tokens[i]), float(tokens[i + 1])
            if cmd == 'm':
                x += cx
                y += cy
            cx, cy = x, y
            current = [(cx, cy)]
            i += 2
            cmd = 'L' if cmd == 'M' else 'l'

        elif cmd in ('L', 'l'):
            x, y = float(tokens[i]), float(tokens[i + 1])
            if cmd == 'l':
                x += cx
                y += cy
            cx, cy = x, y
            current.append((cx, cy))
            i += 2

        elif cmd in ('H', 'h'):
            x = float(tokens[i])
            if cmd == 'h':
                x += cx
            cx = x
            current.append((cx, cy))
            i += 1

        elif cmd in ('V', 'v'):
            y = float(tokens[i])
            if cmd == 'v':
                y += cy
            cy = y
            current.append((cx, cy))
            i += 1

        elif cmd in ('Z', 'z'):
            if current and len(current) >= 2:
                current.append(current[0])
                polylines.append(current)
            current = []
            i += 1

        else:
            # Skip unsupported commands
            i += 1

    if current and len(current) >= 2:
        polylines.append(current)

    return polylines


def shapes_to_svg(shapes_paths, width=300.0, height=400.0):
    """
    Convenience: render multiple shapes given as path lists to a single SVG.
    """
    return paths_to_svg(shapes_paths, width, height, stroke_width=0.5)
