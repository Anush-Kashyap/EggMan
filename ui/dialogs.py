from __future__ import annotations
from typing import List, Any, Optional
from PySide6.QtCore import Qt, Signal, QTimer, QRect, QPoint, QSize
from PySide6.QtGui import QFont, QDragEnterEvent, QDropEvent, QPainter, QColor, QBrush
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
    QTabWidget,
    QListWidget,
    QSplitter,
    QGridLayout,
    QProgressBar,
)
from datetime import datetime
from pathlib import Path
import logging

from backend.ai.ollama_provider import OllamaProvider
from backend.knowledge.vector_store import SQLiteVectorStore
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


STATUS_COLORS = {
    "waiting": "#FFA726",
    "parsing": "#42A5F5",
    "chunking": "#AB47BC",
    "embedding": "#26A69A",
    "indexed": "#66BB6A",
    "failed": "#EF5350",
}

STATUS_LABELS = {
    "waiting": "Waiting",
    "parsing": "Parsing...",
    "chunking": "Chunking...",
    "embedding": "Embedding...",
    "indexed": "Indexed",
    "failed": "Failed",
}


class KnowledgeBaseWindow(QDialog):
    """Knowledge Base window for uploading and managing documents."""

    def __init__(self, knowledge_manager, parent=None) -> None:
        super().__init__(parent)
        self._manager = knowledge_manager
        
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(380, 480)
        
        if parent:
            pg = parent.geometry()
            cx = pg.x() + (pg.width() - 380) // 2
            cy = pg.y() + (pg.height() - 480) // 2
            self.move(cx, cy)
            
        self._build_ui()
        self.load_documents()

        # Polling timer to refresh document status during background indexing
        self._refresh_timer = QTimer(self)
        self._refresh_timer.setInterval(1500)
        self._refresh_timer.timeout.connect(self._poll_refresh)
        self._refresh_timer.start()

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

    def closeEvent(self, event):
        self._refresh_timer.stop()
        super().closeEvent(event)

    def _poll_refresh(self) -> None:
        """Periodically check for status changes during background indexing."""
        self.load_documents()

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

        has_pending = False
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
            except (ValueError, TypeError) as exc:
                logging.getLogger("eggman").debug("Failed to parse document ISO date %s: %s", doc.created_at, exc)
                date_str = doc.created_at[:10] if doc.created_at else "Unknown"
                
            size_str = self.format_size(doc.file_size)
            status_color = STATUS_COLORS.get(doc.status, "#999")
            status_label = STATUS_LABELS.get(doc.status, doc.status)
            chunk_info = f" | {doc.chunk_count} chunks" if doc.chunk_count > 0 else ""
            details_lbl = QLabel(f"Size: {size_str} | Uploaded: {date_str}")
            details_lbl.setFont(QFont("Segoe UI", 8))
            details_lbl.setStyleSheet(f"color: {Theme.TEXT_MID};")
            details_lbl.setWordWrap(True)
            
            status_lbl = QLabel(status_label)
            status_lbl.setFont(QFont("Segoe UI", 8, QFont.Bold))
            status_lbl.setStyleSheet(f"color: {status_color};")
            
            text_layout.addWidget(title_lbl)
            text_layout.addWidget(details_lbl)
            text_layout.addWidget(status_lbl)
            
            doc_item_layout.addWidget(text_widget, stretch=1)
            
            # Delete button (only enabled for indexed/failed docs)
            del_btn = QPushButton("❌")
            del_btn.setFixedSize(20, 20)
            del_btn.setFont(QFont("Segoe UI", 8))
            del_btn.setCursor(Qt.PointingHandCursor)
            del_btn.setEnabled(doc.status in ("indexed", "failed"))
            del_btn.setStyleSheet(f"""
                QPushButton {{
                    background: transparent;
                    border: none;
                }}
                QPushButton:hover {{
                    background: {Theme.CTRL_HOVER_CLS};
                    border-radius: 4px;
                }}
                QPushButton:disabled {{
                    opacity: 0.3;
                }}
            """)
            del_btn.clicked.connect(lambda checked=False, tid=doc.id: self.delete_document(tid))
            doc_item_layout.addWidget(del_btn)
            
            self.scroll_layout.addWidget(doc_widget)
            
            divider = QFrame()
            divider.setFrameShape(QFrame.HLine)
            divider.setStyleSheet(f"background-color: {Theme.BORDER};")
            self.scroll_layout.addWidget(divider)

            if doc.status not in ("indexed", "failed"):
                has_pending = True
            
        self.scroll_layout.addStretch()

        # Keep polling if there are pending documents
        if has_pending:
            if not self._refresh_timer.isActive():
                self._refresh_timer.start()
        else:
            self._refresh_timer.stop()

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


