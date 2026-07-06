from __future__ import annotations

import logging
from typing import Callable, Optional

from PySide6.QtCore import (
    Qt, QPropertyAnimation, QEasingCurve, QPoint, QRect, QSize, QTimer,
)
from PySide6.QtGui import (
    QFont, QPixmap, QColor, QPainter, QPainterPath, QCursor, QBrush, QPen,
)
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QPushButton, QLabel,
    QGraphicsOpacityEffect, QSizePolicy, QApplication,
)

from core.themes import Theme

logger = logging.getLogger("eggman")


# ---------------------------------------------------------------------------
# PersonaCard  (individual card inside the popup panel)
# ---------------------------------------------------------------------------

class PersonaCard(QPushButton):
    """Single persona card with circular avatar and name label."""

    def __init__(
        self,
        key: str,
        display_name: str,
        emoji: str,
        avatar_path: Optional[str],
        parent: QWidget = None,
    ) -> None:
        super().__init__(parent)
        self.persona_key = key
        self._display_name = display_name
        self._emoji = emoji
        self._avatar_path = avatar_path
        self._is_active = False

        self.setCursor(Qt.PointingHandCursor)
        self.setFixedSize(72, 88)
        self.setFlat(True)
        self.setCheckable(False)

        inner = QVBoxLayout(self)
        inner.setContentsMargins(4, 6, 4, 6)
        inner.setSpacing(4)

        self._avatar_label = QLabel(self)
        self._avatar_label.setAlignment(Qt.AlignCenter)
        self._avatar_label.setFixedSize(44, 44)
        self._load_avatar()
        inner.addWidget(self._avatar_label, alignment=Qt.AlignCenter)

        self._name_label = QLabel(display_name, self)
        self._name_label.setAlignment(Qt.AlignCenter)
        self._name_label.setFont(QFont("Segoe UI", 7, QFont.Medium))
        self._name_label.setWordWrap(True)
        inner.addWidget(self._name_label, alignment=Qt.AlignCenter)

        # Independent opacity effect per card
        self._opacity_effect = QGraphicsOpacityEffect(self)
        self._opacity_effect.setOpacity(0.80)
        self.setGraphicsEffect(self._opacity_effect)

        self._apply_style(active=False)

    def _load_avatar(self) -> None:
        if self._avatar_path:
            pix = QPixmap(self._avatar_path)
            if not pix.isNull():
                pix = self._make_circular(pix, 44)
                self._avatar_label.setPixmap(pix)
                self._avatar_label.setText("")
                return
        self._avatar_label.setText(self._emoji)
        self._avatar_label.setFont(QFont("Segoe UI Emoji", 22))

    def _make_circular(self, source: QPixmap, size: int) -> QPixmap:
        scaled = source.scaled(
            size, size, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation
        )
        result = QPixmap(size, size)
        result.fill(Qt.transparent)
        painter = QPainter(result)
        painter.setRenderHint(QPainter.Antialiasing)
        path = QPainterPath()
        path.addEllipse(0, 0, size, size)
        painter.setClipPath(path)
        x_off = (scaled.width() - size) // 2
        y_off = (scaled.height() - size) // 2
        painter.drawPixmap(-x_off, -y_off, scaled)
        painter.end()
        return result

    def set_active(self, active: bool) -> None:
        self._is_active = active
        self._apply_style(active)
        self._opacity_effect.setOpacity(1.0 if active else 0.75)

    def _apply_style(self, active: bool) -> None:
        accent = getattr(Theme, "ACCENT", "#E8A87C")
        bg = "rgba(255,255,255,0.22)" if active else "transparent"
        border = f"2px solid {accent}" if active else "1.5px solid transparent"

        self.setStyleSheet(f"""
            QPushButton {{
                background: {bg};
                border: {border};
                border-radius: 10px;
            }}
            QPushButton:hover {{
                background: rgba(255,255,255,0.16);
                border: 1.5px solid rgba(200,180,160,0.60);
            }}
            QPushButton:pressed {{
                background: rgba(255,255,255,0.26);
            }}
        """)
        self._name_label.setStyleSheet(
            f"color: {Theme.TEXT_DARK}; background: transparent;"
        )


# ---------------------------------------------------------------------------
# PersonaPopupPanel  (floating panel that appears beside the menu button)
# ---------------------------------------------------------------------------

