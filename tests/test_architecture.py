import importlib
import json
import os
import sys

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def test_conversation_engine_uses_provider(monkeypatch):
    from core.conversation import ConversationEngine
    from core.providers import BaseProvider

    class StubProvider(BaseProvider):
        def generate_reply(self, user_message: str) -> str:
            return f"stub:{user_message}"

    engine = ConversationEngine(provider=StubProvider())
    assert engine.get_reply("hello") == "stub:hello"


def test_config_manager_loads_and_saves(tmp_path):
    from core.config import ConfigManager

    config_path = tmp_path / "config.json"
    manager = ConfigManager(config_path=config_path)

    manager.set("provider", "local")
    manager.set("typing_delay", 1234)
    manager.save()

    reloaded = ConfigManager(config_path=config_path)
    assert reloaded.get("provider") == "local"
    assert reloaded.get("typing_delay") == 1234
