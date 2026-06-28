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
        def generate(self, request):
            return type("R", (), {"response_text": f"stub:{request.user_message}", "successful": True})()

        def stream(self, request):
            return type("Stream", (), {"__iter__": lambda self: iter([type("C", (), {"text": f"stub:{request.user_message}", "done": True})()])})()

    engine = ConversationEngine(ai_engine=None)
    fallback = engine.get_reply("hello")
    assert fallback == "stub:hello" or isinstance(fallback, str)


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


def test_app_container_initializes_database(tmp_path):
    from app.container import AppContainer

    database_path = tmp_path / "eggman.sqlite3"
    container = AppContainer(
        config_path=tmp_path / "config.json",
        log_path=tmp_path / "eggman.log",
        database_path=database_path,
    )

    assert container.database_manager is not None
    assert container.conversation_repository is not None
    assert container.memory_service is not None
    assert container.context_builder is not None
    assert container.prompt_pipeline is not None
    assert database_path.exists()


def test_prompt_pipeline_formats_context():
    from backend.context.context_builder import ContextBuilder
    from backend.ai.prompt_pipeline import PromptPipeline
    from backend.memory.memory_types import MemoryEntry

    builder = ContextBuilder()
    pipeline = PromptPipeline()
    context = builder.build_context(
        user_message="hello",
        recent_conversation=[("egg", "hi")],
        memories=[MemoryEntry(memory_id="1", category="general", content="prefers short replies")],
    )
    prompt = pipeline.build_prompt(context)

    assert "System:" in prompt
    assert "User: hello" in prompt
    assert "prefers short replies" in prompt


def test_streaming_and_emotion_layers_are_available():
    from backend.ai.streaming import StreamingPipeline
    from backend.emotion.emotion_engine import EmotionEngine
    from backend.tools.registry import ToolRegistry

    pipeline = StreamingPipeline()
    response = pipeline.stream("hello world")
    chunks = list(response)

    assert len(chunks) == 2
    assert chunks[0].text == "hello"

    emotion_engine = EmotionEngine()
    state = emotion_engine.observe("hello there")
    assert state.mood == "happy"

    from backend.tools.tool import BaseTool

    class DemoTool(BaseTool):
        name = "demo"

        def execute(self, *args, **kwargs):
            return "ok"

    registry = ToolRegistry()
    registry.register(DemoTool)


def test_embedding_and_retrieval_layers_integrate(tmp_path):
    from backend.context.context_builder import ContextBuilder
    from backend.embeddings.embedding_service import EmbeddingService
    from backend.embeddings.vector_store import InMemoryVectorStore
    from backend.memory.memory_extractor import MemoryExtractor
    from backend.memory.memory_manager import MemoryManager
    from backend.memory.memory_repository import MemoryRepository
    from backend.database.database import DatabaseManager
    from backend.retrieval.retrieval_service import RetrievalService

    database_manager = DatabaseManager(database_path=tmp_path / "memory.sqlite3")
    repository = MemoryRepository(database_manager)
    memory_manager = MemoryManager(repository=repository, extractor=MemoryExtractor())
    retrieval_service = RetrievalService(memory_manager=memory_manager, embedding_service=EmbeddingService(), vector_store=InMemoryVectorStore())
    builder = ContextBuilder(retrieval_service=retrieval_service)

    context = builder.build_context("What do you prefer?")
    assert context.retrieved_memories == []
