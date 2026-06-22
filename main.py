"""
EggMan v0.0.9 — Egg Avatar + Mood System (PySide6)
Better icons, improved title bar, EggPanel with fake mood states.
No AI, no backend, no database.
"""

import sys
import random
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QFrame,
    QScrollArea, QSizePolicy,
)
from PySide6.QtCore import Qt, QPoint, QTimer
from PySide6.QtGui import QFont


# ──────────────────────────────────────────────────────────────
# THEME  — all colours and sizes in one place
# ──────────────────────────────────────────────────────────────
class Theme:
    # Palette
    CREAM           = "#F5F0E8"
    CREAM_DARK      = "#EDE7D9"
    CREAM_DEEPER    = "#E4DDD0"   # Panel background — one step darker than title bar
    BORDER          = "#C8BFA8"
    TEXT_DARK       = "#2C2416"
    TEXT_MID        = "#8C7B65"
    INPUT_BG        = "#FFFFFF"
    BTN_BG          = "#DDD5C0"
    BTN_HOVER       = "#CEC5AF"
    BTN_PRESS       = "#BDB49F"

    # Title bar control buttons
    CTRL_HOVER_MIN  = "#C8E0C8"   # Soft green tint for minimize hover
    CTRL_HOVER_CLS  = "#E0B0B0"   # Soft red tint for close hover
    CTRL_PRESS_MIN  = "#A8C8A8"
    CTRL_PRESS_CLS  = "#C89090"

    # Bubble colours
    BUBBLE_USER     = "#E2D9C8"
    BUBBLE_EGG      = "#EDE7D9"
    BUBBLE_RADIUS   = 14

    # Mood colours — used by EggPanel mood label
    MOOD_COLOURS = {
        "Happy":    "#8B7355",
        "Sleepy":   "#7A8FA6",
        "Curious":  "#8B6914",
        "Thinking": "#6B7B5A",
        "Excited":  "#A0522D",
        "Calm":     "#7B9B8A",
    }

    # Typography
    FONT_TITLE      = QFont("Georgia",  13, QFont.Bold)
    FONT_CHAT       = QFont("Segoe UI", 10)
    FONT_SENDER     = QFont("Segoe UI",  8, QFont.Bold)
    FONT_INPUT      = QFont("Segoe UI", 10)
    FONT_BTN        = QFont("Segoe UI", 13)   # slightly larger for cleaner symbols
    FONT_MOOD       = QFont("Segoe UI",  9, QFont.Bold)
    FONT_AVATAR     = QFont("Segoe UI", 32)   # emoji avatar size

    # Layout
    WIN_W           = 270
    WIN_H           = 600          # taller to fit EggPanel
    RADIUS          = 18
    PANEL_H         = 100          # EggPanel fixed height
    AVATAR_SIZE     = 48           # avatar label pixel size (used for min-height)


# ──────────────────────────────────────────────────────────────
# CONVERSATION ENGINE  — unchanged from v0.0.3
# ──────────────────────────────────────────────────────────────
class ConversationEngine:
    _REPLIES = [
        "Hi!",
        "Nice to see you.",
        "I'm just an egg.",
        "Eggcellent question.",
        "Interesting!",
        "Tell me more.",
        "I'm thinking... or maybe not.",
        "Yolk's on you.",
        "That's shell-shocking.",
    ]

    def get_reply(self, user_message: str) -> str:
        return random.choice(self._REPLIES)


