from PySide6.QtCore import Qt, QPoint, QTimer, QPropertyAnimation
from PySide6.QtGui import QFont, QPixmap, QPainter, QColor, QBrush, QPen, QPolygon
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QApplication, QGraphicsOpacityEffect

from core.themes import Theme
from ui.widgets import InputBar


class TypingIndicator(QWidget):
    """Instagram-style sequence bouncing three dots typing indicator."""

    def __init__(self, parent: QWidget = None) -> None:
        super().__init__(parent)
        self.setFixedSize(60, 20)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.update)
        self._frame = 0

    def start(self) -> None:
        self._frame = 0
        self._timer.start(150)

    def stop(self) -> None:
        self._timer.stop()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        y_base = 10
        dot_radius = 3.5

        # Colors corresponding to the active theme text colors
        active_color = QColor(Theme.TEXT_DARK or "#000000")
        inactive_color = QColor(Theme.TEXT_MID or "#888888")

        for i in range(3):
            y = y_base
            if self._frame % 3 == i:
                y -= 4  # Bounce up by 4 pixels
                color = active_color
            else:
                color = inactive_color

            painter.setBrush(QBrush(color))
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(15 + i * 15 - dot_radius, y - dot_radius, dot_radius * 2, dot_radius * 2)

        self._frame += 1


class SpeechBubble(QWidget):
    """Floating speech bubble above EggMan companion displaying replies or typing animations."""

    def __init__(self, companion: QWidget) -> None:
        super().__init__()
        self.companion = companion

        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool | Qt.WindowDoesNotAcceptFocus)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)

        self._build_ui()

        self._fade_anim = None
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.fade_out)

    def mousePressEvent(self, event) -> None:
        self.fade_out()
        super().mousePressEvent(event)

    def _build_ui(self) -> None:
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(12, 12, 12, 22)  # Extra bottom margin for pointing tip
        self.layout.setSpacing(4)

        # Message text label
        self.label = QLabel(self)
        self.label.setWordWrap(True)
        self.label.setFont(Theme.FONT_CHAT)
        self.layout.addWidget(self.label)

        # Typing indicator widget
        self.typing_indicator = TypingIndicator(self)
        self.layout.addWidget(self.typing_indicator, alignment=Qt.AlignCenter)
        self.typing_indicator.hide()

        self.apply_theme()

    def apply_theme(self) -> None:
        self.label.setStyleSheet(f"color: {Theme.TEXT_DARK};")
        self.update()  # Redraw paint event using active theme background/borders

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Use active theme chat bubble background and border colors
        bg_color = QColor(Theme.BUBBLE_EGG or "#EDE7D9")
        border_color = QColor(Theme.BORDER or "#C8BFA8")

        rect = self.rect()
        bubble_rect = rect.adjusted(1, 1, -1, -15)  # Leave bottom space for pointer tip

        painter.setBrush(QBrush(bg_color))
        painter.setPen(QPen(border_color, 1.5))
        painter.drawRoundedRect(bubble_rect, 12, 12)

        # Draw pointing triangle at the bottom center pointing down towards mascot
        x = rect.width() // 2
        y_top = rect.height() - 15
        y_tip = rect.height() - 2

        triangle = QPolygon([
            QPoint(x - 8, y_top),
            QPoint(x + 8, y_top),
            QPoint(x, y_tip)
        ])
        painter.drawPolygon(triangle)

        # Remove the separating line between the bubble and pointer
        painter.setPen(QPen(bg_color, 1.5))
        painter.drawLine(QPoint(x - 7, y_top), QPoint(x + 7, y_top))

    def show_text(self, text: str) -> None:
        self._timer.stop()
        self.typing_indicator.stop()
        self.typing_indicator.hide()
        self.label.show()

        self.label.setText(text)
        self.setFixedWidth(260)
        self.adjustSize()

        self._position_bubble()

        self.fade_in()
        self._timer.start(30000)  # Fade out after 30 seconds

    def show_typing_indicator(self) -> None:
        self._timer.stop()
        self.label.hide()
        self.typing_indicator.show()
        self.typing_indicator.start()

        self.setFixedSize(90, 52)
        self._position_bubble()

        self.fade_in()

    def _position_bubble(self) -> None:
        cx = self.companion.x() + (self.companion.width() - self.width()) // 2
        cy = self.companion.y() - self.height() - 8
        self.move(cx, cy)

    def fade_in(self) -> None:
        if not hasattr(self, "_opacity_effect"):
            self._opacity_effect = QGraphicsOpacityEffect(self)
            self.setGraphicsEffect(self._opacity_effect)

        self.show()
        self._fade_anim = QPropertyAnimation(self._opacity_effect, b"opacity")
        self._fade_anim.setDuration(250)
        self._fade_anim.setStartValue(0.0)
        self._fade_anim.setEndValue(1.0)
        self._fade_anim.start()

    def fade_out(self) -> None:
        if not hasattr(self, "_opacity_effect"):
            return

        self._fade_anim = QPropertyAnimation(self._opacity_effect, b"opacity")
        self._fade_anim.setDuration(250)
        self._fade_anim.setStartValue(1.0)
        self._fade_anim.setEndValue(0.0)
        self._fade_anim.finished.connect(self._on_fade_out_finished)
        self._fade_anim.start()

    def _on_fade_out_finished(self) -> None:
        self.hide()
        self.typing_indicator.stop()