class PersonaPopupPanel(QWidget):
    """Floating panel holding the three persona cards.

    Positioned to the LEFT of the trigger button with a staggered slide-in
    animation. Auto-dismissed when the user clicks outside.

    Key design choices:
      - WindowStaysOnTopHint so it is always on top of the chat window
      - Manual paintEvent instead of stylesheet background (required when
        WA_TranslucentBackground is set on a top-level window on Windows)
      - Card positions read AFTER show() + layout pass to avoid (0,0) coords
    """

    CARD_SPACING = 6
    PANEL_PADDING = 8

    def __init__(
        self,
        on_persona_selected: Callable[[str], None],
    ) -> None:
        # Top-level, no taskbar entry, always on top, no focus stealing
        super().__init__(
            None,
            Qt.Tool
            | Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.WindowDoesNotAcceptFocus,
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)

        self._on_selected = on_persona_selected
        self._cards: dict[str, PersonaCard] = {}
        self._active_key: str = "normal"
        self._is_open: bool = False
        # Keep animation references alive so they don't get GC'd mid-flight
        self._active_anims: list = []

        self._build()

    # ------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------

    def _build(self) -> None:
        from backend.personas.persona_manager import PersonaManager
        manager = PersonaManager.get_instance()

        layout = QHBoxLayout(self)
        layout.setContentsMargins(
            self.PANEL_PADDING, self.PANEL_PADDING,
            self.PANEL_PADDING, self.PANEL_PADDING,
        )
        layout.setSpacing(self.CARD_SPACING)

        for persona in manager.available_personas():
            card = PersonaCard(
                key=persona.key,
                display_name=persona.display_name,
                emoji=persona.emoji,
                avatar_path=persona.avatar_path,
                parent=self,
            )
            card.clicked.connect(
                lambda checked=False, k=persona.key: self._on_card_clicked(k)
            )
            self._cards[persona.key] = card
            layout.addWidget(card)

        self.adjustSize()

    # ------------------------------------------------------------------
    # Background painting (required for translucent top-level on Windows)
    # ------------------------------------------------------------------

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        cream = QColor(getattr(Theme, "CREAM", "#FBF6EE"))
        border_color = QColor(getattr(Theme, "BORDER", "#C8BFA8"))

        rect = self.rect().adjusted(1, 1, -1, -1)
        painter.setBrush(QBrush(cream))
        painter.setPen(QPen(border_color, 1.5))
        painter.drawRoundedRect(rect, 12, 12)

    # ------------------------------------------------------------------
    # Active state
    # ------------------------------------------------------------------

    def set_active_persona(self, key: str) -> None:
        self._active_key = key
        for k, card in self._cards.items():
            card.set_active(k == key)

    def _on_card_clicked(self, key: str) -> None:
        self._active_key = key
        for k, card in self._cards.items():
            card.set_active(k == key)
        self._on_selected(key)
        QTimer.singleShot(200, self.close_panel)

    # ------------------------------------------------------------------
    # Open / Close
    # ------------------------------------------------------------------

    def open_panel(self, trigger_btn: QWidget) -> None:
        """Position and animate-open the panel to the left of trigger_btn."""
        if self._is_open:
            self.close_panel()
            return

        self._is_open = True
        self._active_anims.clear()

        # Position BEFORE showing so size is correct
        self._position_beside(trigger_btn)

        # Show at full opacity immediately — animation handles the entrance
        self.setWindowOpacity(0.0)
        self.show()
        self.raise_()

        # Let Qt finish the layout pass, then animate
        QTimer.singleShot(0, self._run_open_animation)

        # Global event filter to catch outside clicks
        QApplication.instance().installEventFilter(self)

    def _run_open_animation(self) -> None:
        """Runs after Qt layout pass so card positions are correct."""
        # --- Fade in the whole window ---
        fade = QPropertyAnimation(self, b"windowOpacity")
        fade.setDuration(200)
        fade.setStartValue(0.0)
        fade.setEndValue(1.0)
        fade.setEasingCurve(QEasingCurve.OutCubic)
        fade.start(QPropertyAnimation.DeleteWhenStopped)
        self._active_anims.append(fade)

        # --- Staggered slide-in for each card ---
        cards = list(self._cards.values())
        for i, card in enumerate(cards):
            natural_pos = card.pos()  # valid now after layout pass

            # Reset card opacity first
            card._opacity_effect.setOpacity(0.0)

            start_pos = QPoint(natural_pos.x() + 50, natural_pos.y())

            def _launch(c=card, sp=start_pos, np=natural_pos) -> None:
                # Slide
                pos_anim = QPropertyAnimation(c, b"pos")
                pos_anim.setStartValue(sp)
                pos_anim.setEndValue(np)
                pos_anim.setDuration(280)
                pos_anim.setEasingCurve(QEasingCurve.OutBack)
                pos_anim.start(QPropertyAnimation.DeleteWhenStopped)
                self._active_anims.append(pos_anim)

                # Fade in card
                op_anim = QPropertyAnimation(c._opacity_effect, b"opacity")
                op_anim.setStartValue(0.0)
                op_anim.setEndValue(1.0 if c._is_active else 0.75)
                op_anim.setDuration(200)
                op_anim.setEasingCurve(QEasingCurve.OutCubic)
                op_anim.start(QPropertyAnimation.DeleteWhenStopped)
                self._active_anims.append(op_anim)

            # Stagger: each card starts 60ms later
            QTimer.singleShot(i * 60, _launch)

    def close_panel(self) -> None:
        if not self._is_open:
            return
        self._is_open = False
        QApplication.instance().removeEventFilter(self)
        self._active_anims.clear()

        fade = QPropertyAnimation(self, b"windowOpacity")
        fade.setDuration(160)
        fade.setStartValue(self.windowOpacity())
        fade.setEndValue(0.0)
        fade.setEasingCurve(QEasingCurve.InCubic)
        fade.finished.connect(self.hide)
        fade.start(QPropertyAnimation.DeleteWhenStopped)
        self._active_anims.append(fade)

    def _position_beside(self, trigger_btn: QWidget) -> None:
        """Position the panel to the LEFT of the trigger button."""
        self.adjustSize()
        btn_global = trigger_btn.mapToGlobal(QPoint(0, 0))
        x = btn_global.x() - self.width() - 8
        y = btn_global.y() + (trigger_btn.height() - self.height()) // 2
        # Keep on screen
        screen = QApplication.primaryScreen().availableGeometry()
        x = max(screen.left() + 4, min(x, screen.right() - self.width() - 4))
        y = max(screen.top() + 4, min(y, screen.bottom() - self.height() - 4))
        self.move(x, y)

    # ------------------------------------------------------------------
    # Dismiss on outside click
    # ------------------------------------------------------------------

    def eventFilter(self, obj, event) -> bool:
        from PySide6.QtCore import QEvent
        if event.type() == QEvent.MouseButtonPress and self._is_open:
            click_pos = QCursor.pos()
            panel_rect = QRect(self.mapToGlobal(QPoint(0, 0)), self.size())
            if not panel_rect.contains(click_pos):
                self.close_panel()
        return False

    def apply_theme(self) -> None:
        self.update()  # Repaint background via paintEvent
        for card in self._cards.values():
            card._apply_style(card._is_active)


