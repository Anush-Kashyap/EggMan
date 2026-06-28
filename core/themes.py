from PySide6.QtGui import QFont


class Theme:
    CREAM = "#F5F0E8"
    CREAM_DARK = "#EDE7D9"
    BORDER = "#C8BFA8"
    TEXT_DARK = "#2C2416"
    TEXT_MID = "#8C7B65"
    TEXT_FAINT = "#B0A898"
    INPUT_BG = "#FFFFFF"
    BTN_BG = "#DDD5C0"
    BTN_HOVER = "#CEC5AF"
    BTN_PRESS = "#BDB49F"
    CTRL_HOVER_MIN = "#C8E0C8"
    CTRL_HOVER_CLS = "#E0B0B0"
    CTRL_PRESS_MIN = "#A8C8A8"
    CTRL_PRESS_CLS = "#C89090"
    BUBBLE_USER = "#E2D9C8"
    BUBBLE_EGG = "#EDE7D9"
    BUBBLE_RADIUS = 14
    EMPTY_STATE_MSG = "No messages yet.\nSay something to EggMan 🥚"

    FONT_TITLE = QFont("Georgia", 13, QFont.Bold)
    FONT_CHAT = QFont("Segoe UI", 10)
    FONT_SENDER = QFont("Segoe UI", 8, QFont.Bold)
    FONT_TIMESTAMP = QFont("Segoe UI", 7)
    FONT_INPUT = QFont("Segoe UI", 10)
    FONT_BTN = QFont("Segoe UI", 13)
    FONT_EMPTY = QFont("Segoe UI", 9)

    WIN_W = 270
    WIN_H = 500
    RADIUS = 18
    MAX_MESSAGES = 100


class ThemeManager:
    LIGHT = {
        "CREAM": "#F5F0E8",
        "CREAM_DARK": "#EDE7D9",
        "BORDER": "#C8BFA8",
        "TEXT_DARK": "#2C2416",
        "TEXT_MID": "#8C7B65",
        "TEXT_FAINT": "#B0A898",
        "INPUT_BG": "#FFFFFF",
        "BTN_BG": "#DDD5C0",
        "BTN_HOVER": "#CEC5AF",
        "BTN_PRESS": "#BDB49F",
        "CTRL_HOVER_MIN": "#C8E0C8",
        "CTRL_HOVER_CLS": "#E0B0B0",
        "CTRL_PRESS_MIN": "#A8C8A8",
        "CTRL_PRESS_CLS": "#C89090",
        "BUBBLE_USER": "#E2D9C8",
        "BUBBLE_EGG": "#EDE7D9",
    }

    DARK = {
        "CREAM": "#1E1E2E",
        "CREAM_DARK": "#181825",
        "BORDER": "#313244",
        "TEXT_DARK": "#CDD6F4",
        "TEXT_MID": "#7F849C",
        "TEXT_FAINT": "#585B70",
        "INPUT_BG": "#262637",
        "BTN_BG": "#313244",
        "BTN_HOVER": "#45475A",
        "BTN_PRESS": "#585B70",
        "CTRL_HOVER_MIN": "#2A4A2A",
        "CTRL_HOVER_CLS": "#4A2A2A",
        "CTRL_PRESS_MIN": "#1A3A1A",
        "CTRL_PRESS_CLS": "#3A1A1A",
        "BUBBLE_USER": "#2A2A3E",
        "BUBBLE_EGG": "#232334",
    }

    _PALETTES = {"light": LIGHT, "dark": DARK}

    def __init__(self, on_theme_changed):
        self._callback = on_theme_changed

    def apply(self, name: str):
        palette = self._PALETTES.get(name, self.LIGHT)
        for attr, value in palette.items():
            setattr(Theme, attr, value)
        self._callback()

    @staticmethod
    def names() -> list:
        return ["light", "dark"]
