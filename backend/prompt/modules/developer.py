from __future__ import annotations
from backend.prompt.prompt_module import PromptModule
from backend.prompt.prompt_context import PromptContext
from backend.prompt.prompt_registry import PromptRegistry

class DeveloperModule(PromptModule):
    def name(self) -> str:
        return "developer"

    def is_static(self) -> bool:
        return True

    def is_applicable(self, context: PromptContext) -> bool:
        return context.developer_mode

    def generate(self, context: PromptContext) -> str:
        return (
            "DEVELOPER DIAGNOSTIC MODE:\n"
            "- You are running in Developer Diagnostics Mode.\n"
            "- Performance profiling and internal logs are visible to the user.\n"
            "- Be precise, technical, and helpful regarding system states if asked."
        )

PromptRegistry.register(DeveloperModule())
