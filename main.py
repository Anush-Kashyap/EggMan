import os
import sys
from datetime import datetime

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QApplication, QFrame, QVBoxLayout, QWidget

from core.commands import CommandHandler, CommandResult
from core.config import ConfigManager
from core.conversation import ConversationEngine
from core.logger import AppLogger
from core.paths import EXPORTS_DIR as EXPORTS_FOLDER, SCREENSHOTS_DIR as SCREENSHOTS_FOLDER
from core.providers import LocalProvider
from core.settings import SettingsManager
from core.themes import Theme, ThemeManager
from ui.dialogs import SettingsDialog
from ui.widgets import ChatDisplay, InputBar, TitleBar


class EggManWindow(QWidget):
    TYPING_DELAY_MS = 1000
    SCREENSHOT_DIR = SCREENSHOTS_FOLDER
    EXPORTS_DIR = EXPORTS_FOLDER

    def __init__(self):
        super().__init__()
        self.setWindowTitle("EggMan")

        self._config = ConfigManager()
        self._logger = AppLogger()
        self._settings = SettingsManager()
        self._cmd = CommandHandler()
        self._provider = self._build_provider()
        self._conv = ConversationEngine(provider=self._provider)
        self._theme_mgr = ThemeManager(on_theme_changed=self.apply_theme)

        self._pending_reply: str = ""
        self._pending_ts: str = ""
        self._typing_delay_ms = int(self._config.get("typing_delay", self.TYPING_DELAY_MS))

        self._theme_mgr.apply(self._config.get("theme") or self._settings.get("theme"))
        self._config.set("theme", self._config.get("theme") or self._settings.get("theme"))
        self._config.set("always_on_top", bool(self._settings.get("always_on_top")))
        self._config.set("typing_delay", self._typing_delay_ms)
        self._config.save()
        self._logger.info("Application startup")

        self._apply_window_flags()
        self.setAttribute(Qt.WA_TranslucentBackground)

        w = int(self._settings.get("win_w"))
        h = int(self._settings.get("win_h"))
        self.setFixedSize(w, h)

        saved_x = self._settings.get("win_x")
        saved_y = self._settings.get("win_y")
        if saved_x is not None and saved_y is not None:
            self.move(saved_x, saved_y)
        else:
            screen = QApplication.primaryScreen().availableGeometry()
            self.move(screen.right() - w - 40, screen.top() + 60)

        self._build_ui()
        self._connect_signals()
        self._post_welcome()

    def _build_provider(self):
        provider_name = str(self._config.get("provider", "local")).strip().lower()
        if provider_name != "local":
            return LocalProvider()
        return LocalProvider()

    def _apply_window_flags(self):
        flags = Qt.FramelessWindowHint
        always_on_top = bool(self._config.get("always_on_top", self._settings.get("always_on_top")))
        if always_on_top:
            flags |= Qt.WindowStaysOnTopHint
        self._config.set("always_on_top", always_on_top)
        self._settings.set("always_on_top", always_on_top)
        self.setWindowFlags(flags)

    def _build_ui(self):
        self._container = QWidget(self)
        self._container.setObjectName("container")
        self._container.setGeometry(
            0,
            0,
            int(self._settings.get("win_w")),
            int(self._settings.get("win_h")),
        )
        self._title_bar = TitleBar(self)
        self._chat = ChatDisplay()
        self._input_bar = InputBar()

        root_layout = QVBoxLayout(self._container)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)
        root_layout.addWidget(self._title_bar)
        root_layout.addWidget(self._make_divider())
        root_layout.addWidget(self._chat, stretch=1)
        root_layout.addWidget(self._input_bar)

        self._update_container_style()

    def _make_divider(self) -> QFrame:
        d = QFrame()
        d.setFrameShape(QFrame.HLine)
        d.setFixedHeight(1)
        d.setStyleSheet(f"background: {Theme.BORDER}; border: none;")
        return d

    def _update_container_style(self):
        if not hasattr(self, "_container"):
            return
        self._container.setStyleSheet(f"""
            QWidget#container {{
                background: {Theme.CREAM};
                border: 1.5px solid {Theme.BORDER};
                border-radius: {Theme.RADIUS}px;
            }}
        """)

    def _connect_signals(self):
        self._input_bar.send_btn.clicked.connect(self._on_send)
        self._input_bar.entry.returnPressed.connect(self._on_send)
        self._input_bar.screenshot_btn.clicked.connect(self._take_screenshot)

    def apply_theme(self):
        self._update_container_style()
        if not hasattr(self, "_title_bar"):
            return
        self._title_bar.apply_theme()
        self._chat.apply_theme()
        self._input_bar.apply_theme()

    def _post_welcome(self):
        self._chat.append_message("egg", "Hello! I'm EggMan 🥚", self._now())

    def _on_send(self):
        text = self._input_bar.entry.text().strip()
        if not text:
            return
        self._input_bar.entry.clear()

        self._chat.append_message("user", text, self._now())

        try:
            result = self._cmd.handle(text)
            if result.handled:
                self._handle_command(result)
                return

            self._pending_reply = self._conv.get_reply(text)
            self._pending_ts = self._now()
            self._start_typing()
        except Exception as exc:
            self._logger.error(f"Message handling failed: {exc}")
            self._chat.append_message("egg", "Something went wrong. Please try again.", self._now())

    def _handle_command(self, result: CommandResult):
        if result.action == "clear":
            self._chat.clear_messages()

        elif result.action == "export":
            export_msg = self._export_chat()
            self._chat.append_message("egg", export_msg, self._now())
            return

        elif result.action == "settings":
            self._open_settings()

        elif result.action.startswith("theme_"):
            theme_name = result.action.split("_", 1)[1]
            self._settings.set("theme", theme_name)
            self._config.set("theme", theme_name)
            self._config.save()
            self._settings.save()
            self._theme_mgr.apply(theme_name)
            self._logger.info(f"Theme changed to {theme_name}")

        if result.action:
            self._logger.info(f"Command executed: {result.action}")

        if result.response:
            self._chat.append_message("egg", result.response, self._now())

    def _start_typing(self):
        self._set_input_enabled(False)
        self._chat.append_message("egg", "...", self._now())
        QTimer.singleShot(self._typing_delay_ms, self._finish_typing)

    def _finish_typing(self):
        self._chat.replace_last_bubble("egg", self._pending_reply, self._pending_ts)
        self._pending_reply = ""
        self._pending_ts = ""
        self._set_input_enabled(True)
        self._input_bar.entry.setFocus()

    def _set_input_enabled(self, enabled: bool):
        self._input_bar.entry.setEnabled(enabled)
        self._input_bar.send_btn.setEnabled(enabled)

    def _export_chat(self) -> str:
        os.makedirs(self.EXPORTS_DIR, exist_ok=True)
        filename = f"chat_{datetime.now().strftime('%Y_%m_%d_%H_%M_%S')}.txt"
        filepath = os.path.join(self.EXPORTS_DIR, filename)

        history = self._chat.get_history()
        if not history:
            return "Nothing to export — chat is empty."

        lines = []
        for sender, text, ts in history:
            label = "You" if sender == "user" else "EggMan"
            lines.append(f"[{ts}] {label}: {text}")

        try:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write("\n".join(lines))
            self._logger.info(f"Chat exported: {filename}")
            return f"Chat exported: {filename}"
        except OSError as e:
            self._logger.error(f"Chat export failed: {e}")
            return f"Export failed: {e}"

    def _take_screenshot(self):
        os.makedirs(self.SCREENSHOT_DIR, exist_ok=True)
        filename = f"screenshot_{datetime.now().strftime('%Y_%m_%d_%H_%M_%S')}.png"
        filepath = os.path.join(self.SCREENSHOT_DIR, filename)
        pixmap = QApplication.primaryScreen().grabWindow(0)
        if pixmap.save(filepath, "PNG"):
            msg = f"Screenshot saved: {filename}"
            self._logger.info(f"Screenshot saved: {filename}")
        else:
            msg = "Screenshot failed. Check folder permissions."
            self._logger.error("Screenshot save failed")
        self._chat.append_message("egg", msg, self._now())

    def _open_settings(self):
        dialog = SettingsDialog(self._settings, on_saved=self._apply_settings_flags, parent=self)
        dialog.exec()

    def _apply_settings_flags(self):
        self._apply_window_flags()
        self._config.set("always_on_top", bool(self._settings.get("always_on_top")))
        self._config.save()
        self.show()

    @staticmethod
    def _now() -> str:
        return datetime.now().strftime("%H:%M")

    def closeEvent(self, event):
        self._settings.set("win_x", self.x())
        self._settings.set("win_y", self.y())
        self._settings.save()
        self._config.set("always_on_top", bool(self._settings.get("always_on_top")))
        self._config.set("typing_delay", self._typing_delay_ms)
        self._config.save()
        self._logger.info("Application shutdown")
        super().closeEvent(event)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setQuitOnLastWindowClosed(True)

    window = EggManWindow()
    window.show()

    sys.exit(app.exec())
