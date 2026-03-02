"""
Voice Recognizer — transcribes audio using Whisper (local) or returns
text for frontend Web Speech API results.

Supports English and Nepali.
"""

import os
import tempfile

try:
    import whisper
    HAS_WHISPER = True
except ImportError:
    HAS_WHISPER = False


class VoiceRecognizer:
    """Audio transcription using OpenAI Whisper."""

    SUPPORTED_LANGUAGES = {
        "en": "english",
        "ne": "nepali",
    }

    def __init__(self, model_name="base"):
        """
        Initialize the recognizer.

        Args:
            model_name: Whisper model size ("tiny", "base", "small", etc.)
        """
        self.model_name = model_name
        self.model = None
        self._loaded = False

    def is_available(self):
        """Check if Whisper is available."""
        return HAS_WHISPER

    def load_model(self):
        """Load the Whisper model (lazy loading)."""
        if not HAS_WHISPER:
            return {
                "success": False,
                "message": "openai-whisper not installed. "
                           "Install: pip install openai-whisper",
            }
        if self._loaded:
            return {"success": True, "message": "Model already loaded"}

        try:
            self.model = whisper.load_model(self.model_name)
            self._loaded = True
            return {
                "success": True,
                "message": f"Loaded Whisper model: {self.model_name}",
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"Failed to load model: {str(e)}",
            }

    def transcribe(self, audio_bytes, language=None):
        """
        Transcribe audio bytes to text.

        Args:
            audio_bytes: Raw audio data (WAV, MP3, etc.).
            language: Language code ("en" or "ne"). Auto-detect if None.

        Returns:
            dict with "success", "text", "language", "message"
        """
        if not HAS_WHISPER:
            return {
                "success": False,
                "text": "",
                "language": None,
                "message": "Whisper not available. Use Web Speech API on frontend.",
            }

        if not self._loaded:
            load_result = self.load_model()
            if not load_result["success"]:
                return {
                    "success": False,
                    "text": "",
                    "language": None,
                    "message": load_result["message"],
                }

        # Write temporary audio file
        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(
                suffix=".wav", delete=False
            ) as tmp:
                tmp.write(audio_bytes)
                tmp_path = tmp.name

            # Transcribe
            options = {}
            if language and language in self.SUPPORTED_LANGUAGES:
                options["language"] = language

            result = self.model.transcribe(tmp_path, **options)

            return {
                "success": True,
                "text": result["text"].strip(),
                "language": result.get("language", language or "auto"),
                "message": "Transcription complete",
            }

        except Exception as e:
            return {
                "success": False,
                "text": "",
                "language": None,
                "message": f"Transcription error: {str(e)}",
            }

        finally:
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass

    def transcribe_file(self, file_path, language=None):
        """
        Transcribe an audio file to text.

        Args:
            file_path: Path to audio file.
            language: Language code or None for auto-detect.

        Returns:
            dict with "success", "text", "language", "message"
        """
        try:
            with open(file_path, 'rb') as f:
                audio_bytes = f.read()
            return self.transcribe(audio_bytes, language)
        except FileNotFoundError:
            return {
                "success": False,
                "text": "",
                "language": None,
                "message": f"File not found: {file_path}",
            }
        except Exception as e:
            return {
                "success": False,
                "text": "",
                "language": None,
                "message": f"File read error: {str(e)}",
            }


# Module-level singleton
_recognizer = None


def get_recognizer():
    """Get or create the global VoiceRecognizer instance."""
    global _recognizer
    if _recognizer is None:
        _recognizer = VoiceRecognizer()
    return _recognizer
