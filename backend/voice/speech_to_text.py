from __future__ import annotations

import logging
from typing import Optional

import numpy as np

import time

logger = logging.getLogger("eggman")


class SpeechToTextService:
    """Local speech recognition using Faster-Whisper."""

    DEFAULT_MODEL = "base"
    DEFAULT_SAMPLE_RATE = 16000

    def __init__(
        self,
        model_size: Optional[str] = None,
        device: str = "cpu",
        compute_type: str = "int8",
        sample_rate: int = DEFAULT_SAMPLE_RATE,
    ) -> None:
        self._model_size = model_size or self.DEFAULT_MODEL
        self._device = device
        self._compute_type = compute_type
        self._sample_rate = sample_rate
        self._model = None
        self._load_error: str | None = None
        logger.info(
            "SpeechToTextService configured model=%s device=%s compute_type=%s",
            self._model_size,
            self._device,
            self._compute_type,
        )

    @property
    def sample_rate(self) -> int:
        return self._sample_rate

    def is_available(self) -> bool:
        try:
            self._ensure_model()
            return self._model is not None
        except Exception as exc:
            self._load_error = str(exc)
            return False

    def availability_error(self) -> str | None:
        if self._load_error:
            return self._load_error
        try:
            self._ensure_model()
        except Exception as exc:
            self._load_error = str(exc)
            return self._load_error
        return None

    def transcribe(self, audio: np.ndarray, sample_rate: int | None = None) -> str:
        """Transcribe a mono float32/float64 audio buffer."""
        start = time.perf_counter()
        self._ensure_model()

        if audio.size == 0:
            logger.warning("SpeechToTextService received empty audio buffer")
            return ""

        rate = sample_rate or self._sample_rate
        mono = self._to_mono_float32(audio)
        logger.info("SpeechToTextService transcribing samples=%d sample_rate=%d", mono.size, rate)

        try:
            segments, info = self._model.transcribe(
                mono,
                language="en",
                beam_size=1,
                vad_filter=True,
            )
            text = "".join(segment.text for segment in segments).strip()
            elapsed_ms = (time.perf_counter() - start) * 1000
            logger.info(
                "SpeechToTextService transcription completed elapsed_ms=%.1f text_len=%d language=%s",
                elapsed_ms,
                len(text),
                getattr(info, "language", "unknown"),
            )
            logger.debug("SpeechToTextService transcription text=%r", text)
            return text
        except Exception as exc:
            elapsed_ms = (time.perf_counter() - start) * 1000
            logger.exception("SpeechToTextService transcription failed elapsed_ms=%.1f error=%s", elapsed_ms, exc)
            raise RuntimeError(f"Speech recognition failed: {exc}") from exc

    def _ensure_model(self) -> None:
        if self._model is not None:
            return
        try:
            from faster_whisper import WhisperModel
        except ImportError as exc:
            raise RuntimeError(
                "faster-whisper is not installed. Install voice dependencies from requirements.txt."
            ) from exc

        start = time.perf_counter()
        logger.info("SpeechToTextService loading model=%s", self._model_size)
        try:
            self._model = WhisperModel(
                self._model_size,
                device=self._device,
                compute_type=self._compute_type,
            )
            elapsed_ms = (time.perf_counter() - start) * 1000
            logger.info("SpeechToTextService model loaded elapsed_ms=%.1f", elapsed_ms)
        except Exception as exc:
            logger.exception("SpeechToTextService model load failed: %s", exc)
            raise RuntimeError(f"Could not load speech model '{self._model_size}': {exc}") from exc

    @staticmethod
    def _to_mono_float32(audio: np.ndarray) -> np.ndarray:
        data = np.asarray(audio)
        if data.ndim > 1:
            data = np.mean(data, axis=1)
        if data.dtype != np.float32:
            if np.issubdtype(data.dtype, np.integer):
                data = data.astype(np.float32) / np.iinfo(data.dtype).max
            else:
                data = data.astype(np.float32)
        return np.ascontiguousarray(data)