# ──────────────────────────────────────────────────────────────
# TITLE BAR  — v0.0.7: minimize button added, layout improved
# Layout: [EGGMAN label · stretch · minimize · close]
# Drag is still attached to this widget only.
# ──────────────────────────────────────────────────────────────
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

        # Title — centred by the stretch on its right
        title = QLabel("EGGMAN")
        title.setFont(Theme.FONT_TITLE)
        title.setStyleSheet(f"color: {Theme.TEXT_DARK}; background: transparent;")
        layout.addWidget(title)

        layout.addStretch()

        # Minimize button
        self._min_btn = self._make_ctrl_btn("—", "min")
        self._min_btn.clicked.connect(parent.showMinimized)
        layout.addWidget(self._min_btn)

        # Close button
        self._cls_btn = self._make_ctrl_btn("✕", "cls")
        self._cls_btn.clicked.connect(parent.close)
        layout.addWidget(self._cls_btn)

        self.setStyleSheet(f"background: {Theme.CREAM_DARK};")

    def _make_ctrl_btn(self, symbol: str, kind: str) -> QPushButton:
        """Builds a small window-control button.
        kind='min' gets green hover; kind='cls' gets red hover."""
        hover  = Theme.CTRL_HOVER_MIN  if kind == "min" else Theme.CTRL_HOVER_CLS
        press  = Theme.CTRL_PRESS_MIN  if kind == "min" else Theme.CTRL_PRESS_CLS

        btn = QPushButton(symbol)
        btn.setFixedSize(22, 22)
        btn.setFont(QFont("Segoe UI", 9))
        btn.setCursor(Qt.PointingHandCursor)
        btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {Theme.TEXT_MID};
                border: none;
                border-radius: 11px;
            }}
            QPushButton:hover {{
                background: {hover};
                color: {Theme.TEXT_DARK};
            }}
            QPushButton:pressed {{
                background: {press};
            }}
        """)
        return btn

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.window().frameGeometry().topLeft()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton and not self._drag_pos.isNull():
            self.window().move(event.globalPosition().toPoint() - self._drag_pos)


# ──────────────────────────────────────────────────────────────
# MESSAGE BUBBLE  — NEW in v0.0.4
# A single chat bubble for one message.
# sender: "user" or "egg" — controls colour and alignment.
# ──────────────────────────────────────────────────────────────
class MessageBubble(QWidget):
    def __init__(self, sender: str, text: str, parent=None):
        super().__init__(parent)

        is_user = (sender == "user")

        # Outer row: pushes the bubble left or right using a spacer
        row = QHBoxLayout(self)
        row.setContentsMargins(8, 3, 8, 3)
        row.setSpacing(0)

        # The bubble card itself
        bubble = QWidget()
        bubble.setObjectName("bubble")

        bg_color = Theme.BUBBLE_USER if is_user else Theme.BUBBLE_EGG
        r = Theme.BUBBLE_RADIUS
        bubble.setStyleSheet(f"""
            QWidget#bubble {{
                background: {bg_color};
                border-radius: {r}px;
            }}
        """)

        # Layout inside the bubble: optional sender label + message text
        bubble_layout = QVBoxLayout(bubble)
        bubble_layout.setContentsMargins(10, 7, 10, 7)
        bubble_layout.setSpacing(2)

        sender_label = QLabel("You" if is_user else "EggMan")
        sender_label.setFont(Theme.FONT_SENDER)
        sender_label.setStyleSheet(
            f"color: {Theme.TEXT_MID}; background: transparent;"
        )
        bubble_layout.addWidget(sender_label)

        # QLabel for message text — word wrap enabled so long text wraps
        # instead of stretching the bubble off-screen.
        msg_label = QLabel(text)
        msg_label.setFont(Theme.FONT_CHAT)
        msg_label.setStyleSheet(f"color: {Theme.TEXT_DARK}; background: transparent;")
        msg_label.setWordWrap(True)

        # Cap bubble width at 75% of the window so it never fills the full row.
        # The label grows in height to fit wrapped text automatically.
        msg_label.setMaximumWidth(int(Theme.WIN_W * 0.75))
        bubble_layout.addWidget(msg_label)

        # Align: spacer before bubble = right; spacer after = left
        if is_user:
            row.addStretch()
            row.addWidget(bubble)
        else:
            row.addWidget(bubble)
            row.addStretch()

        # Prevent the whole row widget from expanding to window width vertically
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)


# ──────────────────────────────────────────────────────────────
# EGG PANEL  — NEW in v0.0.8/0.0.9
# Sits between TitleBar and ChatDisplay.
# Shows an emoji avatar and the current mood label.
# set_mood() is the only public method — called from EggManWindow.
# ──────────────────────────────────────────────────────────────
class EggPanel(QWidget):
    # All available moods — randomly picked after each EggMan reply
    MOODS = ["Happy", "Sleepy", "Curious", "Thinking", "Excited", "Calm"]

    # Emoji avatar for each mood — same egg, different expression
    _AVATARS = {
        "Happy":    "🥚😊",
        "Sleepy":   "🥚😴",
        "Curious":  "🥚🤔",
        "Thinking": "🥚💭",
        "Excited":  "🥚✨",
        "Calm":     "🥚😌",
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(Theme.PANEL_H)
        self._build_ui()
        self.set_mood("Happy")   # Default starting mood

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 10, 0, 10)
        layout.setSpacing(4)
        layout.setAlignment(Qt.AlignHCenter)

        # Avatar — large emoji, centred
        self._avatar_label = QLabel()
        self._avatar_label.setFont(Theme.FONT_AVATAR)
        self._avatar_label.setAlignment(Qt.AlignCenter)
        self._avatar_label.setStyleSheet("background: transparent;")
        layout.addWidget(self._avatar_label)

        # Mood label — small coloured text below avatar
        self._mood_label = QLabel()
        self._mood_label.setFont(Theme.FONT_MOOD)
        self._mood_label.setAlignment(Qt.AlignCenter)
        self._mood_label.setStyleSheet("background: transparent;")
        layout.addWidget(self._mood_label)

        self.setStyleSheet(f"background: {Theme.CREAM_DEEPER};")

    def set_mood(self, mood: str):
        """Updates avatar emoji and mood label. Called from EggManWindow after each reply."""
        colour = Theme.MOOD_COLOURS.get(mood, Theme.TEXT_MID)
        self._avatar_label.setText(self._AVATARS.get(mood, "🥚"))
        self._mood_label.setText(mood)
        self._mood_label.setStyleSheet(f"color: {colour}; background: transparent;")


# ──────────────────────────────────────────────────────────────
# CHAT DISPLAY  — QScrollArea holding MessageBubble widgets (v0.0.4+)
# Now a QScrollArea holding a QVBoxLayout of MessageBubble widgets.
# The public API (append_message) is unchanged so EggManWindow works as-is.
# ──────────────────────────────────────────────────────────────
class ChatDisplay(QScrollArea):
    def __init__(self):
        super().__init__()
        self.setFrameShape(QFrame.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setWidgetResizable(True)   # Inner widget resizes with the scroll area

        # Thin scrollbar styling — matches v0.0.3 look
        self.setStyleSheet(f"""
            QScrollArea {{
                background: {Theme.CREAM};
                border: none;
            }}
            QScrollBar:vertical {{
                width: 6px;
                background: {Theme.CREAM};
            }}
            QScrollBar::handle:vertical {{
                background: {Theme.BORDER};
                border-radius: 3px;
                min-height: 20px;
            }}
            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
        """)

        # Inner container widget that holds all the bubbles
        self._inner = QWidget()
        self._inner.setStyleSheet(f"background: {Theme.CREAM};")
        self._layout = QVBoxLayout(self._inner)
        self._layout.setContentsMargins(0, 8, 0, 8)
        self._layout.setSpacing(4)
        self._layout.addStretch()   # Pushes bubbles to the bottom initially

        self.setWidget(self._inner)

    def append_message(self, sender: str, text: str) -> "MessageBubble":
        """Creates a MessageBubble, inserts it above the bottom stretch spacer,
        and schedules a scroll. Returns the bubble so callers can hold a ref."""
        bubble = MessageBubble(sender, text)
        count = self._layout.count()
        self._layout.insertWidget(count - 1, bubble)
        QTimer.singleShot(0, self._scroll_to_bottom)
        return bubble

    def remove_last_bubble(self):
        """Removes the most recently added bubble (used to pull the typing indicator).
        Layout order is: [stretch, bubble0, ..., bubbleN] — last widget is at count-2."""
        count = self._layout.count()
        if count < 2:
            return
        item = self._layout.itemAt(count - 2)
        if item and item.widget():
            widget = item.widget()
            self._layout.removeWidget(widget)
            widget.deleteLater()

    def replace_last_bubble(self, sender: str, text: str):
        """Removes the typing indicator and inserts the real reply in its place."""
        self.remove_last_bubble()
        self.append_message(sender, text)

    def _scroll_to_bottom(self):
        self.verticalScrollBar().setValue(self.verticalScrollBar().maximum())


# ──────────────────────────────────────────────────────────────
# INPUT BAR  — unchanged from v0.0.3
# ──────────────────────────────────────────────────────────────
class InputBar(QWidget):
    def __init__(self):
        super().__init__()
        self.setFixedHeight(54)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(8)

        self.entry = QLineEdit()
        self.entry.setPlaceholderText("Say something...")
        self.entry.setFont(Theme.FONT_INPUT)
        self.entry.setFixedHeight(34)
        self.entry.setStyleSheet(f"""
            QLineEdit {{
                background: {Theme.INPUT_BG};
                color: {Theme.TEXT_DARK};
                border: 1.5px solid {Theme.BORDER};
                border-radius: 17px;
                padding: 0 14px;
            }}
            QLineEdit:focus {{
                border: 1.5px solid {Theme.TEXT_MID};
            }}
        """)
        layout.addWidget(self.entry, stretch=1)

        self.send_btn = self._make_icon_btn("➤")        # solid filled arrow — cleaner send icon
        layout.addWidget(self.send_btn)

        self.screenshot_btn = self._make_icon_btn("⊡")  # square-dot — suggests capture/frame
        layout.addWidget(self.screenshot_btn)

        self.setStyleSheet(f"background: {Theme.CREAM_DARK};")

    def _make_icon_btn(self, icon: str) -> QPushButton:
        btn = QPushButton(icon)
        btn.setFixedSize(34, 34)
        btn.setFont(Theme.FONT_BTN)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setStyleSheet(f"""
            QPushButton {{
                background: {Theme.BTN_BG};
                color: {Theme.TEXT_DARK};
                border: none;
                border-radius: 17px;
            }}
            QPushButton:hover {{
                background: {Theme.BTN_HOVER};
            }}
            QPushButton:pressed {{
                background: {Theme.BTN_PRESS};
            }}
        """)
        return btn


# ──────────────────────────────────────────────────────────────
# MAIN WINDOW  — v0.0.9: EggPanel inserted, mood updated on reply
# ──────────────────────────────────────────────────────────────
class EggManWindow(QWidget):
    TYPING_DELAY_MS = 1000

    def __init__(self):
        super().__init__()

        self.setWindowTitle("EggMan")
        self.setWindowFlags(
            Qt.FramelessWindowHint |
            Qt.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(Theme.WIN_W, Theme.WIN_H)

        screen = QApplication.primaryScreen().availableGeometry()
        self.move(screen.right() - Theme.WIN_W - 40, screen.top() + 60)

        self._engine = ConversationEngine()
        self._pending_reply: str = ""

        self._build_ui()
        self._connect_signals()

    def _build_ui(self):
        self._container = QWidget(self)
        self._container.setObjectName("container")
        self._container.setGeometry(0, 0, Theme.WIN_W, Theme.WIN_H)
        self._container.setStyleSheet(f"""
            QWidget#container {{
                background: {Theme.CREAM};
                border: 1.5px solid {Theme.BORDER};
                border-radius: {Theme.RADIUS}px;
            }}
        """)

        root_layout = QVBoxLayout(self._container)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # 1. Title bar
        self._title_bar = TitleBar(self)
        root_layout.addWidget(self._title_bar)

        # Divider below title
        root_layout.addWidget(self._make_divider())

        # 2. Egg panel (avatar + mood)
        self._egg_panel = EggPanel()
        root_layout.addWidget(self._egg_panel)

        # Divider below egg panel
        root_layout.addWidget(self._make_divider())

        # 3. Chat display (fills remaining space)
        self._chat = ChatDisplay()
        root_layout.addWidget(self._chat, stretch=1)

        # 4. Input bar
        self._input_bar = InputBar()
        root_layout.addWidget(self._input_bar)

    def _make_divider(self) -> QFrame:
        """Thin horizontal rule used between sections."""
        d = QFrame()
        d.setFrameShape(QFrame.HLine)
        d.setFixedHeight(1)
        d.setStyleSheet(f"background: {Theme.BORDER}; border: none;")
        return d

    def _connect_signals(self):
        self._input_bar.send_btn.clicked.connect(self._on_send)
        self._input_bar.entry.returnPressed.connect(self._on_send)

    # ── Send flow ────────────────────────────────────────────────

    def _on_send(self):
        """Entry point: post user message then hand off to typing indicator."""
        text = self._input_bar.entry.text().strip()
        if not text:
            return

        self._input_bar.entry.clear()
        self._chat.append_message("user", text)

        self._pending_reply = self._engine.get_reply(text)
        self._start_typing()

    def _start_typing(self):
        """Shows '...' bubble and locks input while EggMan thinks."""
        self._set_input_enabled(False)
        self._chat.append_message("egg", "...")
        QTimer.singleShot(self.TYPING_DELAY_MS, self._finish_typing)

    def _finish_typing(self):
        """Swaps '...' for the real reply, picks a new mood, re-enables input."""
        self._chat.replace_last_bubble("egg", self._pending_reply)
        self._pending_reply = ""

        # Pick a random mood and update the EggPanel
        mood = random.choice(EggPanel.MOODS)
        self._egg_panel.set_mood(mood)

        self._set_input_enabled(True)
        self._input_bar.entry.setFocus()

    def _set_input_enabled(self, enabled: bool):
        """Toggles entry field and send button together."""
        self._input_bar.entry.setEnabled(enabled)
        self._input_bar.send_btn.setEnabled(enabled)


# ──────────────────────────────────────────────────────────────
# ENTRY POINT
# ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setQuitOnLastWindowClosed(True)   # Ensures closing the window exits the process

    window = EggManWindow()
    window.show()

    sys.exit(app.exec())