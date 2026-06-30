from PySide6.QtCore import QPoint, Qt, QTimer
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from core.themes import Theme


class TitleBar(QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.setFixedHeight(42)
        self._drag_pos = QPoint()
        self._build_ui(parent)

    def _build_ui(self, parent):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 0, 8, 0)
        layout.setSpacing(4)

        self._title_label = QLabel("EGGMAN")
        self._title_label.setFont(Theme.FONT_TITLE)
        layout.addWidget(self._title_label)

        layout.addStretch()

        self._min_btn = self._make_ctrl_btn("—", "min")
        self._min_btn.clicked.connect(parent.showMinimized)
        layout.addWidget(self._min_btn)

        self._cls_btn = self._make_ctrl_btn("✕", "cls")
        self._cls_btn.clicked.connect(parent.close)
        layout.addWidget(self._cls_btn)

        self.apply_theme()

    def _make_ctrl_btn(self, symbol: str, kind: str) -> QPushButton:
        btn = QPushButton(symbol)
        btn.setFixedSize(22, 22)
        btn.setFont(QFont("Segoe UI", 9))
        btn.setCursor(Qt.PointingHandCursor)
        btn._kind = kind
        return btn

    def apply_theme(self):
        self.setStyleSheet(f"background: {Theme.CREAM_DARK};")
        self._title_label.setStyleSheet(
            f"color: {Theme.TEXT_DARK}; background: transparent;"
        )
        for btn in (self._min_btn, self._cls_btn):
            kind = btn._kind
            hover = Theme.CTRL_HOVER_MIN if kind == "min" else Theme.CTRL_HOVER_CLS
            press = Theme.CTRL_PRESS_MIN if kind == "min" else Theme.CTRL_PRESS_CLS
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: transparent; color: {Theme.TEXT_MID};
                    border: none; border-radius: 11px;
                }}
                QPushButton:hover {{ background: {hover}; color: {Theme.TEXT_DARK}; }}
                QPushButton:pressed {{ background: {press}; }}
            """)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_pos = (
                event.globalPosition().toPoint()
                - self.window().frameGeometry().topLeft()
            )

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton and not self._drag_pos.isNull():
            self.window().move(event.globalPosition().toPoint() - self._drag_pos)


class MessageBubble(QWidget):
    def __init__(self, sender: str, text: str, timestamp: str, parent=None):
        super().__init__(parent)
        self._is_user = (sender == "user")

        row = QHBoxLayout(self)
        row.setContentsMargins(8, 2, 8, 2)
        row.setSpacing(0)

        self._bubble = QWidget()
        self._bubble.setObjectName("bubble")

        bubble_layout = QVBoxLayout(self._bubble)
        bubble_layout.setContentsMargins(10, 6, 10, 6)
        bubble_layout.setSpacing(1)

        self._sender_label = QLabel("You" if self._is_user else "EggMan")
        self._sender_label.setFont(Theme.FONT_SENDER)
        bubble_layout.addWidget(self._sender_label)

        self._msg_label = QLabel(text)
        self._msg_label.setFont(Theme.FONT_CHAT)
        self._msg_label.setWordWrap(True)
        self._msg_label.setMaximumWidth(int(Theme.WIN_W * 0.75))
        self._msg_label.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Preferred)
        bubble_layout.addWidget(self._msg_label)

        self._ts_label = QLabel(timestamp)
        self._ts_label.setFont(Theme.FONT_TIMESTAMP)
        self._ts_label.setAlignment(Qt.AlignRight)
        bubble_layout.addWidget(self._ts_label)

        if self._is_user:
            row.addStretch()
            row.addWidget(self._bubble)
        else:
            row.addWidget(self._bubble)
            row.addStretch()

        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        self.apply_theme()

    def apply_theme(self):
        bg = Theme.BUBBLE_USER if self._is_user else Theme.BUBBLE_EGG
        self._bubble.setStyleSheet(f"""
            QWidget#bubble {{
                background: {bg};
                border-radius: {Theme.BUBBLE_RADIUS}px;
            }}
        """)
        self._sender_label.setStyleSheet(
            f"color: {Theme.TEXT_MID}; background: transparent;"
        )
        self._msg_label.setStyleSheet(
            f"color: {Theme.TEXT_DARK}; background: transparent;"
        )
        self._ts_label.setStyleSheet(
            f"color: {Theme.TEXT_FAINT}; background: transparent;"
        )


class ChatDisplay(QScrollArea):
    def __init__(self):
        super().__init__()
        self.setFrameShape(QFrame.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setWidgetResizable(True)

        self._inner = QWidget()
        self._layout = QVBoxLayout(self._inner)
        self._layout.setContentsMargins(10, 8, 10, 16)
        self._layout.setSpacing(4)

        self._empty_label = QLabel(Theme.EMPTY_STATE_MSG)
        self._empty_label.setFont(Theme.FONT_EMPTY)
        self._empty_label.setAlignment(Qt.AlignCenter)
        self._empty_label.setWordWrap(True)
        self._layout.addStretch()
        self._layout.addWidget(self._empty_label, alignment=Qt.AlignCenter)
        self._layout.addStretch()

        self.setWidget(self._inner)
        self._message_count = 0
        self._history: list[tuple[str, str, str]] = []

        self.apply_theme()

    def apply_theme(self):
        self.setStyleSheet(f"""
            QScrollArea {{ background: transparent; border: none; }}
            QScrollBar:vertical {{ width: 6px; background: transparent; }}
            QScrollBar::handle:vertical {{
                background: {Theme.BORDER}; border-radius: 3px; min-height: 20px;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
        """)
        self._inner.setStyleSheet("background: transparent;")
        self._empty_label.setStyleSheet(
            f"color: {Theme.TEXT_FAINT}; background: transparent;"
        )
        for i in range(self._layout.count()):
            item = self._layout.itemAt(i)
            if item and isinstance(item.widget(), MessageBubble):
                item.widget().apply_theme()

    def append_message(self, sender: str, text: str, timestamp: str) -> "MessageBubble":
        if self._message_count == 0:
            self._empty_label.hide()
            while self._layout.count() > 0:
                item = self._layout.takeAt(0)
                if item.widget():
                    item.widget().setParent(None)
            self._layout.addStretch()

        self._history.append((sender, text, timestamp))
        bubble = MessageBubble(sender, text, timestamp)
        count = self._layout.count()
        self._layout.insertWidget(count - 1, bubble)
        self._message_count += 1

        if self._message_count > Theme.MAX_MESSAGES:
            self._remove_oldest_bubble()

        QTimer.singleShot(0, self._scroll_to_bottom)
        return bubble

    def clear_messages(self):
        while self._layout.count() > 0:
            item = self._layout.takeAt(0)
            if item.widget():
                item.widget().setParent(None)

        self._history.clear()
        self._message_count = 0

        self._empty_label.show()
        self._layout.addStretch()
        self._layout.addWidget(self._empty_label, alignment=Qt.AlignCenter)
        self._layout.addStretch()

    def get_history(self) -> list:
        return list(self._history)

    def _remove_oldest_bubble(self):
        if self._layout.count() > 1:
            item = self._layout.itemAt(0)
            if item and item.widget():
                w = item.widget()
                self._layout.removeWidget(w)
                w.deleteLater()
                self._message_count -= 1
                if self._history:
                    self._history.pop(0)

    def remove_last_bubble(self):
        count = self._layout.count()
        if count < 2:
            return
        item = self._layout.itemAt(count - 2)
        if item and item.widget():
            w = item.widget()
            self._layout.removeWidget(w)
            w.deleteLater()
            self._message_count -= 1
            if self._history:
                self._history.pop()

    def replace_last_bubble(self, sender: str, text: str, timestamp: str):
        self.remove_last_bubble()
        self.append_message(sender, text, timestamp)

    def _scroll_to_bottom(self):
        self.verticalScrollBar().setValue(self.verticalScrollBar().maximum())


class InputBar(QWidget):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setFixedHeight(54)
        self._build_ui()

    def _build_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(8)

        self.entry = QLineEdit()
        self.entry.setPlaceholderText("Say something...")
        self.entry.setFont(Theme.FONT_INPUT)
        self.entry.setFixedHeight(34)
        layout.addWidget(self.entry, stretch=1)

        self.send_btn = self._make_icon_btn("➤")
        self.mic_btn = self._make_icon_btn("🎤")
        self.screenshot_btn = self._make_icon_btn("📷")
        layout.addWidget(self.mic_btn)
        layout.addWidget(self.send_btn)
        layout.addWidget(self.screenshot_btn)

        self._icon_btns = [self.mic_btn, self.send_btn, self.screenshot_btn]
        self._default_placeholder = "Say something..."
        self._voice_listening = False
        self.apply_theme()

    def _make_icon_btn(self, icon: str) -> QPushButton:
        btn = QPushButton(icon)
        btn.setFixedSize(34, 34)
        btn.setFont(Theme.FONT_BTN)
        btn.setCursor(Qt.PointingHandCursor)
        return btn

    def apply_theme(self):
        self.setStyleSheet("background: transparent;")
        self.entry.setStyleSheet(f"""
            QLineEdit {{
                background: {Theme.INPUT_BG}; color: {Theme.TEXT_DARK};
                border: 1.5px solid {Theme.BORDER}; border-radius: 17px; padding: 0 14px;
            }}
            QLineEdit:focus {{ border: 1.5px solid {Theme.TEXT_MID}; }}
        """)
        btn_ss = f"""
            QPushButton {{
                background: {Theme.BTN_BG}; color: {Theme.TEXT_DARK};
                border: none; border-radius: 17px;
            }}
            QPushButton:hover {{ background: {Theme.BTN_HOVER}; }}
            QPushButton:pressed {{ background: {Theme.BTN_PRESS}; }}
        """
        for btn in self._icon_btns:
            btn.setStyleSheet(btn_ss)
        if hasattr(self, "mic_btn"):
            self._apply_mic_style(listening=self._voice_listening)

    def set_voice_listening(self, listening: bool) -> None:
        self._voice_listening = listening
        self._apply_mic_style(listening=listening)
        if listening:
            self.entry.setPlaceholderText("Listening...")
        elif self.entry.placeholderText() == "Listening...":
            self.entry.setPlaceholderText(self._default_placeholder)

    def set_voice_processing(self, processing: bool) -> None:
        if processing:
            self.entry.setPlaceholderText("Transcribing...")
        elif self.entry.placeholderText() == "Transcribing...":
            self.entry.setPlaceholderText(self._default_placeholder)

    def set_voice_controls_enabled(self, enabled: bool) -> None:
        self.mic_btn.setEnabled(enabled)

    def _apply_mic_style(self, listening: bool) -> None:
        if listening:
            self.mic_btn.setText("●")
            self.mic_btn.setStyleSheet(f"""
                QPushButton {{
                    background: #E0B0B0; color: #8B0000;
                    border: 1.5px solid #C89090; border-radius: 17px;
                }}
                QPushButton:hover {{ background: #D8A0A0; }}
                QPushButton:pressed {{ background: #C89090; }}
            """)
        else:
            self.mic_btn.setText("🎤")
            btn_ss = f"""
                QPushButton {{
                    background: {Theme.BTN_BG}; color: {Theme.TEXT_DARK};
                    border: none; border-radius: 17px;
                }}
                QPushButton:hover {{ background: {Theme.BTN_HOVER}; }}
                QPushButton:pressed {{ background: {Theme.BTN_PRESS}; }}
            """
            self.mic_btn.setStyleSheet(btn_ss)