class DesktopCompanion(QWidget):
    """The desktop pet mascot of EggMan that sits on the desktop and acts as the primary interaction center."""

    def __init__(self, chat_window: QWidget) -> None:
        super().__init__()
        self.chat_window = chat_window
        self._drag_pos = QPoint()
        self._is_thinking = False

        # Frameless, always on top, and hides from taskbar (Qt.Tool)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground, True)

        self._build_ui()

        # Hover timeout buffer to prevent controls flickering
        self._hover_timer = QTimer(self)
        self._hover_timer.setSingleShot(True)
        self._hover_timer.timeout.connect(self.fade_out_inputs)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 1. Mascot image label (15% smaller than 325x325 -> 275x275)
        self.egg_label = QLabel(self)
        self.egg_label.setFixedSize(275, 275)
        self.egg_label.setScaledContents(True)
        layout.addWidget(self.egg_label, alignment=Qt.AlignCenter)

        # Set fixed size for the companion window wrapping the avatar label (275x275)
        self.setFixedSize(275, 275)

        # Position at bottom-right corner of screen just above taskbar
        screen = QApplication.primaryScreen().availableGeometry()
        margin_x = 15
        margin_y = 5
        x = screen.right() - self.width() - margin_x
        y = screen.bottom() - self.height() - margin_y
        self.move(x, y)

        # 2. Layout inside the egg_label to overlay buttons and input controls
        egg_layout = QVBoxLayout(self.egg_label)
        # Top margin of 40px for chat/close buttons, bottom margin of 25px for input bar
        egg_layout.setContentsMargins(10, 40, 10, 25)
        egg_layout.setSpacing(0)

        # Chat and exit buttons layout (floating near the mascot's head)
        btn_layout = QHBoxLayout()
        btn_layout.setContentsMargins(0, 0, 0, 0)
        btn_layout.setSpacing(15)
        btn_layout.addStretch(1)

        self.chat_btn = QPushButton("💬", self.egg_label)
        self.close_btn = QPushButton("❌", self.egg_label)

        for btn in (self.chat_btn, self.close_btn):
            btn.setFixedSize(28, 28)
            btn.setFont(QFont("Segoe UI", 12))
            btn.setCursor(Qt.PointingHandCursor)
            btn_layout.addWidget(btn)

        btn_layout.addStretch(1)
        egg_layout.addLayout(btn_layout)

        # Push the input bar to the bottom of the layout (1cm above bottom edge)
        egg_layout.addStretch(1)

        # Input bar directly overlayed inside self.egg_label
        self.input_bar = InputBar(self.egg_label)
        self.input_bar.setFixedWidth(260)
        egg_layout.addWidget(self.input_bar, alignment=Qt.AlignCenter)

        # Set input bar opacity effects for hover fade transitions
        self.input_opacity = QGraphicsOpacityEffect(self.input_bar)
        self.input_bar.setGraphicsEffect(self.input_opacity)
        self.input_opacity.setOpacity(0.0)  # Hidden by default
        self.input_bar.setEnabled(False)    # Disabled by default

        # State image assets paths mapping
        from core.paths import ASSETS_DIR
        self._state_images = {
            "inactive": str(ASSETS_DIR / "inactive.png"),
            "active": str(ASSETS_DIR / "active.png"),
            "thinking": str(ASSETS_DIR / "thinking.png"),
        }

        # Set initial visual state
        self.set_egg_state("inactive")

        # Connect floating buttons
        self.chat_btn.clicked.connect(self._on_chat_btn_clicked)
        self.close_btn.clicked.connect(self._on_close_btn_clicked)

        # Connect text changes to control active/inactive states
        self.input_bar.entry.textChanged.connect(self._on_input_text_changed)

        # Instantiate floating speech bubble above EggMan
        self.speech_bubble = SpeechBubble(self)

        self.apply_theme()

    def set_egg_state(self, state: str) -> None:
        path = self._state_images.get(state)
        if path:
            pixmap = QPixmap(path)
            self.egg_label.setPixmap(pixmap)

    def display_reply(self, text: str) -> None:
        self.speech_bubble.show_text(text)

    def _on_generation_started(self) -> None:
        self._is_thinking = True
        self.set_egg_state("thinking")
        self.speech_bubble.show_typing_indicator()

    def _on_generation_finished(self) -> None:
        self._is_thinking = False
        if self.input_bar.entry.text().strip():
            self.set_egg_state("active")
        else:
            self.set_egg_state("inactive")

    def _on_input_text_changed(self, text: str) -> None:
        if self._is_thinking:
            return
        if text.strip():
            self.set_egg_state("active")
        else:
            self.set_egg_state("inactive")

    def _on_chat_btn_clicked(self) -> None:
        if self.chat_window.isVisible():
            self.chat_window.raise_()
            self.chat_window.activateWindow()
        else:
            settings = self.chat_window._settings
            saved_x = settings.get("win_x")
            saved_y = settings.get("win_y")
            if saved_x is None or saved_y is None:
                w = self.chat_window.width()
                h = self.chat_window.height()
                x = self.x() - w - 15
                y = self.y() + self.height() - h
                self.chat_window.move(x, y)

            if hasattr(self.chat_window, "fade_in"):
                self.chat_window.fade_in()
            else:
                self.chat_window.show()

    def _on_close_btn_clicked(self) -> None:
        self.speech_bubble.close()
        self.chat_window._is_shutting_down = True
        self.chat_window.close()
        self.close()
        QApplication.quit()

    def apply_theme(self) -> None:
        self.chat_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {Theme.TEXT_DARK};
                border: none;
                border-radius: 14px;
            }}
            QPushButton:hover {{ background: {Theme.BTN_BG}; }}
            QPushButton:pressed {{ background: {Theme.BTN_PRESS}; }}
        """)

        self.close_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {Theme.TEXT_MID};
                border: none;
                border-radius: 14px;
            }}
            QPushButton:hover {{
                background: {Theme.CTRL_HOVER_CLS};
                color: {Theme.TEXT_DARK};
            }}
            QPushButton:pressed {{ background: {Theme.CTRL_PRESS_CLS}; }}
        """)

        self.input_bar.apply_theme()
        if hasattr(self, "speech_bubble"):
            self.speech_bubble.apply_theme()

    # Hover Fade in / Fade out triggers
    def enterEvent(self, event) -> None:
        self._hover_timer.stop()
        self.fade_in_inputs()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._hover_timer.start(400)  # 400ms buffer delay
        super().leaveEvent(event)

    def fade_in_inputs(self) -> None:
        if self.input_bar.isEnabled():
            return
        self.input_bar.setEnabled(True)
        self._input_fade = QPropertyAnimation(self.input_opacity, b"opacity")
        self._input_fade.setDuration(200)
        self._input_fade.setStartValue(self.input_opacity.opacity())
        self._input_fade.setEndValue(1.0)
        self._input_fade.start()

    def fade_out_inputs(self) -> None:
        # Prevent fading out if user is active in entry focus
        if self.input_bar.entry.hasFocus():
            return
        self.input_bar.setEnabled(False)
        self._input_fade = QPropertyAnimation(self.input_opacity, b"opacity")
        self._input_fade.setDuration(200)
        self._input_fade.setStartValue(self.input_opacity.opacity())
        self._input_fade.setEndValue(0.0)
        self._input_fade.start()

    # Window Position Synchronization for Speech Bubble
    def moveEvent(self, event) -> None:
        if hasattr(self, "speech_bubble") and self.speech_bubble.isVisible():
            self.speech_bubble._position_bubble()
        super().moveEvent(event)

    # Draggable Mascot Window
    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self._drag_pos = (
                event.globalPosition().toPoint()
                - self.frameGeometry().topLeft()
            )

    def mouseMoveEvent(self, event) -> None:
        if event.buttons() == Qt.LeftButton and not self._drag_pos.isNull():
            self.move(event.globalPosition().toPoint() - self._drag_pos)
