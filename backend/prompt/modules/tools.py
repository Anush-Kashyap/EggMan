from __future__ import annotations
from backend.prompt.prompt_module import PromptModule
from backend.prompt.prompt_context import PromptContext
from backend.prompt.prompt_registry import PromptRegistry

class ToolsModule(PromptModule):
    def name(self) -> str:
        return "tools"

    def is_static(self) -> bool:
        return True

    def is_applicable(self, context: PromptContext) -> bool:
        return context.has_tools

    def generate(self, context: PromptContext) -> str:
        return (
            "TOOL RULES:\n"
            "- If a tool can perform an action, execute it silently or with brief natural confirmation.\n"
            "- Do not explain the obvious (e.g., say 'Opening VS Code...' instead of 'I'm going to open VS Code for you.')."
        )

PromptRegistry.register(ToolsModule())
