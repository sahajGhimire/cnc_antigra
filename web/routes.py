"""
API Routes for CNC Operating System.
"""

import os
import io
import json
import tempfile
from flask import (
    Blueprint, request, jsonify, render_template,
    current_app, send_from_directory
)
from modes.writing_mode import generate as write_generate
from modes.drawing_mode import generate_shape, list_shapes
from image.vectorizer import vectorize_image
from streaming.grbl_stream import GRBLStreamer
from config.machine_config import MachineConfig

# Global GRBL streamer instance
_streamer = GRBLStreamer()


def register_routes(app):
    """Register all routes with the Flask app."""

    @app.route('/')
    def index():
        return render_template('index.html')

    # ------------------------------------------------------------------
    # Writing Mode
    # ------------------------------------------------------------------
    @app.route('/api/write', methods=['POST'])
    def api_write():
        data = request.get_json(force=True)
        text = data.get('text', '')
        x = data.get('x')
        y = data.get('y')
        font_size = data.get('font_size')
        line_spacing = data.get('line_spacing')
        feed_rate = data.get('feed_rate')

        if x is not None:
            x = float(x)
        if y is not None:
            y = float(y)
        if font_size is not None:
            font_size = float(font_size)
        if line_spacing is not None:
            line_spacing = float(line_spacing)
        if feed_rate is not None:
            feed_rate = float(feed_rate)

        result = write_generate(
            text, x=x, y=y, font_size=font_size,
            line_spacing=line_spacing, feed_rate=feed_rate
        )

        return jsonify({
            'svg': result['svg'],
            'gcode': result['gcode'],
            'warnings': result['warnings'],
            'char_count': result['char_count'],
            'line_count': result['line_count'],
        })

    # ------------------------------------------------------------------
    # Drawing Mode
    # ------------------------------------------------------------------
    @app.route('/api/draw', methods=['POST'])
    def api_draw():
        data = request.get_json(force=True)
        shape_type = data.get('shape', 'circle')
        params = data.get('params', {})

        result = generate_shape(shape_type, params)

        return jsonify({
            'svg': result['svg'],
            'gcode': result['gcode'],
            'warnings': result['warnings'],
        })

    @app.route('/api/shapes', methods=['GET'])
    def api_shapes():
        return jsonify(list_shapes())

    # ------------------------------------------------------------------
    # Voice Input
    # ------------------------------------------------------------------
    @app.route('/api/voice', methods=['POST'])
    def api_voice():
        try:
            from voice.recognizer import transcribe
        except ImportError:
            return jsonify({
                'text': '',
                'error': 'Voice recognizer module not available',
            }), 500

        if 'audio' not in request.files:
            return jsonify({'text': '', 'error': 'No audio file provided'}), 400

        audio_file = request.files['audio']
        audio_bytes = audio_file.read()

        result = transcribe(audio_bytes=audio_bytes)
        return jsonify(result)

    # ------------------------------------------------------------------
    # Image Vectorization
    # ------------------------------------------------------------------
    @app.route('/api/image', methods=['POST'])
    def api_image():
        if 'image' not in request.files:
            return jsonify({'error': 'No image file provided'}), 400

        image_file = request.files['image']

        # Save to temp file
        ext = os.path.splitext(image_file.filename)[1] or '.png'
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=ext)
        try:
            image_file.save(tmp.name)
            tmp.close()

            params = {}
            for key in ['threshold', 'epsilon', 'max_width', 'max_height',
                         'offset_x', 'offset_y']:
                val = request.form.get(key)
                if val is not None:
                    params[key] = float(val)

            invert = request.form.get('invert', 'false').lower() == 'true'

            result = vectorize_image(
                image_path=tmp.name,
                invert=invert,
                **params
            )

            return jsonify({
                'svg': result['svg'],
                'gcode': result['gcode'],
                'warnings': result['warnings'],
                'contour_count': result['contour_count'],
                'point_count': result['point_count'],
            })
        finally:
            os.unlink(tmp.name)

    # ------------------------------------------------------------------
    # GRBL Streaming
    # ------------------------------------------------------------------
    @app.route('/api/stream/connect', methods=['POST'])
    def api_connect():
        data = request.get_json(force=True) if request.data else {}
        port = data.get('port')
        if port:
            _streamer.port = port
        result = _streamer.connect()
        return jsonify(result)

    @app.route('/api/stream/disconnect', methods=['POST'])
    def api_disconnect():
        result = _streamer.disconnect()
        return jsonify(result)

    @app.route('/api/stream/send', methods=['POST'])
    def api_stream_send():
        data = request.get_json(force=True)
        gcode = data.get('gcode', '')
        lines = gcode.strip().split('\n') if gcode else []
        result = _streamer.stream(lines)
        return jsonify(result)

    @app.route('/api/stream/pause', methods=['POST'])
    def api_pause():
        return jsonify(_streamer.pause())

    @app.route('/api/stream/resume', methods=['POST'])
    def api_resume():
        return jsonify(_streamer.resume())

    @app.route('/api/stream/abort', methods=['POST'])
    def api_abort():
        return jsonify(_streamer.abort())

    @app.route('/api/stream/status', methods=['GET'])
    def api_stream_status():
        return jsonify(_streamer.get_status())

    @app.route('/api/stream/ports', methods=['GET'])
    def api_list_ports():
        return jsonify(_streamer.list_ports())

    # ------------------------------------------------------------------
    # Preview (standalone SVG)
    # ------------------------------------------------------------------
    @app.route('/api/preview', methods=['POST'])
    def api_preview():
        data = request.get_json(force=True)
        svg = data.get('svg', '')
        return svg, 200, {'Content-Type': 'image/svg+xml'}

    # ------------------------------------------------------------------
    # Machine Config
    # ------------------------------------------------------------------
    @app.route('/api/config', methods=['GET'])
    def api_config():
        cfg = MachineConfig
        return jsonify({
            'work_area': cfg.work_area(),
            'feed_rate_draw': cfg.FEED_RATE_DRAW,
            'feed_rate_rapid': cfg.FEED_RATE_RAPID,
            'default_font_size': cfg.DEFAULT_FONT_SIZE,
            'serial_port': cfg.SERIAL_PORT,
        })
