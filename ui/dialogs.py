from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from backend.ai.ollama_provider import OllamaProvider
from core.config import ConfigManager
from core.settings import SettingsManager
from core.themes import Theme, ThemeManager
from ui.widgets import TitleBar


class SettingsDialog(QDialog):
    def __init__(self, settings: SettingsManager, config: ConfigManager, on_saved, parent=None):
        super().__init__(parent)
        self._settings = settings
        self._config = config
        self._on_saved = on_saved
        self.setWindowTitle("EggMan Settings")
        self.setMinimumWidth(320)
        self.setModal(True)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        ai_heading = QLabel("Ollama")
        ai_heading.setStyleSheet("font-weight: bold;")
        layout.addWidget(ai_heading)

        ai_form = QFormLayout()
        ai_form.setSpacing(8)

        self._ollama_url = QLineEdit()
        self._ollama_url.setText(str(self._config.get("ollama_base_url")))
        self._ollama_url.setPlaceholderText("http://localhost:11434")
        ai_form.addRow("Base URL:", self._ollama_url)

        self._ollama_model = QLineEdit()
        self._ollama_model.setText(str(self._config.get("ollama_model")))
        self._ollama_model.setPlaceholderText("qwen3:8b")
        ai_form.addRow("Model:", self._ollama_model)

        layout.addLayout(ai_form)

        test_row = QHBoxLayout()
        self._test_btn = QPushButton("Test Connection")
        self._test_btn.clicked.connect(self._test_connection)
        test_row.addWidget(self._test_btn)
        test_row.addStretch()
        layout.addLayout(test_row)

        self._test_status = QLabel("")
        self._test_status.setWordWrap(True)
        self._test_status.setStyleSheet("color: #666; font-size: 9px;")
        layout.addWidget(self._test_status)

        window_heading = QLabel("Window")
        window_heading.setStyleSheet("font-weight: bold;")
        layout.addWidget(window_heading)

        form = QFormLayout()
        form.setSpacing(8)

        self._aot_cb = QCheckBox()
        self._aot_cb.setChecked(bool(self._settings.get("always_on_top")))
        form.addRow("Always on top:", self._aot_cb)

        self._wake_word_cb = QCheckBox()
        self._wake_word_cb.setChecked(bool(self._config.get("wake_word_enabled", True)))
        form.addRow("Enable wake word:", self._wake_word_cb)

        self._w_spin = QSpinBox()
        self._w_spin.setRange(220, 600)
        self._w_spin.setValue(int(self._settings.get("win_w")))
        form.addRow("Window width:", self._w_spin)

        self._h_spin = QSpinBox()
        self._h_spin.setRange(300, 900)
        self._h_spin.setValue(int(self._settings.get("win_h")))
        form.addRow("Window height:", self._h_spin)

        layout.addLayout(form)

        note = QLabel("Window size applies on next launch.")
        note.setStyleSheet("color: #888; font-size: 9px;")
        layout.addWidget(note)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _test_connection(self):
        self._test_btn.setEnabled(False)
        self._test_status.setText("Testing connection...")
        try:
            provider = OllamaProvider(
                base_url=self._ollama_url.text().strip(),
                model_name=self._ollama_model.text().strip(),
            )
            result = provider.test_connection()
            if result.get("ok"):
                models = result.get("available_models") or []
                model_count = len(models)
                self._test_status.setText(
                    f"Connected — using {result.get('model')} ({result.get('elapsed_ms')} ms, {model_count} models available)."
                )
                self._test_status.setStyleSheet("color: #2a6; font-size: 9px;")
            else:
                self._test_status.setText(f"Failed — {result.get('error', 'Unknown error')}")
                self._test_status.setStyleSheet("color: #a33; font-size: 9px;")
        except Exception as exc:
            self._test_status.setText(f"Failed — {exc}")
            self._test_status.setStyleSheet("color: #a33; font-size: 9px;")
        finally:
            self._test_btn.setEnabled(True)

    def _save(self):
        self._config.set("provider", "ollama")
        self._config.set("ollama_base_url", self._ollama_url.text().strip() or OllamaProvider.DEFAULT_BASE_URL)
        self._config.set("ollama_model", self._ollama_model.text().strip() or OllamaProvider.DEFAULT_MODEL)
        self._config.set("wake_word_enabled", self._wake_word_cb.isChecked())
        self._config.save()

        self._settings.set("always_on_top", self._aot_cb.isChecked())
        self._settings.set("win_w", self._w_spin.value())
        self._settings.set("win_h", self._h_spin.value())
        self._settings.save()
        self._on_saved()
        self.accept()


