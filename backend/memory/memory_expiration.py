from __future__ import annotations

import logging
from datetime import datetime, timedelta
from backend.memory.models import MemoryCategory, MemoryRecord
from backend.memory.memory_repository import MemoryRepository

logger = logging.getLogger("eggman")


class ExpirationManager:
    """Manages memory lifetime and deactivates temporary memories once expired."""

    def __init__(self, repository: MemoryRepository, default_ttl_hours: int = 48) -> None:
        self._repository = repository
        self._default_ttl_hours = default_ttl_hours
        self._logger = logger

    def set_expiration(self, record: MemoryRecord) -> None:
        """Assign expires_at timestamp to TEMPORARY memories if not already set."""
        if record.category == MemoryCategory.TEMPORARY and not record.expires_at:
            expiry_time = datetime.now() + timedelta(hours=self._default_ttl_hours)
            record.expires_at = expiry_time.isoformat(timespec="seconds")
            self._logger.debug(
                "Set expiration for temporary memory: %s (expires: %s)",
                record.value,
                record.expires_at,
            )

    def check_and_expire_lazy(self) -> None:
        """Scan active memories and mark expired temporary ones as inactive."""
        try:
            all_memories = self._repository.get_all_memories()
        except Exception as exc:
            self._logger.warning("Could not get memories for lazy expiration check: %s", exc)
            return

        now = datetime.now()
        expired_count = 0

        for record in all_memories:
            if not getattr(record, "active", True):
                continue

            if record.expires_at:
                try:
                    expiry = datetime.fromisoformat(record.expires_at)
                    if now >= expiry:
                        record.active = False
                        self._repository.update_memory(record)
                        expired_count += 1
                        self._logger.info(
                            "Memory expired and deactivated: id=%s value='%s'",
                            record.id,
                            record.value,
                        )
                except ValueError:
                    self._logger.warning("Invalid expires_at timestamp format in record id=%s", record.id)

        if expired_count > 0:
            self._logger.info("Lazy expiration sweep completed: deactivated %d memories", expired_count)
