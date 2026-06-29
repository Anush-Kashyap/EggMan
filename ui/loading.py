from PySide6.QtCore import (
    Qt,
    QTimer,
    QPropertyAnimation,
    QEasingCurve,
    QSequentialAnimationGroup,
    QParallelAnimationGroup,
    Property,
    QObject,
    QRectF,
    QThread,
    Signal,
)
from PySide6.QtGui import QPainter, QFont, QColor
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QApplication

from core.config import ConfigManager
from core.settings import SettingsManager
from core.themes import Theme, ThemeManager


class EggWidget(QLabel):
    """Custom label that draws the egg emoji with rotation and bounce animations."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setText("🥚")
        self.setAlignment(Qt.AlignCenter)

        # Set a large, cute font size for the emoji
        font = QFont("Segoe UI", 64)
        self.setFont(font)

        self._y_offset = 0.0
        self._rotation = 0.0

    def get_y_offset(self) -> float:
        return self._y_offset

    def set_y_offset(self, val: float) -> None:
        self._y_offset = val
        self.update()

    def get_rotation(self) -> float:
        return self._rotation

    def set_rotation(self, val: float) -> None:
        self._rotation = val
        self.update()

    y_offset = Property(float, get_y_offset, set_y_offset)
    rotation = Property(float, get_rotation, set_rotation)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.TextAntialiasing)

        rect = self.rect()
        cx = rect.width() / 2.0
        cy = rect.height() / 2.0

        # Translate to the widget's center, offset by the bounce (y_offset)
        painter.translate(cx, cy + self._y_offset)
        # Apply the tilting rotation around center
        painter.rotate(self._rotation)

        painter.setFont(self.font())
        # Draw emoji centered at (0, 0)
        target_rect = QRectF(-100, -100, 200, 200)
        painter.drawText(target_rect, Qt.AlignCenter, "🥚")
        painter.end()


class LoadingScreen(QWidget):
    """The animated splash screen displayed during application startup."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)

        # Pre-load settings to determine theme and initial coordinates
        config = ConfigManager()
        settings = SettingsManager()
        theme_mgr = ThemeManager(on_theme_changed=self.apply_theme)
        theme_mgr.apply(config.get("theme") or settings.get("theme"))

        # Match dimensions to the main EggManWindow
        w = int(settings.get("win_w") or Theme.WIN_W)
        h = int(settings.get("win_h") or Theme.WIN_H)
        self.setFixedSize(w, h)

        # Position at the exact same location where EggManWindow will open
        saved_x = settings.get("win_x")
        saved_y = settings.get("win_y")
        if saved_x is not None and saved_y is not None:
            self.move(saved_x, saved_y)
        else:
            screen = QApplication.primaryScreen().availableGeometry()
            self.move(screen.right() - w - 40, screen.top() + 60)

        self._build_ui()

    def _build_ui(self) -> None:
        # Base layout for window translucency support
        base_layout = QVBoxLayout(self)
        base_layout.setContentsMargins(0, 0, 0, 0)

        # Container widget for rounded borders and backgrounds
        self.container = QWidget(self)
        self.container.setObjectName("container")
        base_layout.addWidget(self.container)

        container_layout = QVBoxLayout(self.container)
        container_layout.setContentsMargins(20, 40, 20, 40)
        container_layout.setSpacing(20)

        container_layout.addStretch(1)

        # Cute animated egg
        self.egg_widget = EggWidget(self.container)
        self.egg_widget.setFixedHeight(180)
        container_layout.addWidget(self.egg_widget)

        # Soft loading text below egg
        self.loading_label = QLabel("Loading", self.container)
        self.loading_label.setAlignment(Qt.AlignCenter)
        container_layout.addWidget(self.loading_label)

        container_layout.addStretch(1)

        self.apply_theme()
        self._start_animations()

    def apply_theme(self) -> None:
        if not hasattr(self, "container"):
            return
        self.container.setStyleSheet(f"""
            QWidget#container {{
                background: {Theme.CREAM};
                border: 1.5px solid {Theme.BORDER};
                border-radius: {Theme.RADIUS}px;
            }}
        """)
        self.loading_label.setStyleSheet(f"""
            QLabel {{
                color: {Theme.TEXT_MID};
                font-family: 'Segoe UI';
                font-size: 16px;
                font-weight: bold;
                background: transparent;
                border: none;
            }}
        """)

    def _start_animations(self) -> None:
        # 1. Gentle Bounce Animation (Up and Down cycle)
        self.bounce_up = QPropertyAnimation(self.egg_widget, b"y_offset")
        self.bounce_up.setDuration(750)
        self.bounce_up.setStartValue(0.0)
        self.bounce_up.setEndValue(-14.0)
        self.bounce_up.setEasingCurve(QEasingCurve.InOutSine)

        self.bounce_down = QPropertyAnimation(self.egg_widget, b"y_offset")
        self.bounce_down.setDuration(750)
        self.bounce_down.setStartValue(-14.0)
        self.bounce_down.setEndValue(0.0)
        self.bounce_down.setEasingCurve(QEasingCurve.InOutSine)

        self.bounce_group = QSequentialAnimationGroup()
        self.bounce_group.addAnimation(self.bounce_up)
        self.bounce_group.addAnimation(self.bounce_down)
        self.bounce_group.setLoopCount(-1)

        # 2. Tilt Animation (Tilt left -> center -> tilt right -> center)
        self.tilt_left = QPropertyAnimation(self.egg_widget, b"rotation")
        self.tilt_left.setDuration(950)
        self.tilt_left.setStartValue(0.0)
        self.tilt_left.setEndValue(-8.0)
        self.tilt_left.setEasingCurve(QEasingCurve.InOutSine)

        self.tilt_center1 = QPropertyAnimation(self.egg_widget, b"rotation")
        self.tilt_center1.setDuration(950)
        self.tilt_center1.setStartValue(-8.0)
        self.tilt_center1.setEndValue(0.0)
        self.tilt_center1.setEasingCurve(QEasingCurve.InOutSine)

        self.tilt_right = QPropertyAnimation(self.egg_widget, b"rotation")
        self.tilt_right.setDuration(950)
        self.tilt_right.setStartValue(0.0)
        self.tilt_right.setEndValue(8.0)
        self.tilt_right.setEasingCurve(QEasingCurve.InOutSine)

        self.tilt_center2 = QPropertyAnimation(self.egg_widget, b"rotation")
        self.tilt_center2.setDuration(950)
        self.tilt_center2.setStartValue(8.0)
        self.tilt_center2.setEndValue(0.0)
        self.tilt_center2.setEasingCurve(QEasingCurve.InOutSine)

        self.tilt_group = QSequentialAnimationGroup()
        self.tilt_group.addAnimation(self.tilt_left)
        self.tilt_group.addAnimation(self.tilt_center1)
        self.tilt_group.addAnimation(self.tilt_right)
        self.tilt_group.addAnimation(self.tilt_center2)
        self.tilt_group.setLoopCount(-1)

        # Parallel group to run them both
        self.anim_group = QParallelAnimationGroup()
        self.anim_group.addAnimation(self.bounce_group)
        self.anim_group.addAnimation(self.tilt_group)
        self.anim_group.start()

        # 3. Loading text cycle dots timer
        self.loading_timer = QTimer(self)
        self.loading_timer.timeout.connect(self._update_loading_text)
        self.loading_timer.start(500)

    def _update_loading_text(self) -> None:
        dots = self.loading_label.text().count(".")
        next_dots = (dots + 1) % 4
        self.loading_label.setText("Loading" + "." * next_dots)


class AppInitWorker(QThread):
    """Worker thread that constructs AppContainer and runs startup tasks without blocking the UI thread."""

    finished = Signal(object)

    def run(self) -> None:
        try:
            from app.container import AppContainer
            container = AppContainer()

            # Move any instantiated QObjects (like VisionManager) to the main thread
            # so they can receive signals/slots and create widgets safely.
            if hasattr(container, "vision_manager") and isinstance(container.vision_manager, QObject):
                container.vision_manager.moveToThread(QApplication.instance().thread())

            self.finished.emit(container)
        except Exception as e:
            self.finished.emit(e)
