from __future__ import annotations

import ast
import os
import operator
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from backend.tools.tool import BaseTool


class CalculatorTool(BaseTool):
    """Safely evaluates basic arithmetic expressions."""

    name = "calculator"

    _BINARY_OPERATORS = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.Mod: operator.mod,
        ast.Pow: operator.pow,
    }
    _UNARY_OPERATORS = {
        ast.UAdd: operator.pos,
        ast.USub: operator.neg,
    }
    _MAX_ABS_VALUE = 1_000_000_000
    _MAX_EXPONENT = 12

    def execute(self, expression: str, *args, **kwargs) -> dict[str, Any]:
        expression = str(expression).strip()
        if not expression:
            raise ValueError("Calculator expression is required")
        try:
            parsed = ast.parse(expression, mode="eval")
        except SyntaxError as exc:
            raise ValueError("Unsafe or unsupported calculator expression") from exc
        result = self._evaluate(parsed.body)
        return {"tool": self.name, "expression": expression, "result": result}

    def _evaluate(self, node: ast.AST) -> int | float:
        value = self._evaluate_node(node)
        if abs(value) > self._MAX_ABS_VALUE:
            raise ValueError("Calculator result is too large")
        return value

    def _evaluate_node(self, node: ast.AST) -> int | float:
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
            return node.value
        if isinstance(node, ast.BinOp) and type(node.op) in self._BINARY_OPERATORS:
            left = self._evaluate_node(node.left)
            right = self._evaluate_node(node.right)
            if isinstance(node.op, ast.Pow) and abs(right) > self._MAX_EXPONENT:
                raise ValueError("Exponent is too large")
            return self._BINARY_OPERATORS[type(node.op)](left, right)
        if isinstance(node, ast.UnaryOp) and type(node.op) in self._UNARY_OPERATORS:
            return self._UNARY_OPERATORS[type(node.op)](self._evaluate_node(node.operand))
        raise ValueError("Unsafe or unsupported calculator expression")


class ClipboardBackend(Protocol):
    def copy(self, text: str) -> None:
        ...

    def paste(self) -> str:
        ...


class TkClipboardBackend:
    """Small stdlib clipboard adapter used when a Qt clipboard is not injected."""

    def copy(self, text: str) -> None:
        import tkinter

        root = tkinter.Tk()
        root.withdraw()
        try:
            root.clipboard_clear()
            root.clipboard_append(text)
            root.update()
        finally:
            root.destroy()

    def paste(self) -> str:
        import tkinter

        root = tkinter.Tk()
        root.withdraw()
        try:
            return str(root.clipboard_get())
        except tkinter.TclError:
            return ""
        finally:
            root.destroy()


class ClipboardTool(BaseTool):
    """Copies to and reads from the system clipboard."""

    name = "clipboard"

    def __init__(self, clipboard_backend: ClipboardBackend | None = None) -> None:
        self._clipboard = clipboard_backend or TkClipboardBackend()

    def execute(self, action: str, text: str | None = None, *args, **kwargs) -> dict[str, Any]:
        action = str(action).strip().lower()
        if action in {"copy", "set", "write"}:
            if text is None:
                raise ValueError("Clipboard copy requires text")
            value = str(text)
            self._clipboard.copy(value)
            return {"tool": self.name, "action": "copy", "success": True, "text_length": len(value)}
        if action in {"paste", "read", "get"}:
            value = self._clipboard.paste()
            return {"tool": self.name, "action": "read", "success": True, "text": value}
        raise ValueError(f"Unsupported clipboard action: {action}")


@dataclass(frozen=True, slots=True)
class ApplicationRegistry:
    applications: dict[str, tuple[str, ...]]

    @classmethod
    def defaults(cls) -> ApplicationRegistry:
        local_app_data = os.getenv("LOCALAPPDATA", "")
        return cls(
            applications={
                "chrome": (
                    "chrome",
                    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
                ),
                "spotify": ("spotify",),
                "vscode": (
                    "code",
                    str(Path(local_app_data) / "Programs" / "Microsoft VS Code" / "Code.exe") if local_app_data else "",
                ),
                "notepad": ("notepad", "notepad.exe"),
            }
        )

    def candidates_for(self, name: str) -> tuple[str, ...]:
        return self.applications.get(name.strip().lower(), ())

    def names(self) -> list[str]:
        return sorted(self.applications.keys())


class AppLauncherTool(BaseTool):
    """Launches only registered applications without shell command execution."""

    name = "app_launcher"

    def __init__(self, application_registry: ApplicationRegistry | None = None) -> None:
        self._applications = application_registry or ApplicationRegistry.defaults()

    def execute(self, app_name: str, *args, **kwargs) -> dict[str, Any]:
        requested_name = str(app_name).strip().lower()
        candidates = self._applications.candidates_for(requested_name)
        if not candidates:
            raise ValueError(
                f"Unknown application: {app_name}. Registered applications: {', '.join(self._applications.names())}"
            )

        last_error: OSError | None = None
        for executable in candidates:
            if not executable:
                continue
            if "\\" in executable or "/" in executable:
                path = Path(executable)
                if not path.exists():
                    continue
            try:
                process = subprocess.Popen([executable], shell=False)
                return {
                    "tool": self.name,
                    "application": requested_name,
                    "executable": executable,
                    "pid": process.pid,
                    "success": True,
                }
            except OSError as exc:
                last_error = exc

        raise RuntimeError(f"Registered application could not be launched: {requested_name}") from last_error
