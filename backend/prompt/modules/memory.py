from __future__ import annotations
from backend.prompt.prompt_module import PromptModule
from backend.prompt.prompt_context import PromptContext
from backend.prompt.prompt_registry import PromptRegistry

class MemoryModule(PromptModule):
    def name(self) -> str:
        return "memory"

    def is_static(self) -> bool:
        return False

    def is_applicable(self, context: PromptContext) -> bool:
        return bool(context.retrieved_memories)

    def generate(self, context: PromptContext) -> str:
        return (
            "MEMORY RULES:\n"
            "- Only reference previous conversations or user facts if they are genuinely relevant to the current request and improve the answer.\n"
            "- Do not force memories into responses. Avoid repeatedly mentioning the EggMan project, user preferences, previous discussions, or personal facts unless asked or directly helpful."
        )

PromptRegistry.register(MemoryModule())
