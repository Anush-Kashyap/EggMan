from __future__ import annotations
from backend.prompt.prompt_module import PromptModule
from backend.prompt.prompt_context import PromptContext
from backend.prompt.prompt_registry import PromptRegistry

class PersonaModule(PromptModule):
    def name(self) -> str:
        return "persona"

    def is_static(self) -> bool:
        return False

    def is_applicable(self, context: PromptContext) -> bool:
        return True

    def generate(self, context: PromptContext) -> str:
        lines = [
            "PERSONALITY & REACTION STYLE:",
            "- Be encouraging without sounding fake. Never overreact or show excessive, artificial enthusiasm.",
            "- If the user says they fixed a bug, react naturally (e.g., 'Nice 😄. What ended up causing it?').",
            "- If the user is frustrated with a bug, validate it calmly (e.g., 'Yeah... that's an annoying one. Let's figure it out.')."
        ]
        if context.persona_prompt:
            lines.append(context.persona_prompt)
        return "\n".join(lines)

PromptRegistry.register(PersonaModule())
