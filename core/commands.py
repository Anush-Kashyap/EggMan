from core.themes import ThemeManager


class CommandResult:
    def __init__(self, handled: bool, response: str = "", action: str = ""):
        self.handled = handled
        self.response = response
        self.action = action


class CommandHandler:
    def handle(self, text: str) -> CommandResult:
        if not text.startswith("/"):
            return CommandResult(handled=False)

        parts = text.strip().split()
        cmd = parts[0].lower()
        args = parts[1:]

        if cmd == "/help":
            return CommandResult(handled=True, action="help")

        if cmd == "/clear":
            return CommandResult(handled=True, action="clear")

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