# ---------------------------------------------------------------------------
# PersonaMenuButton  (the 🎭 button in the title bar)
# ---------------------------------------------------------------------------

class PersonaMenuButton(QPushButton):
    """Small button in the title bar that opens/closes the persona popup panel."""

    def __init__(
        self,
        on_persona_selected: Callable[[str], None],
        parent: QWidget = None,
    ) -> None:
        super().__init__("🎭", parent)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedSize(26, 26)
        self.setFont(QFont("Segoe UI Emoji", 12))
        self.setToolTip("Switch Persona")

        # Panel is top-level (parent=None) so it can float above the window
        self._panel = PersonaPopupPanel(on_persona_selected=on_persona_selected)
        self.clicked.connect(self._panel.open_panel.__get__(self._panel))
        # Re-bind so it receives the button as the trigger argument
        self.clicked.disconnect()
        self.clicked.connect(self._toggle)
        self._apply_style()

    def _toggle(self) -> None:
        self._panel.open_panel(self)

    def set_active_persona(self, key: str) -> None:
        self._panel.set_active_persona(key)

    def apply_theme(self) -> None:
        self._apply_style()
        self._panel.apply_theme()

    def _apply_style(self) -> None:
        self.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                border-radius: 6px;
            }
            QPushButton:hover {
                background: rgba(0,0,0,0.08);
            }
            QPushButton:pressed {
                background: rgba(0,0,0,0.14);
            }
        """)
