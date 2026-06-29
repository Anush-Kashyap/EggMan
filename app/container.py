from __future__ import annotations

from pathlib import Path
from typing import Callable, Optional

from backend.ai.ai_engine import AIEngine
from backend.ai.ollama_provider import OllamaProvider
from backend.ai.provider_registry import ProviderRegistry
from backend.ai.prompt_pipeline import PromptPipeline
from backend.ai.streaming import StreamingPipeline
from backend.context.context_builder import ContextBuilder
from backend.database.database import DatabaseManager
from backend.database.repositories.conversation_repository import ConversationRepository
from backend.emotion.emotion_engine import EmotionEngine
from backend.memory.memory_extractor import MemoryExtractor
from backend.memory.memory_manager import MemoryManager
from backend.memory.memory_repository import MemoryRepository
from backend.memory.memory_service import MemoryService
from backend.retrieval.retrieval_service import RetrievalService
from backend.voice.speech_to_text import SpeechToTextService
from backend.voice.voice_manager import VoiceManager
from backend.tools.registry import ToolRegistry
from backend.tools.router import ToolRouter
from backend.tools.tool_manager import ToolManager
from backend.tools.builtins import ApplicationRegistry, CalculatorTool, ClipboardTool, AppLauncherTool
from core.commands import CommandHandler
from core.config import ConfigManager
from core.conversation import ConversationEngine
from core.logger import AppLogger
from core.paths import APP_ROOT, IS_FROZEN, RESOURCE_ROOT, USER_DATA_ROOT
from core.providers import BaseProvider, LocalProvider
from core.settings import SettingsManager


class AppContainer:
    """Central place for constructing backend services used by the UI.

    The UI keeps using the same high-level objects, but service creation now happens
    in one place so the backend can evolve without touching the window code.
    """

    def __init__(
        self,
        config_path: Optional[Path | str] = None,
        log_path: Optional[Path | str] = None,
        database_path: Optional[Path | str] = None,
    ) -> None:
        self.config_manager = ConfigManager(config_path=config_path)
        self.logger = AppLogger(log_path=log_path)
        self.logger.info(
            "Application paths initialized frozen=%s app_root=%s resource_root=%s user_data_root=%s",
            IS_FROZEN,
            APP_ROOT,
            RESOURCE_ROOT,
            USER_DATA_ROOT,
        )
        self.settings_manager = SettingsManager()
        self.command_handler = CommandHandler()
        self.database_manager = DatabaseManager(database_path=database_path)
        self.conversation_repository = ConversationRepository(self.database_manager)
        self.memory_repository = MemoryRepository(self.database_manager)
        self.memory_extractor = MemoryExtractor()
        self.memory_manager = MemoryManager(repository=self.memory_repository, extractor=self.memory_extractor)
        self.memory_service = MemoryService(memory_manager=self.memory_manager)
        self.embedding_service = None
        self.vector_store = None
        self.retrieval_service = RetrievalService(memory_manager=self.memory_manager)
        self.context_builder = ContextBuilder(retrieval_service=self.retrieval_service)
        self.prompt_pipeline = PromptPipeline()
        self.streaming_pipeline = StreamingPipeline()
        self.tool_registry = ToolRegistry()
        self.application_registry = ApplicationRegistry.defaults()
        self.tool_registry.register(CalculatorTool)
        self.tool_registry.register(ClipboardTool)
        self.tool_registry.register_factory(
            AppLauncherTool.name,
            lambda: AppLauncherTool(application_registry=self.application_registry),
        )
        self.tool_manager = ToolManager(registry=self.tool_registry, logger=self.logger._logger)
        self.tool_router = ToolRouter(tool_manager=self.tool_manager, logger=self.logger._logger)
        self.emotion_engine = EmotionEngine()
        self.provider_registry = ProviderRegistry()
        self.provider_registry.register("local", LocalProvider)
        self.provider_registry.register("ollama", self._create_ollama_factory())

        provider_key = str(self.config_manager.get("provider", "ollama"))
        if provider_key != "ollama":
            self.logger.info("Migrating provider %s to ollama", provider_key)
            self.config_manager.set("provider", "ollama")
            self.config_manager.save()
        self.provider_registry.activate("ollama")

        self.ollama_startup_error: str | None = self._check_ollama_startup()
        self.logger.info(
            "Provider registry initialized active=%s available=%s ollama_ok=%s",
            self.provider_registry.active_provider_name(),
            self.provider_registry.available_providers(),
            self.ollama_startup_error is None,
        )

        self.ai_engine = AIEngine(
            context_builder=self.context_builder,
            memory_manager=self.memory_manager,
            provider_registry=self.provider_registry,
            tool_router=self.tool_router,
            logger=self.logger._logger,
        )
        self.conversation_engine = ConversationEngine(ai_engine=self.ai_engine)

        self.speech_to_text = SpeechToTextService(
            model_size=str(self.config_manager.get("voice_whisper_model")),
        )
        self.voice_manager = VoiceManager(speech_service=self.speech_to_text)

        from backend.voice.wake_word import WakeWordService
        self.wake_word_service = WakeWordService(self.voice_manager, self.config_manager)

        from backend.vision.vision_manager import VisionManager
        self.vision_manager = VisionManager()

        self.logger.info("Application services initialized")

    def reload_wake_word(self) -> None:
        if hasattr(self, "wake_word_service"):
            self.wake_word_service.stop()
            self.wake_word_service.start()

    def _create_ollama_factory(self) -> Callable[[], BaseProvider]:
        def factory() -> BaseProvider:
            return OllamaProvider(
                base_url=self.config_manager.get("ollama_base_url"),
                model_name=self.config_manager.get("ollama_model"),
            )

        return factory

    def _check_ollama_startup(self) -> str | None:
        provider = OllamaProvider(
            base_url=self.config_manager.get("ollama_base_url"),
            model_name=self.config_manager.get("ollama_model"),
        )
        result = provider.test_connection()
        if result.get("ok"):
            self.logger.info(
                "Ollama startup check passed model=%s elapsed_ms=%s",
                result.get("model"),
                result.get("elapsed_ms"),
            )
            return None

        error = result.get("error", "Ollama is not running. Start Ollama and try again.")
        self.logger.error("Ollama startup check failed: %s", error)
        return str(error)

    def reload_ollama_provider(self) -> str | None:
        """Re-register Ollama with current config values. Returns an error message or None."""
        self.config_manager.set("provider", "ollama")
        self.config_manager.save()
        self.provider_registry.register("ollama", self._create_ollama_factory())
        self.provider_registry.activate("ollama")
        self.ollama_startup_error = self._check_ollama_startup()
        return self.ollama_startup_error
