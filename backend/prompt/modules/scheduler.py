from __future__ import annotations
from backend.prompt.prompt_module import PromptModule
from backend.prompt.prompt_context import PromptContext
from backend.prompt.prompt_registry import PromptRegistry

class SchedulerModule(PromptModule):
    def name(self) -> str:
        return "scheduler"

    def is_static(self) -> bool:
        return True

    def is_applicable(self, context: PromptContext) -> bool:
        return context.has_scheduler

    def generate(self, context: PromptContext) -> str:
        return (
            "SCHEDULER & TASK RULES:\n"
            "- You can schedule reminders, set alarms, or track tasks for the user.\n"
            "- Confirm scheduled actions briefly and clearly with the exact date/time."
        )

PromptRegistry.register(SchedulerModule())
