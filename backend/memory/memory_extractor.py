from __future__ import annotations

import re
from datetime import datetime
from typing import Optional

from backend.memory.models import MemoryCategory, MemoryRecord


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
        "ok",
        "okay",
        "cool",
        "nice",
        "yes",
        "no",
    }

    def extract(self, user_message: str) -> Optional[MemoryRecord]:
        text = user_message.strip()
        if not text:
            return None
        normalized = re.sub(r"\s+", " ", text).lower()
        if normalized in self._IGNORE_PHRASES:
            return None

        # Ignore very short messages
        if len(text.split()) < 3:
            return None

        # 1. Favorite preferences
        if normalized.startswith("my favorite"):
            val = text.split("is", 1)[-1].strip() if " is " in text.lower() else text
            return self._build_record("preference", "favorite", val, "explicit")

        # 2. Birthdays
        if re.match(r"^(my|i) birthday", normalized):
            return self._build_record("personal_fact", "birthday", text, "explicit")

        # 3. Explicit instruction to remember
        if normalized.startswith("remember that "):
            remembered = text[len("remember that "):].strip()
            if remembered:
                return self._build_record("permanent", "remembered_fact", remembered, "remembered")

        # 4. Studies / Major / Careers
        if re.match(r"^(i am|i'm|my major is|i study|i am studying)", normalized):
            return self._build_record("skill", "study", text, "explicit")

        # 5. Location facts
        if re.match(r"^(i live in|i'm from|i am from|my hometown is)", normalized):
            return self._build_record("personal_fact", "profile_location", text, "explicit")

        # 6. Work profile
        if re.match(r"^(i work as|i work at|my job is|my role is)", normalized):
            return self._build_record("personal_fact", "profile_work", text, "explicit")

        # 7. Tool/language preference
        if re.match(r"^(i use|i usually use|my preferred)", normalized):
            return self._build_record("preference", "preference", text, "explicit")

        # 8. Hobbies/interests
        if re.match(r"^(i love|i like|i enjoy)", normalized):
            return self._build_record("preference", "interest", text, "explicit")

        # 9. Future goals
        if re.match(r"^(i want|i wish|my goal is|my goal)", normalized):
            return self._build_record("goal", "goal", text, "explicit")

        # 10. User identity name
        if re.match(r"^(my name is|i am called|call me)", normalized):
            return self._build_record("personal_fact", "name", text, "explicit")

        # 11. Temporary states
        if re.match(r"^(i'm traveling|i'm travelling|i am sick|i'm sick|i am busy|i'm busy)", normalized):
            return self._build_record("temporary", "state", text, "explicit")

        return None

    def _build_record(self, category_str: str, key: str, value: str, source: str) -> MemoryRecord:
        try:
            category = MemoryCategory(category_str)
        except ValueError:
            category = MemoryCategory.PERMANENT

        # Default confidence: explicit statements are highly reliable
        confidence = 0.95 if source == "explicit" else 0.85

        return MemoryRecord(
            category=category,
            key=key,
            value=value,
            confidence=confidence,
            source=source,
            created_at=datetime.now().isoformat(timespec="seconds"),
            updated_at=datetime.now().isoformat(timespec="seconds"),
            last_accessed=datetime.now().isoformat(timespec="seconds"),
            access_count=1,
            active=True,
        )
