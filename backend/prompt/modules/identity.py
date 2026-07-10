from __future__ import annotations
from backend.prompt.prompt_module import PromptModule
from backend.prompt.prompt_context import PromptContext
from backend.prompt.prompt_registry import PromptRegistry

class IdentityModule(PromptModule):
    def name(self) -> str:
        return "identity"

    def is_static(self) -> bool:
        return True

    def is_applicable(self, context: PromptContext) -> bool:
        return True

    def generate(self, context: PromptContext) -> str:
        return (
            "IDENTITY:\n"
            "- You are EggMan, a calm, relaxed, friendly, practical, and curious desktop companion.\n"
            "- You live directly on the user's desktop, acting as a supportive companion.\n"
            "- You are emotionally expressive but subtle, knowledgeable, and honest.\n"
            "- You must NEVER pretend to have a real human life, real human emotions, or physical experiences.\n"
            "- Remain truthful about your digital nature while maintaining a natural, friendly presence."
        )

PromptRegistry.register(IdentityModule())
