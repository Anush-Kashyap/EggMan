from __future__ import annotations
import logging
from typing import Optional
from PySide6.QtCore import QBuffer, QIODevice
from PySide6.QtWidgets import QApplication

from backend.vision.image_source import ImageSource

logger = logging.getLogger("eggman")


class ScreenshotSource(ImageSource):
    """Source that captures the primary screen/monitor using PySide6."""

    def capture(self) -> Optional[bytes]:
        try:
            screen = QApplication.primaryScreen()
            if not screen:
                logger.error("Vision error: No primary screen found during capture")
                return None

            # Grab primary monitor window
            pixmap = screen.grabWindow(0)

            # Save to buffer as PNG bytes
            buffer = QBuffer()
            buffer.open(QIODevice.WriteOnly)
            if not pixmap.save(buffer, "PNG"):
                logger.error("Vision error: Failed to save screen capture to PNG format")
                return None

            image_bytes = buffer.data().data()
            logger.info("Screenshot captured")
            return bytes(image_bytes)
        except Exception as exc:
            logger.exception("Vision error: Failed to capture screen: %s", exc)
            return None
