"""
GRBL Streaming — serial G-code sender with feedback and error handling.
"""

import time
import threading

try:
    import serial
    HAS_SERIAL = True
except ImportError:
    HAS_SERIAL = False

from config.machine_config import MachineConfig


class GRBLStreamer:
    """Manages serial connection to a GRBL controller and streams G-code."""

    def __init__(self, port=None, baud=None, timeout=None):
        cfg = MachineConfig
        self.port = port or cfg.SERIAL_PORT
        self.baud = baud or cfg.SERIAL_BAUD
        self.timeout = timeout or cfg.GRBL_TIMEOUT
        self.serial_conn = None
        self.is_connected = False
        self.is_streaming = False
        self.is_paused = False
        self._abort = False
        self._lock = threading.Lock()
        self.progress = {"total": 0, "sent": 0, "status": "idle"}
        self.errors = []

    def connect(self):
        """
        Open serial connection to GRBL controller.

        Returns:
            dict with "success", "message", "version"
        """
        if not HAS_SERIAL:
            return {
                "success": False,
                "message": "pyserial not installed. Install: pip install pyserial",
                "version": None,
            }

        try:
            self.serial_conn = serial.Serial(
                self.port, self.baud, timeout=self.timeout
            )
            time.sleep(2)  # GRBL wakeup delay

            # Flush startup message
            self.serial_conn.flushInput()

            # Send soft reset
            self.serial_conn.write(b"\r\n\r\n")
            time.sleep(1)

            # Read GRBL version
            version = ""
            while self.serial_conn.inWaiting():
                line = self.serial_conn.readline().decode('utf-8', errors='ignore').strip()
                if line and 'Grbl' in line:
                    version = line

            self.is_connected = True
            return {
                "success": True,
                "message": f"Connected to {self.port}",
                "version": version or "unknown",
            }

        except serial.SerialException as e:
            return {
                "success": False,
                "message": f"Connection failed: {str(e)}",
                "version": None,
            }

    def disconnect(self):
        """Close serial connection."""
        if self.serial_conn and self.serial_conn.is_open:
            self.serial_conn.close()
        self.is_connected = False
        self.is_streaming = False
        return {"success": True, "message": "Disconnected"}

    def stream(self, gcode_lines, callback=None):
        """
        Stream G-code lines to GRBL, one at a time with acknowledge.

        Args:
            gcode_lines: List of G-code strings.
            callback: Optional function called with progress dict after each line.

        Returns:
            dict with "success", "message", "lines_sent", "errors"
        """
        if not self.is_connected:
            return {
                "success": False,
                "message": "Not connected to GRBL",
                "lines_sent": 0,
                "errors": ["Not connected"],
            }

        self.is_streaming = True
        self.is_paused = False
        self._abort = False
        self.errors = []

        # Filter empty / comment-only lines
        commands = []
        for line in gcode_lines:
            stripped = line.strip()
            if stripped and not stripped.startswith(';') and not stripped.startswith('('):
                # Remove inline comments
                if ';' in stripped:
                    stripped = stripped[:stripped.index(';')].strip()
                if stripped:
                    commands.append(stripped)

        self.progress = {
            "total": len(commands),
            "sent": 0,
            "status": "streaming",
        }

        try:
            for i, cmd in enumerate(commands):
                # Check abort
                if self._abort:
                    self.progress["status"] = "aborted"
                    break

                # Pause loop
                while self.is_paused and not self._abort:
                    self.progress["status"] = "paused"
                    time.sleep(0.1)

                if self._abort:
                    self.progress["status"] = "aborted"
                    break

                # Send command
                with self._lock:
                    self.serial_conn.write((cmd + '\n').encode())

                    # Wait for 'ok' or 'error'
                    response = self._read_response()
                    if response.startswith('error'):
                        self.errors.append(f"Line {i + 1} ({cmd}): {response}")

                self.progress["sent"] = i + 1
                self.progress["status"] = "streaming"

                if callback:
                    callback(dict(self.progress))

        except Exception as e:
            self.errors.append(f"Stream error: {str(e)}")
            self.progress["status"] = "error"

        self.is_streaming = False
        if not self._abort and not self.errors:
            self.progress["status"] = "complete"

        return {
            "success": len(self.errors) == 0 and not self._abort,
            "message": self.progress["status"],
            "lines_sent": self.progress["sent"],
            "errors": self.errors,
        }

    def pause(self):
        """Pause streaming."""
        self.is_paused = True
        # Send feed hold to GRBL
        if self.serial_conn and self.serial_conn.is_open:
            self.serial_conn.write(b'!')
        return {"success": True, "status": "paused"}

    def resume(self):
        """Resume streaming."""
        self.is_paused = False
        # Send cycle start to GRBL
        if self.serial_conn and self.serial_conn.is_open:
            self.serial_conn.write(b'~')
        return {"success": True, "status": "resumed"}

    def abort(self):
        """Abort streaming and send soft reset."""
        self._abort = True
        self.is_paused = False
        if self.serial_conn and self.serial_conn.is_open:
            self.serial_conn.write(b'\x18')  # GRBL soft reset
        return {"success": True, "status": "aborted"}

    def get_status(self):
        """Query GRBL status."""
        if not self.is_connected:
            return {"connected": False, "status": "disconnected"}

        try:
            self.serial_conn.write(b'?')
            response = self._read_response()
            return {
                "connected": True,
                "status": response,
                "progress": dict(self.progress),
            }
        except Exception as e:
            return {
                "connected": True,
                "status": f"error: {str(e)}",
                "progress": dict(self.progress),
            }

    def list_ports(self):
        """List available serial ports."""
        if not HAS_SERIAL:
            return []
        try:
            from serial.tools import list_ports
            return [
                {"port": p.device, "description": p.description}
                for p in list_ports.comports()
            ]
        except Exception:
            return []

    def _read_response(self):
        """Read a line response from GRBL."""
        try:
            line = self.serial_conn.readline().decode('utf-8', errors='ignore').strip()
            return line if line else "ok"
        except Exception:
            return "error:timeout"
