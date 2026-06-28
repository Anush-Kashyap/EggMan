from __future__ import annotations

import re
from datetime import datetime
from typing import Optional

from backend.memory.models import ImportanceLevel, MemoryCategory, MemoryRecord


class MemoryExtractor:
    """Rule-based extractor that identifies useful facts for long-term memory."""

    _IGNORE_PHRASES = {
        "hello",
        "hi",
        "thanks",
        "thank you",
        "good morning",
        "good afternoon",
        "good evening",
        "tell me a joke",
        "what's 2+2",
        "what is 2+2",
        "2+2",
    }

    def extract(self, user_message: str) -> Optional[MemoryRecord]:
        text = user_message.strip()
        if not text:
            return None
        normalized = re.sub(r"\s+", " ", text).lower()
        if normalized in self._IGNORE_PHRASES:
            return None

        if normalized.startswith("my favorite"):
            return self._build_record("preference", "favorite", text.split("is", 1)[-1].strip() if " is " in text.lower() else text)

        if re.match(r"^(my|i) birthday", normalized):
            return self._build_record("preference", "birthday", text)

        if normalized.startswith("remember that "):
            remembered = text[len("remember that "):].strip()
            if remembered:
                return self._build_record("semantic", "remembered_fact", remembered)

        if re.match(r"^(i am|i'm|my major is|i study|i am studying)", normalized):
            return self._build_record("semantic", "study", text)

        if re.match(r"^(i live in|i'm from|i am from|my hometown is)", normalized):
            return self._build_record("semantic", "profile_location", text)

        if re.match(r"^(i work as|i work at|my job is|my role is)", normalized):
            return self._build_record("semantic", "profile_work", text)

        if re.match(r"^(i use|i usually use|my preferred)", normalized):
            return self._build_record("preference", "preference", text)

        if re.match(r"^(i love|i like|i enjoy)", normalized):
            return self._build_record("preference", "interest", text)

        if re.match(r"^(i want|i wish|my goal is|my goal)", normalized):
            return self._build_record("semantic", "goal", text)

        if re.match(r"^(my name is|i am called|call me)", normalized):
            return self._build_record("relationship", "name", text)

        return None

    def _build_record(self, category: str, key: str, value: str) -> MemoryRecord:
        memory_category = MemoryCategory(category) if category in {member.value for member in MemoryCategory} else MemoryCategory.SEMANTIC
        return MemoryRecord(
            category=memory_category,
            key=key,
            value=value,
            importance=self._importance_for(key),
            confidence=0.85,
            created_at=datetime.now().isoformat(timespec="seconds"),
            updated_at=datetime.now().isoformat(timespec="seconds"),
            last_accessed=datetime.now().isoformat(timespec="seconds"),
            access_count=1,
        )

    def _importance_for(self, key: str) -> ImportanceLevel:
        if key in {"goal", "birthday", "name", "remembered_fact"}:
            return ImportanceLevel.HIGH
        if key in {"favorite", "interest", "study", "profile_location", "profile_work", "preference"}:
            return ImportanceLevel.MEDIUM
        return ImportanceLevel.LOW
