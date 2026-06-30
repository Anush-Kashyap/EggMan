from __future__ import annotations

import logging
import re
import threading
import time
from enum import Enum
from typing import Callable, Optional

import numpy as np

from backend.voice.speech_to_text import SpeechToTextService

logger = logging.getLogger("eggman")


class VoiceState(str, Enum):
    IDLE = "idle"
    LISTENING = "listening"
    PROCESSING = "processing"


VoiceStateCallback = Callable[[VoiceState], None]
TranscriptionCallback = Callable[[str], None]
ErrorCallback = Callable[[str], None]


class VoiceManager:
    """Coordinates microphone capture and speech-to-text on a background thread.

    Designed as the single entry point for voice input so wake-word detection and
    text-to-speech can be layered on later without changing callers.
    """

    def __init__(
        self,
        speech_service: SpeechToTextService | None = None,
        on_state_changed: VoiceStateCallback | None = None,
        on_transcription: TranscriptionCallback | None = None,
        on_error: ErrorCallback | None = None,
    ) -> None:
        self._speech = speech_service or SpeechToTextService()
        self._on_state_changed = on_state_changed
        self._on_transcription = on_transcription
        self._on_error = on_error
        self._state = VoiceState.IDLE
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._worker: threading.Thread | None = None
        self._frames: list[np.ndarray] = []
        self._stream = None
        self._state_changed_listeners = []
        logger.info("VoiceManager initialized sample_rate=%d", self._speech.sample_rate)

    @property
    def state(self) -> VoiceState:
        return self._state

    @property
    def _state(self) -> VoiceState:
        from backend.session.session_manager import SessionManager
        val = SessionManager.get_instance().context.voice_state
        return VoiceState(val) if val else VoiceState.IDLE

    @_state.setter
    def _state(self, val: VoiceState) -> None:
        from backend.session.session_manager import SessionManager
        SessionManager.get_instance().context.voice_state = val.value

    def bind_callbacks(
        self,
        on_state_changed: VoiceStateCallback | None = None,
        on_transcription: TranscriptionCallback | None = None,
        on_error: ErrorCallback | None = None,
    ) -> None:
        if on_state_changed is not None:
            self._on_state_changed = on_state_changed
        if on_transcription is not None:
            self._on_transcription = on_transcription
        if on_error is not None:
            self._on_error = on_error

    def add_state_changed_listener(self, listener: Callable[[VoiceState], None]) -> None:
        self._state_changed_listeners.append(listener)

    def toggle_listening(self) -> None:
        """Start recording, or stop and transcribe if already listening."""
        with self._lock:
            if self._state == VoiceState.PROCESSING:
                logger.debug("VoiceManager toggle ignored while processing")
                return
            if self._state == VoiceState.LISTENING:
                logger.info("VoiceManager stopping recording")
                self._stop_event.set()
                return
            if self._worker is not None and self._worker.is_alive():
                logger.debug("VoiceManager toggle ignored; worker still active")
                return
            self._begin_recording_locked()

    def stop(self) -> None:
        """Release microphone resources and cancel any active capture."""
        with self._lock:
            self._stop_event.set()
            self._close_stream()
            worker = self._worker
        if worker is not None and worker.is_alive() and worker is not threading.current_thread():
            worker.join(timeout=2.0)
        self._set_state(VoiceState.IDLE)

    def _begin_recording_locked(self) -> None:
        availability_error = self._speech.availability_error()
        if availability_error:
            logger.error("VoiceManager cannot start recording: %s", availability_error)
            self._emit_error(
                "Voice input is unavailable. Install faster-whisper and check your microphone setup."
            )
            return

        self._frames = []
        self._stop_event.clear()
        self._set_state(VoiceState.LISTENING)
        self._worker = threading.Thread(target=self._record_and_transcribe, name="VoiceManagerWorker", daemon=True)
        self._worker.start()
        logger.info("VoiceManager recording started")

    def _record_and_transcribe(self) -> None:
        start = time.perf_counter()
        try:
            audio = self._capture_audio()
            record_ms = (time.perf_counter() - start) * 1000
            logger.info("VoiceManager recording finished elapsed_ms=%.1f samples=%d", record_ms, audio.size)

            if audio.size == 0:
                logger.warning("VoiceManager captured no audio")
                self._emit_error("I didn't hear anything. Try speaking again.")
                self._set_state(VoiceState.IDLE)
                return

            self._set_state(VoiceState.PROCESSING)
            transcribe_start = time.perf_counter()
            text = self._speech.transcribe(audio, sample_rate=self._speech.sample_rate)
            transcribe_ms = (time.perf_counter() - transcribe_start) * 1000
            logger.info("VoiceManager transcription finished elapsed_ms=%.1f text_len=%d", transcribe_ms, len(text))

            if not text:
                self._emit_error("I couldn't understand that. Please try again.")
                self._set_state(VoiceState.IDLE)
                return

            normalized = self._normalize_spoken_text(text)
            logger.info("VoiceManager submitting transcription text=%r normalized=%r", text, normalized)
            if self._on_transcription is not None:
                self._on_transcription(normalized)
            self._set_state(VoiceState.IDLE)
        except Exception as exc:
            logger.exception("VoiceManager record/transcribe failed: %s", exc)
            self._emit_error(self._friendly_error(exc))
            self._set_state(VoiceState.IDLE)
        finally:
            with self._lock:
                self._worker = None

    def _capture_audio(self) -> np.ndarray:
        try:
            import sounddevice as sd
        except ImportError as exc:
            raise RuntimeError("sounddevice is not installed. Install voice dependencies from requirements.txt.") from exc

        sample_rate = self._speech.sample_rate
        block_size = 1024
        self._frames = []

        # Adaptive VAD tracking variables
        has_spoken = False
        max_rms = 0.001
        silence_seconds = 0.0
        elapsed_seconds = 0.0

        # VAD Parameters
        SPEECH_MIN_RMS = 0.007    # Sensitive threshold to capture quiet speech
        SILENCE_TIMEOUT = 2.0      # Stop after 2.0s of silence once speech started (longer pause allowed)
        MAX_START_DELAY = 4.0     # Stop if they don't start speaking in 4s
        MAX_DURATION = 15.0       # Max recording time (longer sentences allowed)

        def callback(indata, frames, time_info, status) -> None:
            if status:
                logger.warning("VoiceManager audio stream status=%s", status)
            self._frames.append(indata.copy())

        try:
            self._stream = sd.InputStream(
                samplerate=sample_rate,
                channels=1,
                dtype="float32",
                blocksize=block_size,
                callback=callback,
            )
            self._stream.start()
            logger.debug("VoiceManager microphone stream opened")
            
            last_checked_idx = 0
            while not self._stop_event.is_set():
                time.sleep(0.05)
                elapsed_seconds += 0.05

                current_frames = len(self._frames)
                if current_frames > last_checked_idx:
                    for i in range(last_checked_idx, current_frames):
                        frame = self._frames[i]
                        rms = np.sqrt(np.mean(frame**2))

                        if rms > SPEECH_MIN_RMS:
                            has_spoken = True
                            silence_seconds = 0.0
                        else:
                            if has_spoken:
                                silence_seconds += (block_size / sample_rate)

                    last_checked_idx = current_frames

                # Check timeouts
                if has_spoken and silence_seconds >= SILENCE_TIMEOUT:
                    logger.info("VoiceManager: Silence detected. Stopping recording automatically.")
                    break
                if not has_spoken and elapsed_seconds >= MAX_START_DELAY:
                    logger.info("VoiceManager: No speech detected on startup. Stopping recording automatically.")
                    break
                if elapsed_seconds >= MAX_DURATION:
                    logger.info("VoiceManager: Maximum duration reached. Stopping recording automatically.")
                    break

        except Exception as exc:
            logger.exception("VoiceManager microphone open failed: %s", exc)
            raise RuntimeError(self._microphone_error(exc)) from exc
        finally:
            self._close_stream()

        if not self._frames:
            return np.array([], dtype=np.float32)
        return np.concatenate(self._frames, axis=0).reshape(-1)

    def _close_stream(self) -> None:
        if self._stream is None:
            return
        try:
            self._stream.stop()
            self._stream.close()
            logger.debug("VoiceManager microphone stream closed")
        except Exception as exc:
            logger.warning("VoiceManager microphone close failed: %s", exc)
        finally:
            self._stream = None

    def _normalize_spoken_text(self, text: str) -> str:
        """Adjust common spoken phrasing so tool routing matches typed commands."""
        cleaned = re.sub(r"\s+", " ", text.strip())
        if not cleaned:
            return cleaned

        calc_prefix = re.match(r"^(calculate|calc|compute|evaluate)\s+(.+)$", cleaned, re.IGNORECASE)
        if calc_prefix:
            command = calc_prefix.group(1)
            expression = self._normalize_spoken_expression(calc_prefix.group(2))
            return f"{command} {expression}"

        question_prefix = re.match(r"^(what is|what's)\s+(.+?)\??$", cleaned, re.IGNORECASE)
        if question_prefix:
            expression = self._normalize_spoken_expression(question_prefix.group(2))
            if self._looks_like_spoken_arithmetic(expression):
                return f"what is {expression}"

        return cleaned

    @staticmethod
    def _normalize_spoken_expression(expression: str) -> str:
        normalized = expression.strip()
        replacements = [
            (r"\btimes\b", "*"),
            (r"\bmultiplied by\b", "*"),
            (r"\bplus\b", "+"),
            (r"\bminus\b", "-"),
            (r"\bdivided by\b", "/"),
            (r"\bover\b", "/"),
        ]
        for pattern, symbol in replacements:
            normalized = re.sub(pattern, symbol, normalized, flags=re.IGNORECASE)
        return re.sub(r"\s+", " ", normalized).strip()

    @staticmethod
    def _looks_like_spoken_arithmetic(expression: str) -> bool:
        return bool(re.search(r"\d", expression) and re.search(r"[+\-*/]", expression))

    def _set_state(self, state: VoiceState) -> None:
        self._state = state
        logger.debug("VoiceManager state=%s", state.value)

        # Update is_listening flag
        from backend.session.session_manager import SessionManager
        SessionManager.get_instance().context.is_listening = (state == VoiceState.LISTENING)

        if self._on_state_changed is not None:
            self._on_state_changed(state)
        for listener in self._state_changed_listeners:
            try:
                listener(state)
            except Exception as e:
                logger.error("Error in state changed listener: %s", e)

    def _emit_error(self, message: str) -> None:
        logger.error("VoiceManager error: %s", message)
        if self._on_error is not None:
            self._on_error(message)

    @staticmethod
    def _microphone_error(exc: Exception) -> str:
        message = str(exc).lower()
        if "permission" in message or "access" in message:
            return "Microphone access was denied. Check Windows privacy settings."
        if "device" in message or "portaudio" in message:
            return "No microphone was found. Connect a microphone and try again."
        return f"Microphone error: {exc}"

    @staticmethod
    def _friendly_error(exc: Exception) -> str:
        message = str(exc)
        lowered = message.lower()
        if "microphone" in lowered or "sounddevice" in lowered:
            return message
        if "speech" in lowered or "whisper" in lowered or "model" in lowered:
            return message
        return f"Voice input failed: {message}"