class HelpWindow(QDialog):
    """Modern control center for EggMan containing system commands and about info."""

    clear_requested = Signal()
    export_requested = Signal()
    settings_requested = Signal()

    def __init__(self, settings: SettingsManager, config: ConfigManager, theme_mgr: ThemeManager, parent=None) -> None:
        super().__init__(parent)
        self._settings = settings
        self._config = config
        self._theme_mgr = theme_mgr

        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setAttribute(Qt.WA_TranslucentBackground)

        # Match dimensions to main window
        w = int(self._settings.get("win_w") or Theme.WIN_W)
        h = int(self._settings.get("win_h") or Theme.WIN_H)
        self.setFixedSize(w, h)

        if parent:
            pg = parent.geometry()
            cx = pg.x() + (pg.width() - w) // 2
            cy = pg.y() + (pg.height() - h) // 2
            self.move(cx, cy)

        self._build_ui()

    def _build_ui(self) -> None:
        base_layout = QVBoxLayout(self)
        base_layout.setContentsMargins(0, 0, 0, 0)

        self.container = QWidget(self)
        self.container.setObjectName("container")
        base_layout.addWidget(self.container)

        layout = QVBoxLayout(self.container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Reusable title bar configured for EGGMAN HELP
        self._title_bar = TitleBar(self)
        self._title_bar._title_label.setText("EGGMAN HELP")
        layout.addWidget(self._title_bar)

        content_widget = QWidget(self.container)
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(18, 16, 18, 16)
        content_layout.setSpacing(10)

        info_lbl = QLabel("/help opens this window instead of sending a chat message.")
        info_lbl.setWordWrap(True)
        info_lbl.setAlignment(Qt.AlignCenter)
        info_lbl.setFont(QFont("Segoe UI", 9))
        content_layout.addWidget(info_lbl)

        content_layout.addWidget(self._create_divider())

        # Control Panel buttons
        self.clear_btn = QPushButton("Clear Chat")
        self.export_btn = QPushButton("Export Chat")
        self.theme_btn = QPushButton()
        self.settings_btn = QPushButton("Settings")

        for btn in (self.clear_btn, self.export_btn, self.theme_btn, self.settings_btn):
            btn.setFixedHeight(36)
            btn.setCursor(Qt.PointingHandCursor)
            content_layout.addWidget(btn)

        self.clear_btn.clicked.connect(self.clear_requested.emit)
        self.export_btn.clicked.connect(self.export_requested.emit)
        self.theme_btn.clicked.connect(self._toggle_theme)
        self.settings_btn.clicked.connect(self.settings_requested.emit)

        # Feedback/success status message label
        self.status_lbl = QLabel("")
        self.status_lbl.setAlignment(Qt.AlignCenter)
        self.status_lbl.setFont(QFont("Segoe UI", 9, QFont.Bold))
        content_layout.addWidget(self.status_lbl)

        content_layout.addWidget(self._create_divider())

        # About info
        about_title = QLabel("About EggMan")
        about_title.setFont(QFont("Segoe UI", 11, QFont.Bold))
        content_layout.addWidget(about_title)

        about_desc = QLabel(
            "EggMan is a modular desktop AI companion designed to provide an intelligent and extensible desktop experience."
        )
        about_desc.setWordWrap(True)
        about_desc.setFont(QFont("Segoe UI", 9))
        content_layout.addWidget(about_desc)

        # Metadata grid
        self.meta_layout = QFormLayout()
        self.meta_layout.setSpacing(4)
        self.meta_layout.setContentsMargins(0, 4, 0, 0)

        self.version_lbl = QLabel()
        self.provider_lbl = QLabel()
        self.theme_lbl = QLabel()

        for lbl in (self.version_lbl, self.provider_lbl, self.theme_lbl):
            lbl.setFont(QFont("Segoe UI", 9))

        self.meta_layout.addRow("Version:", self.version_lbl)
        self.meta_layout.addRow("Current Provider:", self.provider_lbl)
        self.meta_layout.addRow("Current Theme:", self.theme_lbl)

        content_layout.addLayout(self.meta_layout)
        content_layout.addStretch()

        layout.addWidget(content_widget, stretch=1)

        self.apply_theme()
        self.update_info()

    def _create_divider(self) -> QFrame:
        d = QFrame()
        d.setFrameShape(QFrame.HLine)
        d.setFixedHeight(1)
        d.setObjectName("divider")
        return d

    def _toggle_theme(self) -> None:
        current = self._config.get("theme") or self._settings.get("theme") or "light"
        next_theme = "dark" if current == "light" else "light"
        self._settings.set("theme", next_theme)
        self._config.set("theme", next_theme)
        self._config.save()
        self._settings.save()
        self._theme_mgr.apply(next_theme)
        self.update_info()

    def update_info(self) -> None:
        theme_name = self._config.get("theme") or self._settings.get("theme") or "light"
        self.theme_btn.setText(f"Theme: {theme_name.capitalize()}")

        # Avoid circular dependencies
        from main import APP_VERSION
        provider_name = self._config.get("provider") or "ollama"

        self.version_lbl.setText(APP_VERSION)
        self.provider_lbl.setText(provider_name.capitalize())
        self.theme_lbl.setText(theme_name.capitalize())

    def show_status_message(self, message: str) -> None:
        self.status_lbl.setText(message)
        QTimer.singleShot(3000, lambda: self.status_lbl.setText(""))

    def apply_theme(self) -> None:
        if not hasattr(self, "container"):
            return

        self._title_bar.apply_theme()

        self.container.setStyleSheet(f"""
            QWidget#container {{
                background: {Theme.CREAM};
                border: 1.5px solid {Theme.BORDER};
                border-radius: {Theme.RADIUS}px;
            }}
        """)

        btn_ss = f"""
            QPushButton {{
                background: {Theme.BTN_BG}; color: {Theme.TEXT_DARK};
                border: 1px solid {Theme.BORDER}; border-radius: 8px;
                font-family: 'Segoe UI'; font-size: 13px; font-weight: 500;
            }}
            QPushButton:hover {{ background: {Theme.BTN_HOVER}; }}
            QPushButton:pressed {{ background: {Theme.BTN_PRESS}; }}
        """
        for btn in (self.clear_btn, self.export_btn, self.theme_btn, self.settings_btn):
            btn.setStyleSheet(btn_ss)

        text_dark_ss = f"color: {Theme.TEXT_DARK}; background: transparent; border: none;"
        text_mid_ss = f"color: {Theme.TEXT_MID}; background: transparent; border: none;"

        for label in self.findChildren(QLabel):
            if label.parent() == self._title_bar:
                continue
            if self.meta_layout.labelForField(label) is not None:
                label.setStyleSheet(text_mid_ss)
            else:
                label.setStyleSheet(text_dark_ss)

        self.status_lbl.setStyleSheet(f"color: {Theme.TEXT_MID}; background: transparent; border: none;")

        for divider in self.findChildren(QFrame, "divider"):
            divider.setStyleSheet(f"background: {Theme.BORDER}; border: none;")
