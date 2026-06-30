from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QFont, QDragEnterEvent, QDropEvent
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
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
    QFileDialog,
)
from datetime import datetime
from pathlib import Path
import logging

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

        self.cmd_center_btn = QPushButton("Command Center")
        self.cmd_center_btn.setFixedHeight(36)
        self.cmd_center_btn.setCursor(Qt.PointingHandCursor)
        content_layout.addWidget(self.cmd_center_btn)
        self.cmd_center_btn.clicked.connect(self._open_command_center)

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

    def _open_command_center(self) -> None:
        dialog = CommandCenterWindow(self)
        dialog.exec()

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
        for btn in (self.clear_btn, self.export_btn, self.theme_btn, self.settings_btn, self.cmd_center_btn):
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


class CommandCenterWindow(QDialog):
    """Command Center listing all available slash commands."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(300, 350)
        
        if parent:
            pg = parent.geometry()
            cx = pg.x() + (pg.width() - 300) // 2
            cy = pg.y() + (pg.height() - 350) // 2
            self.move(cx, cy)
            
        self._build_ui()
        
    def _build_ui(self) -> None:
        base_layout = QVBoxLayout(self)
        base_layout.setContentsMargins(0, 0, 0, 0)
        
        container = QWidget(self)
        container.setObjectName("container")
        base_layout.addWidget(container)
        
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Title bar
        title_bar = TitleBar(self)
        title_bar._title_label.setText("COMMAND CENTER")
        layout.addWidget(title_bar)
        
        # Content
        content_widget = QWidget(container)
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(16, 16, 16, 16)
        content_layout.setSpacing(12)
        
        commands = [
            ("/help", "Open the Command Center."),
            ("/schedule", "Create reminders and recurring schedules."),
            ("/file", "Open the Knowledge Base and manage uploaded documents.")
        ]
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setObjectName("scrollArea")
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)
        scroll_layout.setContentsMargins(0, 0, 0, 0)
        scroll_layout.setSpacing(10)
        
        for cmd, desc in commands:
            cmd_lbl = QLabel(cmd)
            cmd_lbl.setFont(QFont("Segoe UI", 10, QFont.Bold))
            cmd_lbl.setStyleSheet(f"color: {Theme.TEXT_DARK};")
            
            desc_lbl = QLabel(desc)
            desc_lbl.setFont(QFont("Segoe UI", 9))
            desc_lbl.setWordWrap(True)
            desc_lbl.setStyleSheet(f"color: {Theme.TEXT_MID};")
            
            scroll_layout.addWidget(cmd_lbl)
            scroll_layout.addWidget(desc_lbl)
            
            divider = QFrame()
            divider.setFrameShape(QFrame.HLine)
            divider.setStyleSheet(f"background-color: {Theme.BORDER};")
            scroll_layout.addWidget(divider)
            
        scroll_layout.addStretch()
        scroll.setWidget(scroll_widget)
        content_layout.addWidget(scroll)
        
        layout.addWidget(content_widget, stretch=1)
        
        self.setStyleSheet(f"""
            #container {{
                background-color: {Theme.CREAM};
                border: 2px solid {Theme.BORDER};
                border-radius: {Theme.RADIUS}px;
            }}
            QScrollArea {{
                border: none;
                background: transparent;
            }}
            QWidget {{
                background: transparent;
            }}
        """)


class ScheduleWindow(QDialog):
    """Window that lists all scheduled tasks and allows deleting them."""

    def __init__(self, task_repository, parent=None) -> None:
        super().__init__(parent)
        self._repository = task_repository
        
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(320, 400)
        
        if parent:
            pg = parent.geometry()
            cx = pg.x() + (pg.width() - 320) // 2
            cy = pg.y() + (pg.height() - 400) // 2
            self.move(cx, cy)
            
        self._build_ui()
        self.load_tasks()

    def _build_ui(self) -> None:
        base_layout = QVBoxLayout(self)
        base_layout.setContentsMargins(0, 0, 0, 0)
        
        container = QWidget(self)
        container.setObjectName("container")
        base_layout.addWidget(container)
        
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Title bar
        title_bar = TitleBar(self)
        title_bar._title_label.setText("SCHEDULED TASKS")
        layout.addWidget(title_bar)
        
        # Content
        content_widget = QWidget(container)
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(16, 16, 16, 16)
        content_layout.setSpacing(12)
        
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setObjectName("scrollArea")
        
        self.scroll_widget = QWidget()
        self.scroll_widget.setObjectName("scrollAreaContent")
        self.scroll_layout = QVBoxLayout(self.scroll_widget)
        self.scroll_layout.setContentsMargins(0, 0, 0, 0)
        self.scroll_layout.setSpacing(10)
        
        self.scroll.setWidget(self.scroll_widget)
        content_layout.addWidget(self.scroll)
        
        layout.addWidget(content_widget, stretch=1)
        
        self.setStyleSheet(f"""
            QWidget#container {{
                background-color: {Theme.CREAM};
                border: 2px solid {Theme.BORDER};
                border-radius: {Theme.RADIUS}px;
            }}
            QScrollArea {{
                border: none;
                background: transparent;
            }}
            QWidget#scrollAreaContent {{
                background: transparent;
            }}
        """)

    def load_tasks(self) -> None:
        logger = logging.getLogger("eggman")
        logger.info("Schedule loaded")
        
        while self.scroll_layout.count():
            child = self.scroll_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
                
        tasks = self._repository.get_all_tasks()
        if not tasks:
            no_tasks_lbl = QLabel("No scheduled tasks found.")
            no_tasks_lbl.setFont(QFont("Segoe UI", 9))
            no_tasks_lbl.setStyleSheet(f"color: {Theme.TEXT_MID};")
            no_tasks_lbl.setAlignment(Qt.AlignCenter)
            self.scroll_layout.addWidget(no_tasks_lbl)
            return

        for task in tasks:
            task_widget = QWidget()
            task_item_layout = QHBoxLayout(task_widget)
            task_item_layout.setContentsMargins(0, 4, 0, 4)
            task_item_layout.setSpacing(6)
            
            text_widget = QWidget()
            text_layout = QVBoxLayout(text_widget)
            text_layout.setContentsMargins(0, 0, 0, 0)
            text_layout.setSpacing(2)
            
            title_lbl = QLabel(task.title)
            title_lbl.setFont(QFont("Segoe UI", 9, QFont.Bold))
            title_lbl.setWordWrap(True)
            title_lbl.setStyleSheet(f"color: {Theme.TEXT_DARK};")
            
            details_str = f"Time: {task.scheduled_time}"
            if task.repeat_status and task.repeat_status != "Once":
                details_str += f" | Repeat: {task.repeat_status}"
            details_lbl = QLabel(details_str)
            details_lbl.setFont(QFont("Segoe UI", 8))
            details_lbl.setStyleSheet(f"color: {Theme.TEXT_MID};")
            details_lbl.setWordWrap(True)
            
            text_layout.addWidget(title_lbl)
            text_layout.addWidget(details_lbl)
            
            task_item_layout.addWidget(text_widget, stretch=1)
            
            del_btn = QPushButton("❌")
            del_btn.setFixedSize(20, 20)
            del_btn.setFont(QFont("Segoe UI", 8))
            del_btn.setCursor(Qt.PointingHandCursor)
            del_btn.setStyleSheet(f"""
                QPushButton {{
                    background: transparent;
                    border: none;
                }}
                QPushButton:hover {{
                    background: {Theme.CTRL_HOVER_CLS};
                    border-radius: 4px;
                }}
            """)
            del_btn.clicked.connect(lambda checked=False, tid=task.id: self.delete_task(tid))
            task_item_layout.addWidget(del_btn)
            
            self.scroll_layout.addWidget(task_widget)
            
            divider = QFrame()
            divider.setFrameShape(QFrame.HLine)
            divider.setStyleSheet(f"background-color: {Theme.BORDER};")
            self.scroll_layout.addWidget(divider)
            
        self.scroll_layout.addStretch()

    def delete_task(self, task_id: int) -> None:
        logger = logging.getLogger("eggman")
        self._repository.delete_task(task_id)
        logger.info("Schedule deleted: ID=%s", task_id)
        self.load_tasks()


class DropArea(QLabel):
    fileDropped = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAlignment(Qt.AlignCenter)
        self.setText("Drag & Drop PDF here\nor click 'Browse Files'")
        self.setAcceptDrops(True)
        self.setFixedHeight(80)
        self.apply_default_style()

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                if url.toLocalFile().lower().endswith(".pdf"):
                    event.acceptProposedAction()
                    self.setStyleSheet(f"""
                        QLabel {{
                            border: 2px dashed {Theme.TEXT_MID};
                            border-radius: 8px;
                            color: {Theme.TEXT_DARK};
                            background: rgba(0, 0, 0, 0.06);
                            font-family: 'Segoe UI';
                            font-size: 12px;
                        }}
                    """)
                    return
        event.ignore()

    def dragLeaveEvent(self, event):
        self.apply_default_style()

    def dropEvent(self, event: QDropEvent):
        for url in event.mimeData().urls():
            file_path = url.toLocalFile()
            if file_path and file_path.lower().endswith(".pdf"):
                self.fileDropped.emit(file_path)
        self.apply_default_style()

    def apply_default_style(self):
        self.setStyleSheet(f"""
            QLabel {{
                border: 2px dashed {Theme.BORDER};
                border-radius: 8px;
                color: {Theme.TEXT_MID};
                background: rgba(0, 0, 0, 0.02);
                font-family: 'Segoe UI';
                font-size: 12px;
            }}
        """)


class KnowledgeBaseWindow(QDialog):
    """Knowledge Base window for uploading and managing documents."""

    def __init__(self, knowledge_manager, parent=None) -> None:
        super().__init__(parent)
        self._manager = knowledge_manager
        
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(340, 450)
        
        if parent:
            pg = parent.geometry()
            cx = pg.x() + (pg.width() - 340) // 2
            cy = pg.y() + (pg.height() - 450) // 2
            self.move(cx, cy)
            
        self._build_ui()
        self.load_documents()

    def _build_ui(self) -> None:
        base_layout = QVBoxLayout(self)
        base_layout.setContentsMargins(0, 0, 0, 0)
        
        container = QWidget(self)
        container.setObjectName("container")
        base_layout.addWidget(container)
        
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Title bar
        title_bar = TitleBar(self)
        title_bar._title_label.setText("KNOWLEDGE BASE")
        layout.addWidget(title_bar)
        
        # Content
        content_widget = QWidget(container)
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(16, 16, 16, 16)
        content_layout.setSpacing(12)
        
        # Drop Area
        self.drop_area = DropArea(self)
        self.drop_area.fileDropped.connect(self.upload_file)
        content_layout.addWidget(self.drop_area)
        
        # Browse Button
        self.browse_btn = QPushButton("Browse Files")
        self.browse_btn.setFixedHeight(30)
        self.browse_btn.setFont(QFont("Segoe UI", 9, QFont.Bold))
        self.browse_btn.setCursor(Qt.PointingHandCursor)
        self.browse_btn.setStyleSheet(f"""
            QPushButton {{
                background: {Theme.BTN_BG};
                color: {Theme.TEXT_DARK};
                border: 1px solid {Theme.BORDER};
                border-radius: 6px;
            }}
            QPushButton:hover {{ background: {Theme.BTN_HOVER}; }}
            QPushButton:pressed {{ background: {Theme.BTN_PRESS}; }}
        """)
        self.browse_btn.clicked.connect(self.browse_files)
        content_layout.addWidget(self.browse_btn)
        
        # Document List Scroll Area
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setObjectName("scrollArea")
        
        self.scroll_widget = QWidget()
        self.scroll_widget.setObjectName("scrollAreaContent")
        self.scroll_layout = QVBoxLayout(self.scroll_widget)
        self.scroll_layout.setContentsMargins(0, 0, 0, 0)
        self.scroll_layout.setSpacing(10)
        
        self.scroll.setWidget(self.scroll_widget)
        content_layout.addWidget(self.scroll)
        
        layout.addWidget(content_widget, stretch=1)
        
        self.setStyleSheet(f"""
            QWidget#container {{
                background-color: {Theme.CREAM};
                border: 2px solid {Theme.BORDER};
                border-radius: {Theme.RADIUS}px;
            }}
            QScrollArea {{
                border: none;
                background: transparent;
            }}
            QWidget#scrollAreaContent {{
                background: transparent;
            }}
        """)

    def browse_files(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select PDF Document", "", "PDF Files (*.pdf)"
        )
        if file_path:
            self.upload_file(file_path)

    def upload_file(self, file_path: str) -> None:
        try:
            path = Path(file_path)
            self._manager.upload_document(path)
            self.load_documents()
        except Exception as e:
            logging.getLogger("eggman").error("KB UI: upload failed: %s", e)

    def load_documents(self) -> None:
        while self.scroll_layout.count():
            child = self.scroll_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
                
        docs = self._manager.get_all_documents()
        if not docs:
            no_docs_lbl = QLabel("No uploaded documents.")
            no_docs_lbl.setFont(QFont("Segoe UI", 9))
            no_docs_lbl.setStyleSheet(f"color: {Theme.TEXT_MID};")
            no_docs_lbl.setAlignment(Qt.AlignCenter)
            self.scroll_layout.addWidget(no_docs_lbl)
            return

        for doc in docs:
            doc_widget = QWidget()
            doc_item_layout = QHBoxLayout(doc_widget)
            doc_item_layout.setContentsMargins(0, 4, 0, 4)
            doc_item_layout.setSpacing(6)
            
            text_widget = QWidget()
            text_layout = QVBoxLayout(text_widget)
            text_layout.setContentsMargins(0, 0, 0, 0)
            text_layout.setSpacing(2)
            
            title_lbl = QLabel(doc.filename)
            title_lbl.setFont(QFont("Segoe UI", 9, QFont.Bold))
            title_lbl.setWordWrap(True)
            title_lbl.setStyleSheet(f"color: {Theme.TEXT_DARK};")
            
            # Format date/size
            try:
                date_dt = datetime.fromisoformat(doc.created_at)
                date_str = date_dt.strftime("%Y-%m-%d")
            except:
                date_str = doc.created_at[:10]
                
            size_str = self.format_size(doc.file_size)
            details_lbl = QLabel(f"Size: {size_str} | Uploaded: {date_str}")
            details_lbl.setFont(QFont("Segoe UI", 8))
            details_lbl.setStyleSheet(f"color: {Theme.TEXT_MID};")
            details_lbl.setWordWrap(True)
            
            text_layout.addWidget(title_lbl)
            text_layout.addWidget(details_lbl)
            
            doc_item_layout.addWidget(text_widget, stretch=1)
            
            del_btn = QPushButton("❌")
            del_btn.setFixedSize(20, 20)
            del_btn.setFont(QFont("Segoe UI", 8))
            del_btn.setCursor(Qt.PointingHandCursor)
            del_btn.setStyleSheet(f"""
                QPushButton {{
                    background: transparent;
                    border: none;
                }}
                QPushButton:hover {{
                    background: {Theme.CTRL_HOVER_CLS};
                    border-radius: 4px;
                }}
            """)
            del_btn.clicked.connect(lambda checked=False, tid=doc.id: self.delete_document(tid))
            doc_item_layout.addWidget(del_btn)
            
            self.scroll_layout.addWidget(doc_widget)
            
            divider = QFrame()
            divider.setFrameShape(QFrame.HLine)
            divider.setStyleSheet(f"background-color: {Theme.BORDER};")
            self.scroll_layout.addWidget(divider)
            
        self.scroll_layout.addStretch()

    def delete_document(self, doc_id: int) -> None:
        self._manager.remove_document(doc_id)
        self.load_documents()

    def format_size(self, size_bytes: int) -> str:
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        else:
            return f"{size_bytes / (1024 * 1024):.1f} MB"
