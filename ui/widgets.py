from PySide6.QtCore import QPoint, Qt, QTimer, QRect, QSize, Property, QParallelAnimationGroup, QPropertyAnimation
from PySide6.QtGui import QFont, QFontMetrics, QPainter, QColor
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
    QLayout,
)

from core.themes import Theme


class FlowLayout(QLayout):
    """Layout that arranges widgets horizontally and wraps them line-by-line."""

    def __init__(self, parent=None, margin=0, hspacing=0, vspacing=3):
        super().__init__(parent)
        self._items = []
        self._hspacing = hspacing
        self._vspacing = vspacing
        self.setContentsMargins(margin, margin, margin, margin)

    def __del__(self):
        item = self.takeAt(0)
        while item:
            item = self.takeAt(0)

    def addItem(self, item):
        self._items.append(item)

    def count(self):
        return len(self._items)

    def itemAt(self, index):
        if 0 <= index < len(self._items):
            return self._items[index]
        return None

    def takeAt(self, index):
        if 0 <= index < len(self._items):
            return self._items.pop(index)
        return None

    def expandingDirections(self):
        return Qt.Orientations(0)

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return self._do_layout(QRect(0, 0, width, 0), True)

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self._do_layout(rect, False)

    def sizeHint(self):
        # Calculate total width if laid out on a single line
        total_w = 0
        default_line_height = QFontMetrics(Theme.FONT_CHAT).lineSpacing()
        has_newline = False
        for item in self._items:
            widget = item.widget()
            if widget:
                if getattr(widget, "is_newline", False):
                    has_newline = True
                else:
                    total_w += item.sizeHint().width()
        
        # Determine maximum allowed width based on current window size
        parent_widget = self.parentWidget()
        if parent_widget:
            top_window = parent_widget.window()
            win_width = top_window.width() if top_window else Theme.WIN_W
        else:
            win_width = Theme.WIN_W
            
        max_allowed_w = int(win_width * 0.72)
        margin = self.contentsMargins().left()
        
        if total_w < max_allowed_w and not has_newline:
            # Short text: shrink-to-fit width
            return QSize(total_w + 2 * margin, default_line_height + 2 * margin)
        else:
            # Long text: wrap up to max_allowed_w
            h = self.heightForWidth(max_allowed_w)
            return QSize(max_allowed_w, h)

    def minimumSize(self):
        return self.sizeHint()

    def _do_layout(self, rect, test_only):
        x = rect.x()
        y = rect.y()
        line_height = 0
        hspacing = self._hspacing
        vspacing = self._vspacing
        default_line_height = QFontMetrics(Theme.FONT_CHAT).lineSpacing()

        for item in self._items:
            widget = item.widget()
            if widget is None:
                continue

            # Force line break on NewlineWidget
            if getattr(widget, "is_newline", False):
                x = rect.x()
                y = y + (line_height if line_height > 0 else default_line_height) + vspacing
                line_height = 0
                continue

            space_x = hspacing
            space_y = vspacing
            item_w = item.sizeHint().width()
            item_h = item.sizeHint().height()

            next_x = x + item_w + space_x
            if next_x - space_x > rect.right() and line_height > 0:
                x = rect.x()
                y = y + line_height + space_y
                next_x = x + item_w + space_x
                line_height = 0

            if not test_only:
                item.setGeometry(QRect(QPoint(x, y), QSize(item_w, item_h)))

            x = next_x
            line_height = max(line_height, item_h)

        return y + line_height - rect.y()


class NewlineWidget(QWidget):
    """Special zero-size widget used by FlowLayout to force newlines."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.is_newline = True
        self.setFixedSize(0, 0)


class AnimatedWordLabel(QWidget):
    """Label rendering a single word/token with entry animations (subtle fade + upward motion)."""

    def __init__(self, text: str, font: QFont, parent=None):
        super().__init__(parent)
        self.text = text
        self.font = font
        self._opacity = 0.0
        self._offset_y = 6.0

        fm = QFontMetrics(self.font)
        self._text_size = fm.size(Qt.TextSingleLine, self.text)
        w = self._text_size.width()
        if text == " ":
            w = fm.horizontalAdvance(" ")
        self.setFixedSize(max(w, 1), max(self._text_size.height(), 1))

    @Property(float)
    def opacity(self) -> float:
        return self._opacity

    @opacity.setter
    def opacity(self, val: float):
        self._opacity = val
        self.update()

    @Property(float)
    def offset_y(self) -> float:
        return self._offset_y

    @offset_y.setter
    def offset_y(self, val: float):
        self._offset_y = val
        self.update()

    def show_instantly(self):
        self._opacity = 1.0
        self._offset_y = 0.0
        self.update()

    def start_animation(self):
        self.anim_group = QParallelAnimationGroup(self)

        anim_op = QPropertyAnimation(self, b"opacity")
        anim_op.setDuration(150)
        anim_op.setStartValue(0.0)
        anim_op.setEndValue(1.0)

        anim_off = QPropertyAnimation(self, b"offset_y")
        anim_off.setDuration(150)
        anim_off.setStartValue(6.0)
        anim_off.setEndValue(0.0)

        self.anim_group.addAnimation(anim_op)
        self.anim_group.addAnimation(anim_off)
        self.anim_group.start()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setOpacity(self._opacity)
        painter.setFont(self.font)
        painter.setPen(QColor(Theme.TEXT_DARK))
        
        fm = QFontMetrics(self.font)
        y = self.height() - fm.descent() - int(self._offset_y)
        painter.drawText(0, y, self.text)


class MessageTextContainer(QWidget):
    """FlowLayout-based container that splits text into animatable tokens."""

    def __init__(self, text: str, is_streamed: bool = False, parent=None):
        super().__init__(parent)
        self.layout = FlowLayout(self, margin=0, hspacing=0, vspacing=3)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        
        if text:
            self.add_text(text, animate=is_streamed)

    def add_text(self, text: str, animate: bool = True):
        tokens = self._tokenize(text)
        for token in tokens:
            if token == "\n":
                w = NewlineWidget(self)
                self.layout.addWidget(w)
            else:
                w = AnimatedWordLabel(token, Theme.FONT_CHAT, self)
                self.layout.addWidget(w)
                if animate:
                    w.start_animation()
                else:
                    w.show_instantly()
        self.updateGeometry()

    def _tokenize(self, text: str) -> list[str]:
        tokens = []
        current = ""
        for char in text:
            if char in (' ', '\n'):
                if current:
                    tokens.append(current)
                    current = ""
                tokens.append(char)
            else:
                current += char
        if current:
            tokens.append(current)
        return tokens



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
    def __init__(self, sender: str, text: str, timestamp: str, is_streamed: bool = False, parent=None):
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

        # Container for text wrapping and token animation
        self._text_container = MessageTextContainer(text, is_streamed=is_streamed, parent=self)
        bubble_layout.addWidget(self._text_container)

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

    def add_streaming_text(self, text: str):
        """Append a streaming chunk to the message bubble container."""
        if self._text_container:
            self._text_container.add_text(text, animate=True)

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

    def append_message(self, sender: str, text: str, timestamp: str, is_streamed: bool = False) -> "MessageBubble":
        if self._message_count == 0:
            self._empty_label.hide()
            while self._layout.count() > 0:
                item = self._layout.takeAt(0)
                if item.widget():
                    item.widget().setParent(None)
            self._layout.addStretch()

        self._history.append((sender, text, timestamp))
        bubble = MessageBubble(sender, text, timestamp, is_streamed=is_streamed)
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
