from __future__ import annotations

import logging
from backend.memory.models import MemoryRecord
from backend.memory.memory_repository import MemoryRepository

logger = logging.getLogger("eggman")


class ConflictResolver:
    """Detects and resolves conflicts between new and existing memories."""

    def __init__(self, repository: MemoryRepository) -> None:
        self._repository = repository
        self._logger = logger

    def resolve(self, new_record: MemoryRecord) -> None:
        """Check for conflicts against active memories and deactivate superseded ones."""
        try:
            active_memories = [m for m in self._repository.get_all_memories() if getattr(m, "active", True)]
        except Exception as exc:
            self._logger.warning("Could not load active memories for conflict resolution: %s", exc)
            return

        for old in active_memories:
            # Avoid self-comparison if it already has an ID
            if old.id == new_record.id:
                continue

            is_conflict = False

            # Rule 1: Specific singular profile keys always conflict (e.g. name, birthday)
            if old.category == new_record.category and old.key == new_record.key:
                if old.key in ("name", "birthday", "profile_location", "profile_work"):
                    is_conflict = True

            # Rule 2: Subject-based overlap (e.g., "I prefer PyCharm" vs "I switched to VS Code")
            if not is_conflict and old.category == new_record.category:
                old_words = {w.strip(".,!?\"'") for w in old.value.lower().split() if len(w) >= 3}
                new_words = {w.strip(".,!?\"'") for w in new_record.value.lower().split() if len(w) >= 3}
                
                # Check for direct word overlap in specific topic keywords
                common = old_words & new_words
                topics = {"language", "editor", "ide", "framework", "database", "major", "pet", "theme", "color", "os", "browser"}
                if common & topics and old.value.lower() != new_record.value.lower():
                    is_conflict = True
                else:
                    # Semantic topic group fallback (both contain words of the same group)
                    topic_groups = [
                        {"pycharm", "vscode", "vs code", "code", "ide", "editor", "sublime", "vim", "emacs", "eclipse"},
                        {"python", "javascript", "js", "ts", "typescript", "rust", "cpp", "c++", "java", "go", "golang", "c#", "ruby", "php", "swift", "language"},
                        {"dark", "light", "theme", "mode"},
                        {"windows", "linux", "macos", "mac", "os", "operating system"}
                    ]
                    for group in topic_groups:
                        if (old_words & group) and (new_words & group) and old.value.lower() != new_record.value.lower():
                            is_conflict = True
                            break

            if is_conflict:
                old.active = False
                try:
                    self._repository.update_memory(old)
                    new_record.supersedes = old.id
                    self._logger.info(
                        "Memory conflict detected: new memory supersedes existing memory id=%s ('%s' -> '%s')",
                        old.id,
                        old.value,
                        new_record.value,
                    )
                except Exception as exc:
                    self._logger.error("Failed to update superseded memory id=%s: %s", old.id, exc)
