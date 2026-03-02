"""
CNC Operating System — Entry Point
"""

import sys
import os

# Ensure project root is on Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from web.app import create_app
from config.machine_config import MachineConfig


def main():
    app = create_app()
    cfg = MachineConfig
    print(f"\n  CNC Operating System")
    print(f"  Server: http://{cfg.FLASK_HOST}:{cfg.FLASK_PORT}")
    print(f"  Work area: {cfg.X_MAX}x{cfg.Y_MAX} mm\n")
    app.run(
        host=cfg.FLASK_HOST,
        port=cfg.FLASK_PORT,
        debug=True,
    )


if __name__ == '__main__':
    main()
