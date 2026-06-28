from datetime import datetime

from core.themes import ThemeManager


class CommandResult:
    def __init__(self, handled: bool, response: str = "", action: str = ""):
        self.handled = handled
        self.response = response
        self.action = action


class CommandHandler:
    HELP_TEXT = (
        "Available commands:\n"
        "  /help       — show this message\n"
        "  /clear      — clear chat history\n"
        "  /about      — about EggMan\n"
        "  /time       — current time\n"
        "  /export     — export chat to file\n"
        "  /settings   — open settings window\n"
        "  /theme light|dark  — switch theme"
    )

    ABOUT_TEXT = (
        "EggMan v0.1.9 🥚\n"
        "A soft desktop companion.\n"
        "Built with PySide6."
    )

    def handle(self, text: str) -> CommandResult:
        if not text.startswith("/"):
            return CommandResult(handled=False)

        parts = text.strip().split()
        cmd = parts[0].lower()
        args = parts[1:]

        if cmd == "/help":
            return CommandResult(handled=True, response=self.HELP_TEXT)

        if cmd == "/clear":
            return CommandResult(handled=True, action="clear")

        if cmd == "/about":
            return CommandResult(handled=True, response=self.ABOUT_TEXT)

        if cmd == "/time":
            now = datetime.now().strftime("%H:%M:%S on %A, %d %B %Y")
            return CommandResult(handled=True, response=f"It is {now}.")

        if cmd == "/export":
            return CommandResult(handled=True, action="export")

        if cmd == "/settings":
            return CommandResult(handled=True, action="settings")

        if cmd == "/theme":
            if args and args[0].lower() in ThemeManager.names():
                return CommandResult(
                    handled=True,
                    action=f"theme_{args[0].lower()}",
                    response=f"Theme switched to {args[0].lower()}.",
                )
            return CommandResult(handled=True, response="Usage: /theme light|dark")

        return CommandResult(handled=True, response=f"Unknown command: {cmd}\nType /help for a list.")
