from __future__ import annotations
from backend.prompt.prompt_module import PromptModule
from backend.prompt.prompt_context import PromptContext
from backend.prompt.prompt_registry import PromptRegistry

class KnowledgeModule(PromptModule):
    def name(self) -> str:
        return "knowledge"

    def is_static(self) -> bool:
        return False

    def is_applicable(self, context: PromptContext) -> bool:
        return bool(context.retrieved_knowledge)

    def generate(self, context: PromptContext) -> str:
        return (
            "KNOWLEDGE DOCUMENTATION RULES:\n"
            "- Answer using information from the retrieved document chunks if it helps address the query.\n"
            "- Keep knowledge injection natural. Do not cite chunk index numbers directly to the user."
        )

PromptRegistry.register(KnowledgeModule())
