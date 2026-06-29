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

from PySide6.QtCore import Qt, Signal, Slot, QTimer
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QFrame, QVBoxLayout, QWidget

from app.container import AppContainer
from core.commands import CommandResult
from core.paths import APP_ICON_PATH, EXPORTS_DIR as EXPORTS_FOLDER, SCREENSHOTS_DIR as SCREENSHOTS_FOLDER
from core.themes import Theme, ThemeManager
from backend.voice.voice_manager import VoiceState
from ui.dialogs import SettingsDialog
from ui.widgets import ChatDisplay, InputBar, TitleBar

APP_NAME = "EggMan"
APP_VERSION = "0.1.9"
APP_ORGANIZATION = "EggMan"
WINDOW_TITLE = APP_NAME
WINDOWS_APP_ID = f"{APP_ORGANIZATION}.{APP_NAME}.{APP_VERSION}"


class EggManWindow(QWidget):
    _reply_ready = Signal(str, str)
    _voice_text_ready = Signal(str)
    _voice_error = Signal(str)
    _voice_state_changed = Signal(str)

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
        self._conv = self._services.conversation_engine
        self._memory_manager = self._services.memory_manager
        self._memory_extractor = self._services.memory_extractor
        self._voice = self._services.voice_manager
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
        self._setup_voice_callbacks()
        self._connect_signals()
        self._post_welcome()
        self._post_startup_status()

        if hasattr(self._services, "vision_manager"):
            self._services.vision_manager.set_submit_callback(self._on_ask_about_screenshot)

        if hasattr(self._services, "wake_word_service"):
            self._logger.info("Voice initialization")
            QTimer.singleShot(500, self._services.wake_word_service.start)

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

    def _setup_voice_callbacks(self):
        self._voice.bind_callbacks(
            on_state_changed=self._voice_state_callback,
            on_transcription=self._voice_transcription_callback,
            on_error=self._voice_error_callback,
        )

    def _voice_state_callback(self, state: VoiceState) -> None:
        self._voice_state_changed.emit(state.value)

    def _voice_transcription_callback(self, text: str) -> None:
        self._voice_text_ready.emit(text)

    def _voice_error_callback(self, message: str) -> None:
        self._logger.error("Voice errors: %s", message)
        self._voice_error.emit(message)

    def _connect_signals(self):
        self._input_bar.send_btn.clicked.connect(self._on_send)
        self._input_bar.entry.returnPressed.connect(self._on_send)
        self._input_bar.mic_btn.clicked.connect(self._on_mic_toggle)
        self._input_bar.screenshot_btn.clicked.connect(self._take_screenshot)
        self._reply_ready.connect(self._finish_typing)
        self._voice_text_ready.connect(self._on_voice_text)
        self._voice_error.connect(self._on_voice_error)
        self._voice_state_changed.connect(self._on_voice_state_changed)

    def apply_theme(self):
        self._update_container_style()
        if not hasattr(self, "_title_bar"):
            return
        self._title_bar.apply_theme()
        self._chat.apply_theme()
        self._input_bar.apply_theme()

    def _post_welcome(self):
        self._chat.append_message("egg", "Hello! I'm EggMan 🥚", self._now())

    def _post_startup_status(self):
        error = self._services.ollama_startup_error
        if error:
            self._chat.append_message(
                "egg",
                f"Ollama is not available right now.\n{error}\n\nOpen Settings to check your connection or start Ollama.",
                self._now(),
            )

    def _on_send(self):
        text = self._input_bar.entry.text().strip()
        if not text:
            return
        self._input_bar.entry.clear()
        self._submit_message(text)

    def _submit_message(self, text: str):
        if not text.strip():
            return

        normalized_text = text.lower().strip().rstrip(".")
        if normalized_text == "take screenshot":
            self._take_screenshot()
            return

        self._chat.append_message("user", text, self._now())

        try:
            self._logger.debug("UI _submit_message entering")
            result = self._cmd.handle(text)
            if result.handled:
                self._handle_command(result)
                return

            images = []
            if hasattr(self._services, "vision_manager") and self._services.vision_manager.has_pending_attachment():
                img_b64 = self._services.vision_manager.pop_pending_attachment()
                if img_b64:
                    images = [img_b64]

            self._start_typing()
            self._pending_ts = self._now()
            thread = Thread(target=self._fetch_reply, args=(text, self._pending_ts, images), daemon=True)
            self._logger.debug(f"UI starting AI worker thread name={thread.name}")
            thread.start()
            self._capture_memory(text)
        except Exception as exc:
            self._logger.error(f"Message handling failed: {exc}\n{traceback.format_exc()}")
            self._chat.append_message("egg", "Something went wrong. Please try again.", self._now())

    def _on_mic_toggle(self):
        if self._voice.state == VoiceState.PROCESSING:
            return
        self._logger.info("UI microphone toggle state=%s", self._voice.state.value)
        self._voice.toggle_listening()

    @Slot(str)
    def _on_voice_text(self, text: str):
        self._logger.info("UI voice transcription ready len=%d", len(text))
        self._input_bar.entry.clear()
        self._submit_message(text)

    @Slot(str)
    def _on_voice_error(self, message: str):
        self._logger.error("UI voice error: %s", message)
        self._chat.append_message("egg", message, self._now())

    @Slot(str)
    def _on_voice_state_changed(self, state: str):
        if state == VoiceState.LISTENING.value:
            self._input_bar.set_voice_listening(True)
            self._input_bar.set_voice_processing(False)
            self._set_input_enabled(False, keep_mic=True)
        elif state == VoiceState.PROCESSING.value:
            self._input_bar.set_voice_listening(False)
            self._input_bar.set_voice_processing(True)
            self._set_input_enabled(False, keep_mic=False)
        else:
            self._input_bar.set_voice_listening(False)
            self._input_bar.set_voice_processing(False)
            self._set_input_enabled(True)

    def _fetch_reply(self, user_message: str, timestamp: str, images: list[str] | None = None):
        """Fetch AI reply in background thread to avoid UI blocking."""
        start = perf_counter()
        self._logger.debug("AI worker entering _fetch_reply")
        try:
            reply = self._conv.get_reply(user_message, images=images)
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

    def _set_input_enabled(self, enabled: bool, keep_mic: bool = False):
        self._input_bar.entry.setEnabled(enabled)
        self._input_bar.send_btn.setEnabled(enabled)
        self._input_bar.screenshot_btn.setEnabled(enabled)
        self._input_bar.set_voice_controls_enabled(enabled or keep_mic)

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
        if hasattr(self._services, "vision_manager"):
            img_b64 = self._services.vision_manager.add_pending_screenshot()
            if img_b64:
                self._services.vision_manager.show_preview(img_b64)

    def _on_ask_about_screenshot(self):
        text = self._input_bar.entry.text().strip()
        if not text:
            self._chat.append_message("egg", "There is no command given for the screenshot", self._now())
            return

        self._input_bar.entry.clear()
        self._submit_message(text)

    def _open_settings(self):
        dialog = SettingsDialog(
            self._settings,
            config=self._config,
            on_saved=self._apply_settings,
            parent=self,
        )
        dialog.exec()

    def _apply_settings(self):
        self._apply_settings_flags()
        self._services.reload_wake_word()
        error = self._services.reload_ollama_provider()
        if error:
            self._chat.append_message("egg", f"Ollama: {error}", self._now())
        else:
            model = self._config.get("ollama_model")
            self._chat.append_message("egg", f"Ollama connected — model: {model}", self._now())

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
        self._voice.stop()
        if hasattr(self._services, "wake_word_service"):
            self._services.wake_word_service.stop()
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