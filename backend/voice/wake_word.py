from __future__ import annotations

import logging
import os
import sys
import threading
import time
from pathlib import Path
from typing import Optional

import numpy as np
import sounddevice as sd
from openwakeword.model import Model

logger = logging.getLogger("eggman")


class WakeWordService:
    """Service that runs a background thread to detect the 'EggMan' wake word."""

    def __init__(self, voice_manager, config_manager, project_root: Optional[str | Path] = None) -> None:
        self._voice_manager = voice_manager
        self._config_manager = config_manager
        self._project_root = Path(project_root) if project_root else Path(__file__).resolve().parents[2]

        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._paused = False
        self._model: Optional[Model] = None
        self._wakeword_name = "hey_jarvis"
        self._is_running = False

        # Register state listener on VoiceManager
        if hasattr(self._voice_manager, "add_state_changed_listener"):
            self._voice_manager.add_state_changed_listener(self._on_voice_state_changed)

        # Audio parameters
        self._sample_rate = 16000
        self._chunk_size = 1280

    def start(self) -> None:
        """Start the background wake word thread if enabled and not already running."""
        if not self._config_manager.get("wake_word_enabled"):
            logger.info("Wake word is disabled in settings; not starting WakeWordService")
            return

        if self._is_running:
            return

        self._stop_event.clear()
        self._paused = False
        self._is_running = True

        self._thread = threading.Thread(target=self._run_loop, name="WakeWordServiceThread", daemon=True)
        self._thread.start()
        logger.info("Wake-word service started")

    def stop(self) -> None:
        """Stop the background thread and clean up resources."""
        if not self._is_running:
            return

        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)

        self._is_running = False
        self._thread = None
        logger.info("Wake word system stopped")

    def pause(self) -> None:
        """Pause listening (releases the microphone)."""
        if not self._paused:
            self._paused = True
            logger.debug("WakeWordService paused")

    def resume(self) -> None:
        """Resume listening."""
        if self._paused:
            if self._model:
                try:
                    self._model.reset()
                except Exception as e:
                    logger.debug("Failed to reset openWakeWord model: %s", e)
            self._paused = False
            logger.debug("WakeWordService resumed")

    def _initialize_model(self) -> bool:
        try:
            logger.info("Loading built-in 'alexa' wake word model.")
            self._model = Model(wakeword_models=["alexa"], inference_framework="onnx")
            self._wakeword_name = "alexa"
            logger.info("Detector initialized")
            return True
        except Exception as exc:
            logger.error("Wake word error: Failed to initialize openWakeWord model: %s", exc)
            return False

    def _run_loop(self) -> None:
        if not self._initialize_model():
            self._is_running = False
            return

        while not self._stop_event.is_set():
            if self._paused:
                time.sleep(0.1)
                continue

            try:
                # Open mic stream for wake word detection
                # Read chunks of 1280 samples at 16000Hz mono int16
                with sd.InputStream(
                    samplerate=self._sample_rate,
                    channels=1,
                    dtype="int16",
                    blocksize=self._chunk_size
                ) as stream:
                    logger.info("Audio stream opened")
                    while not self._stop_event.is_set() and not self._paused:
                        # Blocking read of 1280 frames
                        data, overflowed = stream.read(self._chunk_size)
                        if data.size == 0:
                            continue

                        # Log frames received
                        logger.info("Frames received")

                        # Reshape/flatten for model input
                        audio_chunk = data.flatten()

                        # Get predictions
                        prediction = self._model.predict(audio_chunk)
                        score = prediction.get(self._wakeword_name, 0.0)

                        # Log detector confidence score
                        logger.info("Detector confidence score: %f", score)

                        if score > 0.5:
                            logger.info("Wake word detected")
                            self._trigger_wake_word_activation()
                            break  # Exit inner loop to release stream for VoiceManager

            except Exception as exc:
                logger.error("Wake word error: Microphone read or prediction failed: %s", exc)
                time.sleep(1.0)  # Avoid tight error loop

    def _trigger_wake_word_activation(self) -> None:
        # Pause ourselves first to release the microphone
        self.pause()

        # Begin speech recording (state listener will log "Recording started")
        self._voice_manager.toggle_listening()

    def _on_voice_state_changed(self, state) -> None:
        from backend.voice.voice_manager import VoiceState
        # Log recording state changes
        if state == VoiceState.LISTENING:
            logger.info("Recording started")
        elif state == VoiceState.PROCESSING:
            logger.info("Recording stopped")
        elif state == VoiceState.IDLE:
            if self._is_running:
                # We resume with a slight delay to avoid instantly self-triggering on own audio
                threading.Timer(1.0, self.resume).start()

    def _play_confirmation_sound(self) -> None:
        if sys.platform == "win32":
            try:
                import winsound
                winsound.Beep(1000, 150)
            except Exception as e:
                logger.error("Wake word error: Failed to play winsound beep: %s", e)
        else:
            try:
                # Fallback sine wave beep via sounddevice
                duration = 0.15
                frequency = 1000.0
                t = np.linspace(0, duration, int(self._sample_rate * duration), False)
                tone = np.sin(frequency * t * 2 * np.pi)
                sd.play(tone.astype(np.float32), self._sample_rate)
                sd.wait()
            except Exception as e:
                logger.error("Wake word error: Failed to play sounddevice fallback beep: %s", e)
