from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any

from backend.tools.tool_manager import ToolManager


@dataclass(frozen=True, slots=True)
class ToolRouteResult:
    handled: bool
    response_text: str = ""
    tool_name: str = ""
    result: Any = None


class ToolRouter:
    """Routes direct natural-language requests to local tools before AI execution."""

    _APP_ALIASES = {
        "vs code": "vscode",
        "visual studio code": "vscode",
        "google chrome": "chrome",
    }

    def __init__(self, tool_manager: ToolManager, logger: logging.Logger | None = None) -> None:
        self._tool_manager = tool_manager
        self._logger = logger or logging.getLogger("eggman")

    def route(self, message: str) -> ToolRouteResult:
        text = message.strip()
        if not text:
            return ToolRouteResult(handled=False)

        clipboard_text = self._parse_clipboard_copy(text)
        if clipboard_text is not None:
            return self._execute("clipboard", "copy", clipboard_text)

        app_name = self._parse_app_launch(text)
        if app_name is not None:
            return self._execute("app_launcher", app_name)

        expression = self._parse_calculation(text)
        if expression is not None:
            return self._execute("calculator", expression)

        return ToolRouteResult(handled=False)

    def _execute(self, tool_name: str, *args: Any) -> ToolRouteResult:
        self._logger.info("ToolRouter matched tool=%s args=%r", tool_name, args)
        try:
            result = self._tool_manager.execute(tool_name, *args)
        except Exception as exc:
            self._logger.info("ToolRouter handled tool=%s success=False error=%s", tool_name, exc)
            return ToolRouteResult(
                handled=True,
                response_text=self._friendly_error(tool_name, exc),
                tool_name=tool_name,
                result={"success": False, "error": str(exc)},
            )

        response = self._friendly_success(tool_name, result)
        self._logger.info("ToolRouter handled tool=%s success=True response=%r", tool_name, response)
        return ToolRouteResult(handled=True, response_text=response, tool_name=tool_name, result=result)

    def _parse_clipboard_copy(self, text: str) -> str | None:
        match = re.match(r"^\s*copy(?:\s+this\s+text\s*:|\s+this\s*:|\s+text\s*:|\s+)(.+)$", text, re.IGNORECASE | re.DOTALL)
        if not match:
            return None
        value = match.group(1).strip()
        return value or None

    def _parse_app_launch(self, text: str) -> str | None:
        match = re.match(r"^\s*(?:open|launch|start)\s+(.+?)\s*$", text, re.IGNORECASE)
        if not match:
            return None
        app_name = re.sub(r"^(?:the\s+)?app\s+", "", match.group(1).strip().lower())
        return self._APP_ALIASES.get(app_name, app_name.replace(" ", ""))

    def _parse_calculation(self, text: str) -> str | None:
        patterns = [
            r"^\s*(?:calculate|calc|compute|evaluate)\s+(.+?)\s*$",
            r"^\s*what\s+is\s+(.+?)\??\s*$",
            r"^\s*what'?s\s+(.+?)\??\s*$",
        ]
        for pattern in patterns:
            match = re.match(pattern, text, re.IGNORECASE)
            if match:
                expression = match.group(1).strip()
                return expression if self._looks_like_arithmetic(expression) else None
        return None

    def _looks_like_arithmetic(self, expression: str) -> bool:
        if not re.fullmatch(r"[0-9\s+\-*/%().]+", expression):
            return False
        return bool(re.search(r"\d", expression) and re.search(r"[+\-*/%]", expression))

    def _friendly_success(self, tool_name: str, result: Any) -> str:
        if tool_name == "clipboard":
            return "✓ Copied to clipboard."
        if tool_name == "app_launcher":
            app_name = self._display_app_name(str(result.get("application", ""))) if isinstance(result, dict) else "the app"
            return f"✓ Opening {app_name}..."
        if tool_name == "calculator":
            value = result.get("result") if isinstance(result, dict) else result
            return f"✓ Result: {value}."
        return "✓ Done."

    def _friendly_error(self, tool_name: str, exc: Exception) -> str:
        if tool_name == "app_launcher":
            return f"I couldn't open that app: {exc}"
        if tool_name == "calculator":
            return f"I couldn't calculate that: {exc}"
        if tool_name == "clipboard":
            return f"I couldn't copy that: {exc}"
        return f"I couldn't run that tool: {exc}"

    def _display_app_name(self, app_name: str) -> str:
        names = {
            "vscode": "VS Code",
            "chrome": "Chrome",
            "spotify": "Spotify",
            "notepad": "Notepad",
        }
        return names.get(app_name.lower(), app_name)
