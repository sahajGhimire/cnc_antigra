"""
Flask Application Factory for CNC Operating System.
"""

import os
from flask import Flask
from config.machine_config import MachineConfig


def create_app():
    """Create and configure the Flask application."""
    app = Flask(
        __name__,
        static_folder='static',
        template_folder='templates',
    )

    cfg = MachineConfig

    # Configuration
    app.config['MAX_CONTENT_LENGTH'] = cfg.MAX_CONTENT_LENGTH
    app.config['UPLOAD_FOLDER'] = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        cfg.UPLOAD_FOLDER,
    )

    # Ensure upload directory exists
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

    # Register routes
    from web.routes import register_routes
    register_routes(app)

    return app
