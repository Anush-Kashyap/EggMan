import os
import sys
import ctypes
from datetime import datetime
from pathlib import Path
from threading import Thread
from time import perf_counter
import traceback

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QFrame, QVBoxLayout, QWidget

from app.container import AppContainer
from core.commands import CommandResult
from core.paths import APP_ICON_PATH, EXPORTS_DIR as EXPORTS_FOLDER, SCREENSHOTS_DIR as SCREENSHOTS_FOLDER
from core.themes import Theme, ThemeManager
from ui.dialogs import SettingsDialog
from ui.widgets import ChatDisplay, InputBar, TitleBar

APP_NAME = "EggMan"
APP_VERSION = "0.1.9"
APP_ORGANIZATION = "EggMan"
WINDOW_TITLE = APP_NAME
WINDOWS_APP_ID = f"{APP_ORGANIZATION}.{APP_NAME}.{APP_VERSION}"


class EggManWindow(QWidget):
    _reply_ready = Signal(str, str)

    TYPING_DELAY_MS = 1000
    SCREENSHOT_DIR = SCREENSHOTS_FOLDER
    EXPORTS_DIR = EXPORTS_FOLDER

    def __init__(self):
        super().__init__()
        self.setWindowTitle(WINDOW_TITLE)
        self._apply_window_icon()

        self._services = AppContainer()
        self._config = self._services.config_manager
        self._logger = self._services.logger
        self._settings = self._services.settings_manager
        self._cmd = self._services.command_handler
        self._provider = self._services.provider
        self._conv = self._services.conversation_engine
        self._memory_manager = self._services.memory_manager
        self._memory_extractor = self._services.memory_extractor
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

    def _apply_window_icon(self):
        icon = QIcon(str(APP_ICON_PATH))
        if not icon.isNull():
            self.setWindowIcon(icon)

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
        self._reply_ready.connect(self._finish_typing)

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
            self._logger.debug("UI _on_send entering")
            result = self._cmd.handle(text)
            if result.handled:
                self._handle_command(result)
                return

            # Run AI request in background thread to avoid UI blocking
            self._start_typing()
            self._pending_ts = self._now()
            thread = Thread(target=self._fetch_reply, args=(text, self._pending_ts), daemon=True)
            self._logger.debug(f"UI starting AI worker thread name={thread.name}")
            thread.start()
            self._capture_memory(text)
        except Exception as exc:
            self._logger.error(f"Message handling failed: {exc}\n{traceback.format_exc()}")
            self._chat.append_message("egg", "Something went wrong. Please try again.", self._now())

    def _fetch_reply(self, user_message: str, timestamp: str):
        """Fetch AI reply in background thread to avoid UI blocking."""
        start = perf_counter()
        self._logger.debug("AI worker entering _fetch_reply")
        try:
            reply = self._conv.get_reply(user_message)
            self._logger.debug(
                "AI worker received reply in %.1fms len=%d",
                (perf_counter() - start) * 1000,
                len(str(reply)),
            )
        except Exception as exc:
            self._logger.error(f"AI response failed: {exc}\n{traceback.format_exc()}")
            reply = "Sorry, I'm having trouble thinking right now."

        self._logger.debug("AI worker emitting reply_ready")
        self._reply_ready.emit(str(reply), timestamp)

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
        self._logger.debug("UI entering _start_typing")
        self._set_input_enabled(False)
        self._chat.append_message("egg", "...", self._now())

    @Slot(str, str)
    def _finish_typing(self, reply: str, timestamp: str):
        self._logger.debug("UI entering _finish_typing")
        reply = str(reply) if reply else "..."
        self._chat.replace_last_bubble("egg", reply, timestamp)
        self._pending_reply = ""
        self._pending_ts = ""
        self._set_input_enabled(True)
        self._input_bar.entry.setFocus()

    def _capture_memory(self, user_message: str) -> None:
        try:
            memory = self._memory_extractor.extract(user_message)
            if memory is not None:
                self._memory_manager.save_memory(memory)
                self._logger.info(f"Memory saved: {memory.key}={memory.value}")
        except Exception as exc:
            self._logger.error(f"Memory extraction failed: {exc}\n{traceback.format_exc()}")

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


def _set_windows_app_id() -> None:
    if sys.platform != "win32":
        return
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(WINDOWS_APP_ID)
    except Exception:
        return


def create_application(argv: list[str]) -> QApplication:
    _set_windows_app_id()
    QApplication.setApplicationName(APP_NAME)
    QApplication.setApplicationVersion(APP_VERSION)
    QApplication.setOrganizationName(APP_ORGANIZATION)

    app = QApplication(argv)
    app.setStyle("Fusion")
    app.setQuitOnLastWindowClosed(True)
    icon = QIcon(str(APP_ICON_PATH))
    if not icon.isNull():
        app.setWindowIcon(icon)
    return app


def main() -> int:
    app = create_application(sys.argv)
    window = EggManWindow()
    window.show()
    window._logger.info("Qt application entering event loop")
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