class ToastLabel(QLabel):
    """Auto-dismissing borderless toast alert for developer state notifications."""

    def __init__(self, text: str, parent=None):
        super().__init__(text, parent)
        self.setWindowFlags(Qt.ToolTip | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setStyleSheet(f"""
            QLabel {{
                background-color: rgba(30, 30, 30, 0.94);
                color: #ffffff;
                border: 1px solid #555555;
                border-radius: 12px;
                padding: 8px 16px;
                font-family: 'Segoe UI';
                font-size: 11px;
                font-weight: bold;
            }}
        """)
        self.setAlignment(Qt.AlignCenter)
        self.adjustSize()
        
        # Center toast relative to parent window if available
        if parent:
            geo = parent.geometry()
            cx = geo.x() + (geo.width() - self.width()) // 2
            cy = geo.y() + (geo.height() - self.height()) // 2
            self.move(cx, cy)
        else:
            # Default to top-center of active screen
            screen = QApplication.primaryScreen()
            if screen:
                geom = screen.geometry()
                self.move((geom.width() - self.width()) // 2, 100)
        
        # Auto-close timer
        QTimer.singleShot(2000, self.close)


class StackedTokenBar(QWidget):
    """Visual horizontal stacked progress bar representing prompt tokens breakdown."""

    def __init__(self, system: int, user: int, history: int, parent=None):
        super().__init__(parent)
        self.system = system
        self.user = user
        self.history = history
        self.setFixedHeight(12)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        total = self.system + self.user + self.history
        if total == 0:
            # Draw gray placeholder if no tokens
            painter.setBrush(QBrush(QColor("#D0D0D0")))
            painter.setPen(Qt.NoPen)
            painter.drawRoundedRect(self.rect(), 4, 4)
            return

        w_sys = int((self.system / total) * self.width())
        w_usr = int((self.user / total) * self.width())
        w_his = self.width() - w_sys - w_usr

        # System: Purple
        painter.setBrush(QBrush(QColor("#8A2BE2")))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(QRect(0, 0, w_sys + 4, self.height()), 4, 4)

        # User: Blue
        painter.setBrush(QBrush(QColor("#1E90FF")))
        painter.drawRect(QRect(w_sys, 0, w_usr, self.height()))

        # History: SeaGreen
        painter.setBrush(QBrush(QColor("#2E8B57")))
        painter.drawRoundedRect(QRect(w_sys + w_usr - 4, 0, w_his + 4, self.height()), 4, 4)


class TimelineStageBar(QWidget):
    """Horizontal bar chart indicating execution duration of a stage relative to total latency."""

    def __init__(self, label: str, duration: float, total_duration: float, parent=None):
        super().__init__(parent)
        self.label = label
        self.duration = duration
        self.total_duration = total_duration
        self.setFixedHeight(24)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Background
        painter.setBrush(QBrush(QColor(Theme.CREAM_DARK)))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(self.rect(), 4, 4)

        # Fill duration proportionally
        ratio = self.duration / self.total_duration if self.total_duration > 0.0 else 0.0
        w_fill = int(ratio * self.width())
        if w_fill > 0:
            painter.setBrush(QBrush(QColor("#4CAF50")))
            painter.drawRoundedRect(QRect(0, 0, w_fill, self.height()), 4, 4)

        # Labels text
        painter.setFont(QFont("Segoe UI", 9))
        painter.setPen(QColor(Theme.TEXT_DARK))
        painter.drawText(8, 16, f"{self.label} ({self.duration:.3f} s)")

        percentage = int(ratio * 100)
        painter.drawText(self.width() - 40, 16, f"{percentage}%")


class EggInspectorWindow(QDialog):
    """Developer-only diagnostics and performance profiling dashboard."""

    def __init__(self, services, parent=None) -> None:
        super().__init__(parent)
        self._services = services
        self.setWindowTitle("Egg Inspector - Developer Diagnostics")
        self.setMinimumSize(750, 520)
        self.resize(850, 580)
        self.setStyleSheet(f"background-color: {Theme.CREAM}; color: {Theme.TEXT_DARK};")

        self._build_ui()

        # Polling/Refresh timer for status updates & profiling history
        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._on_tick)
        self._timer.start()

        self._last_history_len = -1
        self._on_tick()

    def _build_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(10)

        # 1. Tab Widget
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet(f"""
            QTabWidget::panel {{
                border: 1px solid {Theme.BORDER};
                background: {Theme.CREAM};
                border-radius: 6px;
            }}
            QTabBar::tab {{
                background: {Theme.CREAM_DARK};
                color: {Theme.TEXT_MID};
                border: 1px solid {Theme.BORDER};
                border-bottom: none;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
                padding: 6px 12px;
                font-family: 'Segoe UI';
                font-size: 11px;
            }}
            QTabBar::tab:selected, QTabBar::tab:hover {{
                background: {Theme.CREAM};
                color: {Theme.TEXT_DARK};
                font-weight: bold;
            }}
        """)
        main_layout.addWidget(self.tabs, stretch=1)

        # Initialize Tabs
        self._init_performance_tab()
        self._init_startup_tab()
        self._init_knowledge_tab()
        self._init_placeholder_tabs()

        # 2. Status Bar live panel at bottom
        self._build_status_panel()
        main_layout.addWidget(self.status_panel)

    def _init_performance_tab(self) -> None:
        perf_widget = QWidget()
        layout = QHBoxLayout(perf_widget)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(10)

        # Left Column: Request List Splitter
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(6)

        list_title = QLabel("Recent Requests:")
        list_title.setFont(QFont("Segoe UI", 10, QFont.Bold))
        left_layout.addWidget(list_title)

        self.req_list = QListWidget()
        self.req_list.setFont(QFont("Segoe UI", 9))
        self.req_list.setStyleSheet(f"""
            QListWidget {{
                border: 1px solid {Theme.BORDER};
                background: {Theme.CREAM_DARK};
                border-radius: 6px;
                padding: 4px;
            }}
            QListWidget::item {{
                padding: 6px;
                border-bottom: 1px solid {Theme.BORDER};
                border-radius: 4px;
            }}
            QListWidget::item:hover {{
                background: {Theme.BTN_HOVER};
            }}
            QListWidget::item:selected {{
                background: {Theme.BTN_BG};
                color: {Theme.TEXT_DARK};
                font-weight: bold;
            }}
        """)
        self.req_list.itemSelectionChanged.connect(self._on_request_selected)
        left_layout.addWidget(self.req_list)

        # Right Column: Timing details
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(8)

        details_title = QLabel("Stage Timings:")
        details_title.setFont(QFont("Segoe UI", 10, QFont.Bold))
        right_layout.addWidget(details_title)

        self.details_scroll = QScrollArea()
        self.details_scroll.setWidgetResizable(True)
        self.details_scroll.setStyleSheet(f"border: 1px solid {Theme.BORDER}; border-radius: 6px; background: {Theme.CREAM_DARK};")

        scroll_content = QWidget()
        scroll_content.setStyleSheet("background: transparent;")
        self.details_grid = QGridLayout(scroll_content)
        self.details_grid.setContentsMargins(12, 12, 12, 12)
        self.details_grid.setVerticalSpacing(8)
        self.details_grid.setHorizontalSpacing(20)

        self.details_scroll.setWidget(scroll_content)
        right_layout.addWidget(self.details_scroll)

        # Assemble Splitter
        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(left_widget)
        splitter.addWidget(right_widget)
        splitter.setSizes([300, 450])
        layout.addWidget(splitter)

        self.tabs.addTab(perf_widget, "📊 Performance")

    def _init_startup_tab(self) -> None:
        """Build the Startup timing panel inside Egg Inspector."""
        startup_widget = QWidget()
        layout = QVBoxLayout(startup_widget)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        title_lbl = QLabel("Startup Performance")
        title_lbl.setFont(QFont("Segoe UI", 12, QFont.Bold))
        title_lbl.setStyleSheet(f"color: {Theme.TEXT_DARK};")
        layout.addWidget(title_lbl)

        self.startup_scroll = QScrollArea()
        self.startup_scroll.setWidgetResizable(True)
        self.startup_scroll.setStyleSheet(
            f"border: 1px solid {Theme.BORDER}; border-radius: 6px; background: {Theme.CREAM_DARK};"
        )
        layout.addWidget(self.startup_scroll, stretch=1)

        self.tabs.addTab(startup_widget, "🚀 Startup")

    def _init_placeholder_tabs(self) -> None:
        placeholder_tabs = [
            ("🧠 Context", "Context Dashboard Coming Soon\n\nReserved for Future Development"),
            ("💾 Memory", "Memory Graph Visualizer Coming Soon\n\nReserved for Future Development"),
            ("🛠 Tools", "Tool Execution Inspector Coming Soon\n\nReserved for Future Development"),
            ("🎤 Voice", "Voice Synthesis Diagnostic Panel Coming Soon\n\nReserved for Future Development"),
            ("👁 Vision", "Vision Token Calculator Coming Soon\n\nReserved for Future Development"),
            ("📜 Logs", "Log Stream Aggregator Coming Soon\n\nReserved for Future Development"),
        ]
        for name, text in placeholder_tabs:
            widget = QWidget()
            layout = QVBoxLayout(widget)
            layout.setContentsMargins(20, 20, 20, 20)
            lbl = QLabel(text)
            lbl.setFont(QFont("Segoe UI", 11))
            lbl.setStyleSheet(f"color: {Theme.TEXT_MID};")
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setWordWrap(True)
            layout.addWidget(lbl)
            self.tabs.addTab(widget, name)

    def _init_knowledge_tab(self) -> None:
        """Build the Knowledge System diagnostics panel."""
        kb_widget = QWidget()
        layout = QVBoxLayout(kb_widget)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        title_lbl = QLabel("Knowledge System Diagnostics")
        title_lbl.setFont(QFont("Segoe UI", 12, QFont.Bold))
        title_lbl.setStyleSheet(f"color: {Theme.TEXT_DARK};")
        layout.addWidget(title_lbl)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(
            f"border: 1px solid {Theme.BORDER}; border-radius: 6px; background: {Theme.CREAM_DARK};"
        )

        content = QWidget()
        content.setStyleSheet("background: transparent;")
        grid = QGridLayout(content)
        grid.setContentsMargins(16, 16, 16, 16)
        grid.setVerticalSpacing(10)
        grid.setHorizontalSpacing(24)

        scroll.setWidget(content)
        self._kb_scroll = scroll
        layout.addWidget(scroll, stretch=1)

        self.tabs.addTab(kb_widget, "📚 Knowledge")

    def _build_status_panel(self) -> None:
        self.status_panel = QFrame()
        self.status_panel.setFrameStyle(QFrame.StyledPanel | QFrame.Sunken)
        self.status_panel.setStyleSheet(f"""
            QFrame {{
                background-color: {Theme.CREAM_DARK};
                border: 1px solid {Theme.BORDER};
                border-radius: 6px;
                padding: 6px;
            }}
            QLabel {{
                font-family: 'Segoe UI';
                font-size: 10px;
                color: {Theme.TEXT_MID};
            }}
        """)
        grid = QGridLayout(self.status_panel)
        grid.setContentsMargins(6, 6, 6, 6)
        grid.setSpacing(8)

        self.status_labels = {
            "ollama": QLabel("Ollama: Loading..."),
            "chat_model": QLabel("Chat Model: Loading..."),
            "vision_model": QLabel("Vision Model: Loading..."),
            "avg_resp": QLabel("Avg Response: Loading..."),
            "avg_token": QLabel("Avg First Token: Loading..."),
            "dev_status": QLabel("Developer Mode: Loading..."),
            "gpu": QLabel("GPU: Loading..."),
            "vram": QLabel("VRAM: Loading...")
        }

        grid.addWidget(self.status_labels["ollama"], 0, 0)
        grid.addWidget(self.status_labels["chat_model"], 0, 1)
        grid.addWidget(self.status_labels["vision_model"], 0, 2)
        grid.addWidget(self.status_labels["dev_status"], 0, 3)

        grid.addWidget(self.status_labels["gpu"], 1, 0)
        grid.addWidget(self.status_labels["vram"], 1, 1)
        grid.addWidget(self.status_labels["avg_resp"], 1, 2)
        grid.addWidget(self.status_labels["avg_token"], 1, 3)

    def _on_tick(self) -> None:
        """Periodic UI updates for status stats and new requests history."""
        from backend.profiler.performance_profiler import PerformanceProfiler
        profiler = PerformanceProfiler.get_instance()
        
        with profiler._history_lock:
            current_len = len(profiler.history)
            if current_len != self._last_history_len:
                self._last_history_len = current_len
                self._refresh_request_list(profiler.history)

        from backend.session.session_manager import SessionManager
        session = SessionManager.get_instance().context
        
        dev_text = "ENABLED 🛠" if session.developer_mode else "DISABLED"
        self.status_labels["dev_status"].setText(f"Developer Mode: {dev_text}")
        
        provider_name = session.active_provider or "Unknown"
        self.status_labels["ollama"].setText(f"Ollama: {provider_name.capitalize()}")
        self.status_labels["chat_model"].setText(f"Chat Model: {session.active_chat_model or 'qwen3:8b'}")
        self.status_labels["vision_model"].setText(f"Vision Model: {session.active_vision_model or 'qwen2.5vl:7b'}")

        with profiler._history_lock:
            total_requests = len(profiler.history)
            if total_requests > 0:
                avg_total = sum(p.total_time for p in profiler.history) / total_requests
                self.status_labels["avg_resp"].setText(f"Avg Response: {avg_total:.2f} s")

                first_token_sum = 0.0
                first_token_count = 0
                for p in profiler.history:
                    token_time = p.stages.get("Ollama First Token") or p.stages.get("Vision Processing")
                    if token_time is not None:
                        first_token_sum += token_time
                        first_token_count += 1
                
                if first_token_count > 0:
                    avg_ft = first_token_sum / first_token_count
                    self.status_labels["avg_token"].setText(f"Avg First Token: {avg_ft:.2f} s")
                else:
                    self.status_labels["avg_token"].setText("Avg First Token: N/A")
            else:
                self.status_labels["avg_resp"].setText("Avg Response: N/A")
                self.status_labels["avg_token"].setText("Avg First Token: N/A")

        if not hasattr(self, "_gpu_name"):
            self._gpu_name, self._vram = profiler.get_gpu_diagnostics()

        self.status_labels["gpu"].setText(f"GPU: {self._gpu_name}")
        self.status_labels["vram"].setText(f"VRAM: {self._vram}")

        # Refresh startup panel (only needed until it's finalized)
        self._refresh_startup_panel()

        # Refresh Knowledge tab
        self._refresh_knowledge_panel()

    def _refresh_startup_panel(self) -> None:
        """Rebuild the startup timing panel content from the StartupService profile."""
        if not hasattr(self, "startup_scroll"):
            return

        # Try to get the startup service from the parent window
        parent_window = self.parent()
        startup_service = None
        if parent_window and hasattr(parent_window, "_startup_service"):
            startup_service = parent_window._startup_service
        elif hasattr(self._services, "_startup_service"):
            startup_service = self._services._startup_service

        if startup_service is None:
            return

        profile = startup_service.profile
        state = startup_service.state

        # Avoid rebuilding when nothing has changed and startup is finalized
        profile_key = (tuple(sorted(profile.stages.items())), profile.status)
        if getattr(self, "_last_startup_key", None) == profile_key and state.value != "INITIALIZING":
            return
        self._last_startup_key = profile_key

        # Reconstruct the scroll content
        old_w = self.startup_scroll.takeWidget()
        if old_w:
            old_w.deleteLater()

        content = QWidget()
        content.setStyleSheet("background: transparent;")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(16, 16, 16, 16)
        content_layout.setSpacing(0)

        grid_widget = QWidget()
        grid = QGridLayout(grid_widget)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setVerticalSpacing(10)
        grid.setHorizontalSpacing(24)

        STAGE_ORDER = [
            "SessionContext",
            "Scheduler",
            "Reminder Check",
            "Voice Initialization",
            "Ollama Connection",
            "Model Warm-Up",
            "Configuration",
        ]

        row = 0

        def _add_row(label: str, value: str, bold: bool = False, color: str = "") -> None:
            nonlocal row
            name_lbl = QLabel(label)
            name_lbl.setFont(QFont("Segoe UI", 10, QFont.Bold if bold else QFont.Normal))
            name_lbl.setStyleSheet(f"color: {color or Theme.TEXT_DARK};")

            val_lbl = QLabel(value)
            val_lbl.setFont(QFont("Segoe UI", 10, QFont.Bold if bold else QFont.Normal))
            val_lbl.setStyleSheet(f"color: {color or Theme.TEXT_DARK};")
            val_lbl.setAlignment(Qt.AlignRight)

            grid.addWidget(name_lbl, row, 0)
            grid.addWidget(val_lbl, row, 1)
            row += 1

        # Individual stages
        for stage_name in STAGE_ORDER:
            val = profile.stages.get(stage_name)
            if val is not None:
                _add_row(stage_name, f"{val:.2f} s")

        # Any extra stages not in the expected list
        for k, v in profile.stages.items():
            if k not in STAGE_ORDER:
                _add_row(k, f"{v:.2f} s")

        content_layout.addWidget(grid_widget)

        # Divider
        div = QFrame()
        div.setFrameShape(QFrame.HLine)
        div.setStyleSheet(f"background-color: {Theme.BORDER}; margin-top: 8px; margin-bottom: 8px;")
        content_layout.addWidget(div)

        # Total startup time
        total_layout = QHBoxLayout()
        total_name = QLabel("Total Startup Time")
        total_name.setFont(QFont("Segoe UI", 11, QFont.Bold))
        total_name.setStyleSheet(f"color: {Theme.TEXT_DARK};")
        total_val = QLabel(f"{profile.total_time:.2f} s" if profile.total_time > 0 else "Running...")
        total_val.setFont(QFont("Segoe UI", 11, QFont.Bold))
        total_val.setStyleSheet("color: #4CAF50;")
        total_val.setAlignment(Qt.AlignRight)
        total_layout.addWidget(total_name)
        total_layout.addStretch()
        total_layout.addWidget(total_val)
        content_layout.addLayout(total_layout)

        # Startup Status
        status_color = {
            "READY": "#4CAF50",
            "INITIALIZING": "#FFA726",
            "ERROR": "#EF5350",
        }.get(state.value, Theme.TEXT_DARK)
        status_layout = QHBoxLayout()
        status_name = QLabel("Startup Status")
        status_name.setFont(QFont("Segoe UI", 10))
        status_name.setStyleSheet(f"color: {Theme.TEXT_MID};")
        status_val = QLabel(state.value)
        status_val.setFont(QFont("Segoe UI", 10, QFont.Bold))
        status_val.setStyleSheet(f"color: {status_color};")
        status_val.setAlignment(Qt.AlignRight)
        status_layout.addWidget(status_name)
        status_layout.addStretch()
        status_layout.addWidget(status_val)
        content_layout.addLayout(status_layout)

        content_layout.addStretch()
        self.startup_scroll.setWidget(content)


    def _refresh_request_list(self, history: List[RequestProfile]) -> None:
        """Repopulate the request list widget (chronologically descending)."""
        current_selection = self.req_list.currentRow()
        self.req_list.clear()
        
        for profile in reversed(history):
            title = f"#{profile.request_num} - {profile.user_message[:20]}... ({profile.total_time:.2f}s)"
            self.req_list.addItem(title)

        if current_selection >= 0 and current_selection < self.req_list.count():
            self.req_list.setCurrentRow(current_selection)

    def _on_request_selected(self) -> None:
        """Handle request selection changes to update timing details list."""
        old_widget = self.details_scroll.takeWidget()
        if old_widget:
            old_widget.deleteLater()

        selected_row = self.req_list.currentRow()
        if selected_row < 0:
            return

        from backend.profiler.performance_profiler import PerformanceProfiler
        profiler = PerformanceProfiler.get_instance()
        
        with profiler._history_lock:
            if selected_row < len(profiler.history):
                profile = profiler.history[len(profiler.history) - 1 - selected_row]
            else:
                return

        scroll_content = QWidget()
        scroll_content.setStyleSheet("background: transparent;")
        main_layout = QVBoxLayout(scroll_content)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(14)

        # Header with classification and complexity score
        header_layout = QHBoxLayout()
        header_title = QLabel(f"Request #{profile.request_num} Details")
        header_title.setFont(QFont("Segoe UI", 11, QFont.Bold))
        header_title.setStyleSheet(f"color: {Theme.TEXT_DARK};")
        header_layout.addWidget(header_title)

        class_lbl = QLabel(f"[{profile.request_classification.upper()}] (Complexity: {profile.complexity_score}/10)")
        class_lbl.setFont(QFont("Segoe UI", 9, QFont.Bold))
        class_lbl.setStyleSheet(f"color: {Theme.TEXT_MID};")
        header_layout.addStretch()
        header_layout.addWidget(class_lbl)
        main_layout.addLayout(header_layout)

        # Flags layout (Memory, Knowledge, Vision, Tools)
        flags_layout = QHBoxLayout()
        flags_layout.setSpacing(10)
        
        def make_flag_label(name: str, active: bool) -> QLabel:
            lbl = QLabel(f"{name}: {'✅' if active else '❌'}")
            lbl.setFont(QFont("Segoe UI", 9, QFont.Bold))
            lbl.setStyleSheet(f"color: {Theme.TEXT_DARK};")
            return lbl

        flags_layout.addWidget(make_flag_label("Memory", profile.memory_used))
        flags_layout.addWidget(make_flag_label("Knowledge", profile.knowledge_used))
        flags_layout.addWidget(make_flag_label("Vision", profile.vision_used))
        flags_layout.addWidget(make_flag_label("Tools", profile.tools_executed))
        main_layout.addLayout(flags_layout)

        # Metadata Section
        meta_section_title = QLabel("Model & Connection Info")
        meta_section_title.setFont(QFont("Segoe UI", 9, QFont.Bold))
        meta_section_title.setStyleSheet(f"color: {Theme.TEXT_MID}; text-transform: uppercase;")
        main_layout.addWidget(meta_section_title)

        grid_meta = QWidget()
        grid_layout = QGridLayout(grid_meta)
        grid_layout.setContentsMargins(0, 0, 0, 0)
        grid_layout.setVerticalSpacing(6)
        grid_layout.setHorizontalSpacing(16)

        def add_meta_row(label: str, val: str, row: int):
            lbl_name = QLabel(label)
            lbl_name.setFont(QFont("Segoe UI", 9))
            lbl_name.setStyleSheet(f"color: {Theme.TEXT_DARK};")
            lbl_val = QLabel(val)
            lbl_val.setFont(QFont("Segoe UI", 9, QFont.Bold))
            lbl_val.setStyleSheet(f"color: {Theme.TEXT_DARK};")
            grid_layout.addWidget(lbl_name, row, 0)
            grid_layout.addWidget(lbl_val, row, 1)

        add_meta_row("Model Name", profile.model_name, 0)
        add_meta_row("Provider", profile.provider.upper(), 1)
        add_meta_row("Keep Alive", profile.keep_alive, 2)
        
        state_color = "#4CAF50" if profile.model_state == "Warm" else "#FFA726"
        add_meta_row("Model State", f"<span style='color: {state_color};'>{profile.model_state}</span>", 3)
        # Enable rich text formatting for state color
        grid_layout.itemAtPosition(3, 1).widget().setTextFormat(Qt.RichText)
        
        add_meta_row("First Token Latency", f"{profile.first_token_latency:.2f} s", 4)
        add_meta_row("Generation Speed", f"{profile.generation_speed:.1f} tokens/s", 5)

        main_layout.addWidget(grid_meta)

        # Divider
        div1 = QFrame()
        div1.setFrameShape(QFrame.HLine)
        div1.setStyleSheet(f"background-color: {Theme.BORDER};")
        main_layout.addWidget(div1)

        # Tokens Section
        token_section_title = QLabel("Token Usage")
        token_section_title.setFont(QFont("Segoe UI", 9, QFont.Bold))
        token_section_title.setStyleSheet(f"color: {Theme.TEXT_MID}; text-transform: uppercase;")
        main_layout.addWidget(token_section_title)

        token_summary = QHBoxLayout()
        token_summary.addWidget(QLabel(f"<b>Total:</b> {profile.total_tokens} tokens"))
        token_summary.addStretch()
        token_summary.addWidget(QLabel(f"<b>Prompt:</b> {profile.prompt_tokens} (size: {profile.prompt_char_count} chars)"))
        token_summary.addStretch()
        token_summary.addWidget(QLabel(f"<b>Output:</b> {profile.output_tokens}"))
        for i in range(token_summary.count()):
            item = token_summary.itemAt(i).widget()
            if item:
                item.setFont(QFont("Segoe UI", 9))
                item.setStyleSheet(f"color: {Theme.TEXT_DARK};")
        main_layout.addLayout(token_summary)

        # Stacked Token Bar
        token_bar = StackedTokenBar(
            profile.system_prompt_tokens,
            profile.user_prompt_tokens,
            profile.history_tokens,
            self
        )
        main_layout.addWidget(token_bar)

        # Token Legend
        legend_layout = QHBoxLayout()
        def add_legend_item(color: str, text: str):
            indicator = QLabel("■")
            indicator.setStyleSheet(f"color: {color}; font-size: 12px;")
            label = QLabel(text)
            label.setFont(QFont("Segoe UI", 8))
            label.setStyleSheet(f"color: {Theme.TEXT_DARK};")
            legend_layout.addWidget(indicator)
            legend_layout.addWidget(label)
            legend_layout.addSpacing(10)

        add_legend_item("#8A2BE2", f"System ({profile.system_prompt_tokens})")
        add_legend_item("#1E90FF", f"User ({profile.user_prompt_tokens})")
        add_legend_item("#2E8B57", f"History ({profile.history_tokens})")
        legend_layout.addStretch()
        main_layout.addLayout(legend_layout)

        # Divider
        div2 = QFrame()
        div2.setFrameShape(QFrame.HLine)
        div2.setStyleSheet(f"background-color: {Theme.BORDER};")
        main_layout.addWidget(div2)

        # Stage Timings (Timeline) Section
        timeline_section_title = QLabel("Execution Stages Timeline")
        timeline_section_title.setFont(QFont("Segoe UI", 9, QFont.Bold))
        timeline_section_title.setStyleSheet(f"color: {Theme.TEXT_MID}; text-transform: uppercase;")
        main_layout.addWidget(timeline_section_title)

        stages_display = [
            ("Speech-to-Text", "Speech-to-Text"),
            ("Prompt Builder", "Prompt Builder"),
            ("Memory Retrieval", "Memory Retrieval"),
            ("Knowledge Retrieval", "Knowledge Retrieval"),
            ("Tool Execution", "Tool Execution"),
            ("Vision Processing", "Vision Processing"),
            ("Ollama First Token", "Ollama First Token"),
            ("Response Generation", "Response Generation"),
            ("Streaming", "Streaming"),
        ]

        timeline_container = QWidget()
        timeline_layout = QVBoxLayout(timeline_container)
        timeline_layout.setContentsMargins(0, 0, 0, 0)
        timeline_layout.setSpacing(6)

        total_time_stages = profile.total_time
        for display_name, stage_key in stages_display:
            val = profile.stages.get(stage_key)
            if val is not None:
                stage_bar = TimelineStageBar(display_name, val, total_time_stages, self)
                timeline_layout.addWidget(stage_bar)

        main_layout.addWidget(timeline_container)

        # Divider
        div3 = QFrame()
        div3.setFrameShape(QFrame.HLine)
        div3.setStyleSheet(f"background-color: {Theme.BORDER};")
        main_layout.addWidget(div3)

        # Comparison Action & Total Latency
        bottom_layout = QHBoxLayout()
        
        comp_btn = QPushButton("⚖ Compare with Averages")
        comp_btn.setFont(QFont("Segoe UI", 9, QFont.Bold))
        comp_btn.setStyleSheet(f"""
            QPushButton {{
                background: {Theme.BTN_BG};
                color: {Theme.TEXT_DARK};
                border: 1px solid {Theme.BORDER};
                border-radius: 4px;
                padding: 4px 10px;
            }}
            QPushButton:hover {{ background: {Theme.BTN_HOVER}; }}
            QPushButton:pressed {{ background: {Theme.BTN_PRESS}; }}
        """)
        comp_btn.clicked.connect(self._on_compare_clicked)
        bottom_layout.addWidget(comp_btn)
        
        bottom_layout.addStretch()

        total_lbl = QLabel("Total Execution Time:")
        total_lbl.setFont(QFont("Segoe UI", 10, QFont.Bold))
        total_lbl.setStyleSheet(f"color: {Theme.TEXT_DARK};")
        bottom_layout.addWidget(total_lbl)

        total_val = QLabel(f"{profile.total_time:.2f} s")
        total_val.setFont(QFont("Segoe UI", 10, QFont.Bold))
        total_val.setStyleSheet("color: #4CAF50;")
        bottom_layout.addWidget(total_val)
        
        main_layout.addLayout(bottom_layout)

        # Add vertical stretch so items align nicely to the top
        main_layout.addStretch()

        self.details_scroll.setWidget(scroll_content)

    def _refresh_knowledge_panel(self) -> None:
        """Update the Knowledge tab with current stats from the vector store and knowledge manager."""
        if not hasattr(self, "_kb_grid"):
            return

        services = self._services
        if not hasattr(services, "knowledge_manager"):
            return

        km = services.knowledge_manager
        vs = getattr(services, "vector_store", None)
        es = getattr(services, "embedding_service", None)
        retriever = getattr(services, "retriever", None)

        # Collect stats
        docs = km.get_all_documents()
        total_docs = len(docs)
        indexed_docs = sum(1 for d in docs if d.status == "indexed")
        pending_docs = sum(1 for d in docs if d.status not in ("indexed", "failed"))

        vector_count = vs.get_vector_count() if vs else 0
        chunk_count = vs.get_chunk_count() if vs else 0
        avg_chunk_size = vs.get_average_chunk_size() if vs else 0.0
        db_size = vs.get_database_size() if vs else 0

        model_name = es.model_name() if es else "N/A"
        retrieval_stats = retriever.last_stats if retriever else None

        # Build data rows
        rows: list[tuple[str, str]] = [
            ("Documents (Total)", str(total_docs)),
            ("Documents (Indexed)", str(indexed_docs)),
            ("Documents (Indexing)", str(pending_docs)),
            ("Embedding Model", model_name),
            ("Vector Count", str(vector_count)),
            ("Chunk Count", str(chunk_count)),
            ("Avg Chunk Size", f"{avg_chunk_size:.0f} chars"),
            ("Database Size", f"{db_size / 1024:.1f} KB" if db_size > 0 else "N/A"),
        ]

        if retrieval_stats:
            rows.append(("Top-K", str(retrieval_stats.top_k)))
            rows.append(("Last Query", retrieval_stats.query[:40] + "..." if len(retrieval_stats.query) > 40 else retrieval_stats.query))
            rows.append(("Embedding Duration", f"{retrieval_stats.embedding_duration_ms:.1f} ms"))
            rows.append(("Search Duration", f"{retrieval_stats.search_duration_ms:.1f} ms"))
            rows.append(("Avg Similarity Score", f"{retrieval_stats.average_score:.3f}" if retrieval_stats.results else "N/A"))
            if retrieval_stats.results:
                rows.append(("Retrieved Chunks", str(len(retrieval_stats.results))))
                chunk_ids = ", ".join(str(r.chunk.chunk_index) for r in retrieval_stats.results[:10])
                rows.append(("Chunk IDs", chunk_ids))
                scores = ", ".join(f"{r.score:.3f}" for r in retrieval_stats.results[:10])
                rows.append(("Similarity Scores", scores))

        # Rebuild grid
        old_w = self._kb_grid.parent()
        new_content = QWidget()
        new_content.setStyleSheet("background: transparent;")
        new_grid = QGridLayout(new_content)
        new_grid.setContentsMargins(16, 16, 16, 16)
        new_grid.setVerticalSpacing(10)
        new_grid.setHorizontalSpacing(24)

        for row_idx, (label, value) in enumerate(rows):
            name_lbl = QLabel(label)
            name_lbl.setFont(QFont("Segoe UI", 10))
            name_lbl.setStyleSheet(f"color: {Theme.TEXT_DARK};")
            val_lbl = QLabel(value)
            val_lbl.setFont(QFont("Segoe UI", 10, QFont.Bold))
            val_lbl.setStyleSheet(f"color: {Theme.TEXT_DARK};")
            val_lbl.setAlignment(Qt.AlignRight)
            new_grid.addWidget(name_lbl, row_idx, 0)
            new_grid.addWidget(val_lbl, row_idx, 1)

        # Replace the scroll content
        for i in range(len(rows), self._kb_grid.count()):
            item = self._kb_grid.itemAt(i)
            if item and item.widget():
                item.widget().deleteLater()

        # Swap the grid
        scroll_content = self._kb_grid.parent()
        if scroll_content:
            scroll_content_layout = scroll_content.layout()
            if scroll_content_layout:
                scroll_content_layout.removeItem(self._kb_grid)
        self._kb_grid = new_grid
        if scroll_content:
            scroll_content_layout.addLayout(self._kb_grid)

    def _on_compare_clicked(self) -> None:
        """Show comparison dialog comparing this request's stats to history averages."""
        selected_row = self.req_list.currentRow()
        if selected_row < 0:
            return

        from backend.profiler.performance_profiler import PerformanceProfiler
        profiler = PerformanceProfiler.get_instance()
        
        with profiler._history_lock:
            if selected_row < len(profiler.history):
                profile = profiler.history[len(profiler.history) - 1 - selected_row]
            else:
                return
            history = list(profiler.history)

        if not history:
            return

        # Calculate averages
        avg_total = sum(p.total_time for p in history) / len(history)
        avg_ft = sum(p.first_token_latency for p in history) / len(history)
        avg_speed = sum(p.generation_speed for p in history) / len(history)
        avg_tokens = sum(p.total_tokens for p in history) / len(history)

        comp_dialog = QDialog(self)
        comp_dialog.setWindowTitle("Request Comparison")
        comp_dialog.setMinimumWidth(380)
        comp_dialog.setStyleSheet(f"background-color: {Theme.CREAM}; color: {Theme.TEXT_DARK};")
        
        layout = QVBoxLayout(comp_dialog)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(14)

        title = QLabel(f"Comparing Request #{profile.request_num} with History Averages")
        title.setFont(QFont("Segoe UI", 11, QFont.Bold))
        title.setStyleSheet(f"color: {Theme.TEXT_DARK};")
        layout.addWidget(title)

        grid = QGridLayout()
        grid.setSpacing(10)

        headers = ["Metric", f"Req #{profile.request_num}", "History Avg", "Difference"]
        for col, h in enumerate(headers):
            lbl = QLabel(h)
            lbl.setFont(QFont("Segoe UI", 9, QFont.Bold))
            lbl.setStyleSheet(f"color: {Theme.TEXT_MID};")
            grid.addWidget(lbl, 0, col)

        metrics = [
            ("Latency", profile.total_time, avg_total, "s"),
            ("First Token", profile.first_token_latency, avg_ft, "s"),
            ("Gen Speed", profile.generation_speed, avg_speed, "t/s"),
            ("Total Tokens", profile.total_tokens, avg_tokens, "t"),
        ]

        for row, (name, val, avg, unit) in enumerate(metrics, start=1):
            name_lbl = QLabel(name)
            name_lbl.setFont(QFont("Segoe UI", 9))
            name_lbl.setStyleSheet(f"color: {Theme.TEXT_DARK};")
            grid.addWidget(name_lbl, row, 0)
            
            val_lbl = QLabel(f"{val:.2f} {unit}" if isinstance(val, float) else f"{int(val)} {unit}")
            val_lbl.setFont(QFont("Segoe UI", 9, QFont.Bold))
            val_lbl.setStyleSheet(f"color: {Theme.TEXT_DARK};")
            grid.addWidget(val_lbl, row, 1)

            avg_lbl = QLabel(f"{avg:.2f} {unit}" if isinstance(avg, float) else f"{int(avg)} {unit}")
            avg_lbl.setFont(QFont("Segoe UI", 9))
            avg_lbl.setStyleSheet(f"color: {Theme.TEXT_DARK};")
            grid.addWidget(avg_lbl, row, 2)

            diff = val - avg
            pct = (diff / avg * 100) if avg > 0 else 0
            if diff < 0:
                diff_text = f"{diff:.2f} ({pct:.1f}%)" if isinstance(diff, float) else f"{int(diff)} ({pct:.1f}%)"
                diff_color = "#4CAF50" if name in ("Latency", "First Token") else "#EF5350"
            else:
                diff_text = f"+{diff:.2f} (+{pct:.1f}%)" if isinstance(diff, float) else f"+{int(diff)} (+{pct:.1f}%)"
                diff_color = "#EF5350" if name in ("Latency", "First Token") else "#4CAF50"

            diff_lbl = QLabel(diff_text)
            diff_lbl.setFont(QFont("Segoe UI", 9, QFont.Bold))
            diff_lbl.setStyleSheet(f"color: {diff_color};")
            grid.addWidget(diff_lbl, row, 3)

        layout.addLayout(grid)

        # Close button
        btn = QPushButton("Close")
        btn.clicked.connect(comp_dialog.accept)
        btn.setStyleSheet(f"""
            QPushButton {{
                background: {Theme.BTN_BG};
                color: {Theme.TEXT_DARK};
                border: 1px solid {Theme.BORDER};
                border-radius: 4px;
                padding: 6px 14px;
            }}
            QPushButton:hover {{ background: {Theme.BTN_HOVER}; }}
        """)
        layout.addWidget(btn, alignment=Qt.AlignRight)

        comp_dialog.exec()
