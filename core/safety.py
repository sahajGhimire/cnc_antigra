"""
Safety Layer — validates and auto-corrects G-code for safe CNC operation.
"""

import re
import math
from config.machine_config import MachineConfig


class SafetyValidator:
    """Validates and auto-corrects G-code for GRBL safety."""

    def __init__(self):
        self.cfg = MachineConfig
        self.warnings = []
        self.errors = []

    def validate(self, gcode_lines):
        """
        Validate and auto-correct G-code lines.

        Returns:
            dict with:
                "gcode": list of corrected G-code lines
                "warnings": list of warning messages
                "errors": list of error messages
                "is_safe": bool
        """
        self.warnings = []
        self.errors = []

        corrected = []
        pen_is_up = True
        last_x, last_y, last_z = 0.0, 0.0, self.cfg.SAFE_Z

        for line_num, raw_line in enumerate(gcode_lines, 1):
            line = raw_line.strip()

            # Pass through comments and empty lines
            if not line or line.startswith(';') or line.startswith('('):
                corrected.append(raw_line)
                continue

            # Check for pen state commands
            if 'M3 S10' in line:
                pen_is_up = False
                corrected.append(raw_line)
                continue
            if 'M3 S70' in line:
                pen_is_up = True
                corrected.append(raw_line)
                continue
            if line.startswith('M2') or line.startswith('M0'):
                corrected.append(raw_line)
                continue

            # Parse G commands
            g_match = re.match(r'G(\d+)', line)
            if not g_match:
                # Non-movement command, pass through
                corrected.append(raw_line)
                continue

            g_code = int(g_match.group(1))

            # Extract coordinates
            x = self._extract_value(line, 'X', last_x)
            y = self._extract_value(line, 'Y', last_y)
            z = self._extract_value(line, 'Z', last_z)
            f = self._extract_value(line, 'F', None)

            # --- Safety checks ---

            # 1. Boundary check
            x, y, z = self._clamp_position(x, y, z, line_num)

            # 2. Feed rate check
            if f is not None:
                f = self._clamp_feed_rate(f, line_num)

            # 3. Rapid move without pen up check
            if g_code == 0 and not pen_is_up:
                self.warnings.append(
                    f"Line {line_num}: Rapid move (G0) with pen down. "
                    f"Inserting pen up."
                )
                corrected.append(f"{self.cfg.PEN_UP_CMD}  ; auto pen up")
                corrected.append(f"G0 Z{self.cfg.SAFE_Z:.2f}  ; auto safe Z")
                pen_is_up = True

            # 4. Draw move with pen up check
            if g_code == 1 and pen_is_up and z <= self.cfg.PEN_DOWN_Z:
                # This is a plunge move, which is fine
                pass

            # Reconstruct the corrected line
            corrected_line = self._reconstruct_line(
                g_code, x, y, z, f, last_x, last_y, last_z, raw_line
            )
            corrected.append(corrected_line)

            last_x, last_y, last_z = x, y, z

        # Final safety: ensure program ends with pen up
        if not pen_is_up:
            self.warnings.append("Program ends with pen down. Adding pen up.")
            corrected.append(f"{self.cfg.PEN_UP_CMD}  ; auto pen up at end")
            corrected.append(f"G0 Z{self.cfg.SAFE_Z:.2f}")

        return {
            "gcode": corrected,
            "warnings": self.warnings,
            "errors": self.errors,
            "is_safe": len(self.errors) == 0,
        }

    def validate_paths(self, paths):
        """
        Validate polyline paths before G-code generation.

        Returns:
            dict with "paths" (clamped), "warnings", "is_valid"
        """
        warnings = []
        validated = []

        for i, path in enumerate(paths):
            new_path = []
            for pt in path:
                x, y = pt[0], pt[1]
                clamped = False
                if x < self.cfg.X_MIN:
                    x = self.cfg.X_MIN
                    clamped = True
                elif x > self.cfg.X_MAX:
                    x = self.cfg.X_MAX
                    clamped = True
                if y < self.cfg.Y_MIN:
                    y = self.cfg.Y_MIN
                    clamped = True
                elif y > self.cfg.Y_MAX:
                    y = self.cfg.Y_MAX
                    clamped = True
                if clamped:
                    warnings.append(
                        f"Path {i}: point clamped to work area bounds"
                    )
                new_path.append((x, y))
            validated.append(new_path)

        return {
            "paths": validated,
            "warnings": warnings,
            "is_valid": True,
        }

    # --- Internal helpers ---

    def _extract_value(self, line, letter, default):
        """Extract a numeric value from a G-code parameter."""
        match = re.search(rf'{letter}([-+]?\d*\.?\d+)', line)
        if match:
            return float(match.group(1))
        return default

    def _clamp_position(self, x, y, z, line_num):
        """Clamp position to machine work area."""
        orig_x, orig_y, orig_z = x, y, z

        x = max(self.cfg.X_MIN, min(self.cfg.X_MAX, x))
        y = max(self.cfg.Y_MIN, min(self.cfg.Y_MAX, y))
        z = max(self.cfg.Z_MIN, min(self.cfg.Z_MAX, z))

        if x != orig_x or y != orig_y or z != orig_z:
            self.warnings.append(
                f"Line {line_num}: Position clamped to work area "
                f"({orig_x:.2f},{orig_y:.2f},{orig_z:.2f}) → "
                f"({x:.2f},{y:.2f},{z:.2f})"
            )

        return x, y, z

    def _clamp_feed_rate(self, f, line_num):
        """Clamp feed rate to safe limits."""
        orig_f = f
        f = max(self.cfg.FEED_RATE_MIN, min(self.cfg.FEED_RATE_MAX, f))
        if f != orig_f:
            self.warnings.append(
                f"Line {line_num}: Feed rate clamped "
                f"{orig_f:.0f} → {f:.0f} mm/min"
            )
        return f

    def _reconstruct_line(self, g, x, y, z, f,
                          last_x, last_y, last_z, original):
        """Reconstruct a G-code line with corrected values."""
        parts = [f"G{g}"]

        if x != last_x or 'X' in original:
            parts.append(f"X{x:.3f}")
        if y != last_y or 'Y' in original:
            parts.append(f"Y{y:.3f}")
        if z != last_z or 'Z' in original:
            parts.append(f"Z{z:.2f}")
        if f is not None and 'F' in original:
            parts.append(f"F{f:.0f}")

        # Preserve inline comment
        comment_match = re.search(r';.*$', original)
        if comment_match:
            parts.append(f" {comment_match.group(0)}")

        return ' '.join(parts)
