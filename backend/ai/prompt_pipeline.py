from __future__ import annotations

from enum import Enum

from backend.context.context_builder import ContextPayload


class PromptPipeline:
    """Formats provider-agnostic prompt content for future AI backends."""

    def build_prompt(self, context: ContextPayload) -> str:
        lines: list[str] = []
        lines.append(f"System: {context.system_prompt}")
        lines.append("Recent conversation:")
        if context.recent_conversation:
            for sender, message in context.recent_conversation:
                lines.append(f"- {sender}: {message}")
        else:
            lines.append("- none")

        lines.append("Retrieved memories:")
        if context.retrieved_memories:
            for memory in context.retrieved_memories:
                category = getattr(memory, "category", "")
                content = getattr(memory, "content", None)
                if content is None:
                    content = getattr(memory, "value", "")
                if isinstance(category, Enum):
                    category = category.value
                lines.append(f"- {category}: {content}")
        else:
            lines.append("- none")

        lines.append(f"User: {context.current_user_message}")
        return "\n".join(lines)
