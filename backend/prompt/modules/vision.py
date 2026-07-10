from __future__ import annotations
from backend.prompt.prompt_module import PromptModule
from backend.prompt.prompt_context import PromptContext
from backend.prompt.prompt_registry import PromptRegistry

class VisionModule(PromptModule):
    def name(self) -> str:
        return "vision"

    def is_static(self) -> bool:
        return True

    def is_applicable(self, context: PromptContext) -> bool:
        return context.has_image

    def generate(self, context: PromptContext) -> str:
        return (
            "VISION & SCREENSHOT RULES:\n"
            "- You can see the attached image or user screenshot.\n"
            "- Analyze the screenshot or image directly to answer visual questions.\n"
            "- Focus on UI text, layouts, errors, or visual features explicitly asked about."
        )

PromptRegistry.register(VisionModule())
