from __future__ import annotations
import logging
import base64
from typing import Optional, Dict, Callable
from dataclasses import dataclass

from PySide6.QtCore import Qt, QObject, Signal
from PySide6.QtGui import QPixmap, QImage
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QApplication

from backend.vision.image_source import ImageSource
from backend.vision.screenshot_source import ScreenshotSource

logger = logging.getLogger("eggman")


@dataclass
class PendingAttachment:
    source_type: str
    image_base64: str


class FloatingPreviewWidget(QWidget):
    """Floating preview window that stays on top, doesn't steal focus, and has action buttons."""

    ask_clicked = Signal()
    remove_clicked = Signal()

    def __init__(self, image_bytes: bytes, parent=None) -> None:
        super().__init__(parent, Qt.Window | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.WindowDoesNotAcceptFocus)
        self.setAttribute(Qt.WA_TranslucentBackground, True)

        # Outer layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)

        # Dark Styled Container Widget
        container = QWidget(self)
        container.setStyleSheet("""
            QWidget {
                background-color: rgba(30, 30, 30, 0.94);
                border: 1px solid #555555;
                border-radius: 8px;
            }
        """)
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(10, 10, 10, 10)
        container_layout.setSpacing(6)

        # Header Label
        title = QLabel("📸 Screenshot Ready")
        title.setStyleSheet("font-weight: bold; color: #4CAF50; font-size: 11px; border: none; background: transparent;")
        title.setAlignment(Qt.AlignCenter)
        container_layout.addWidget(title)

        # Subtitle
        sub = QLabel("Attached to next message")
        sub.setStyleSheet("color: #bbbbbb; font-size: 9px; border: none; background: transparent;")
        sub.setAlignment(Qt.AlignCenter)
        container_layout.addWidget(sub)

        # Image Preview Label
        qimg = QImage.fromData(image_bytes)
        pixmap = QPixmap.fromImage(qimg)
        scaled_pixmap = pixmap.scaledToWidth(240, Qt.SmoothTransformation)

        img_label = QLabel()
        img_label.setPixmap(scaled_pixmap)
        img_label.setStyleSheet("border: 1px solid #444444; border-radius: 4px; background: transparent;")
        container_layout.addWidget(img_label)

        # Buttons layout
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(6)

        # "Ask About" Button
        self.ask_btn = QPushButton("Ask About")
        self.ask_btn.setStyleSheet("""
            QPushButton {
                background-color: #0078D4;
                color: white;
                font-weight: bold;
                font-size: 10px;
                padding: 4px 8px;
                border-radius: 3px;
                border: none;
            }
            QPushButton:hover {
                background-color: #106EBE;
            }
        """)
        self.ask_btn.clicked.connect(self.ask_clicked.emit)
        btn_layout.addWidget(self.ask_btn)

        # "Remove" Button
        self.remove_btn = QPushButton("Remove")
        self.remove_btn.setStyleSheet("""
            QPushButton {
                background-color: #D83B01;
                color: white;
                font-weight: bold;
                font-size: 10px;
                padding: 4px 8px;
                border-radius: 3px;
                border: none;
            }
            QPushButton:hover {
                background-color: #B33000;
            }
        """)
        self.remove_btn.clicked.connect(self.remove_clicked.emit)
        btn_layout.addWidget(self.remove_btn)

        container_layout.addLayout(btn_layout)
        layout.addWidget(container)
        self.adjustSize()

        # Place at top-right of screen
        screen = QApplication.primaryScreen()
        if screen:
            geom = screen.geometry()
            x = geom.width() - self.width() - 20
            y = 50
            self.move(x, y)


class VisionManager(QObject):
    """Entry point for all image/visual content capture and understanding."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._sources: Dict[str, ImageSource] = {}
        self._active_preview: Optional[FloatingPreviewWidget] = None
        self._pending_attachment: Optional[PendingAttachment] = None
        self._submit_callback: Optional[Callable[[str], None]] = None

        # Register screenshot source
        self.register_source("screenshot", ScreenshotSource())

        # Future ready placeholder slots (for future extension without refactoring)
        self.register_source("clipboard", None)
        self.register_source("file", None)
        self.register_source("camera", None)
        self.register_source("region", None)

    def register_source(self, name: str, source: Optional[ImageSource]) -> None:
        """Register a new image source."""
        self._sources[name] = source
        if source is not None:
            logger.info("VisionManager: Registered image source: %s", name)

    def set_submit_callback(self, callback: Callable[[], None]) -> None:
        """Register UI message submission callback."""
        self._submit_callback = callback

    def has_pending_attachment(self) -> bool:
        """Check if an attachment is currently pending."""
        return self._pending_attachment is not None

    def pop_pending_attachment(self) -> Optional[str]:
        """Use and retrieve the pending attachment, then clear it."""
        if self._pending_attachment:
            img_b64 = self._pending_attachment.image_base64
            self._pending_attachment = None
            logger.info("Attachment used")
            self.close_preview()
            return img_b64
        return None

    def clear_pending_attachment(self) -> None:
        """Manually remove the pending attachment."""
        if self._pending_attachment:
            self._pending_attachment = None
            logger.info("Attachment removed")
        self.close_preview()

    def add_pending_screenshot(self) -> Optional[str]:
        """Capture screen and register as a pending attachment."""
        source = self._sources.get("screenshot")
        if not source:
            logger.error("Vision error: ScreenshotSource is not registered")
            return None

        img_bytes = source.capture()
        if not img_bytes:
            return None

        img_b64 = base64.b64encode(img_bytes).decode("utf-8")
        self._pending_attachment = PendingAttachment(source_type="screenshot", image_base64=img_b64)
        logger.info("Attachment created")
        return img_b64

    def show_preview(self, img_b64: str) -> None:
        """Decode base64 and display floating preview with buttons."""
        try:
            img_bytes = base64.b64decode(img_b64)
            # Create and show preview widget on main thread
            self._active_preview = FloatingPreviewWidget(img_bytes)
            self._active_preview.ask_clicked.connect(self._on_ask_clicked)
            self._active_preview.remove_clicked.connect(self.clear_pending_attachment)
            self._active_preview.show()
            logger.info("Preview shown")
        except Exception as exc:
            logger.exception("Vision error: Failed to show preview: %s", exc)

    def close_preview(self) -> None:
        """Close the preview window if visible."""
        if self._active_preview:
            self._active_preview.close()
            self._active_preview = None

    def _on_ask_clicked(self) -> None:
        """Trigger AI query about the pending screenshot."""
        if self._submit_callback:
            self._submit_callback()
