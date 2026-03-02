"""
Machine configuration for CNC operating system.
All machine limits, feed rates, and defaults are defined here.
No hardcoded values elsewhere in the project.
"""


class MachineConfig:
    """Central configuration for the CNC machine."""

    # ----- Work Area (mm) -----
    X_MIN = 0.0
    X_MAX = 300.0
    Y_MIN = 0.0
    Y_MAX = 400.0
    Z_MIN = -5.0
    Z_MAX = 10.0

    # ----- Pen Heights (mm) -----
    PEN_UP_Z = 5.0
    PEN_DOWN_Z = 0.0
    SAFE_Z = 5.0

    # ----- Feed Rates (mm/min) -----
    FEED_RATE_DRAW = 800.0
    FEED_RATE_RAPID = 3000.0
    FEED_RATE_PLUNGE = 300.0
    FEED_RATE_MIN = 50.0
    FEED_RATE_MAX = 5000.0

    # ----- G-code Defaults -----
    UNIT_MODE = "G21"        # millimetres
    POSITIONING = "G90"      # absolute
    PEN_DOWN_CMD = "M3 S90"  # servo pen down
    PEN_UP_CMD = "M5"        # servo pen up

    # ----- Arc Fitting -----
    ARC_TOLERANCE = 0.1      # mm – max deviation for arc fitting
    MIN_ARC_POINTS = 4       # minimum points to attempt arc fit

    # ----- Serial / GRBL -----
    SERIAL_PORT = "COM3"
    SERIAL_BAUD = 115200
    GRBL_TIMEOUT = 10        # seconds

    # ----- Drawing Defaults -----
    DEFAULT_FONT_SIZE = 10.0     # mm
    DEFAULT_LINE_SPACING = 1.5   # multiplier
    DEFAULT_CHAR_SPACING = 1.0   # mm
    DEFAULT_ORIGIN_X = 10.0      # mm
    DEFAULT_ORIGIN_Y = 10.0      # mm

    # ----- Image Vectorization -----
    IMAGE_THRESHOLD = 128
    CONTOUR_SIMPLIFY_EPSILON = 1.5  # px – Douglas-Peucker tolerance
    IMAGE_MAX_WIDTH = 280          # mm – leave margin
    IMAGE_MAX_HEIGHT = 380         # mm

    # ----- Server -----
    FLASK_HOST = "0.0.0.0"
    FLASK_PORT = 5000
    UPLOAD_FOLDER = "uploads"
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB

    @classmethod
    def work_area(cls):
        """Return work area bounds as dict."""
        return {
            "x_min": cls.X_MIN, "x_max": cls.X_MAX,
            "y_min": cls.Y_MIN, "y_max": cls.Y_MAX,
            "z_min": cls.Z_MIN, "z_max": cls.Z_MAX,
        }

    @classmethod
    def is_within_bounds(cls, x, y):
        """Check if point is within machine work area."""
        return (cls.X_MIN <= x <= cls.X_MAX and
                cls.Y_MIN <= y <= cls.Y_MAX)
