from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from backend.ai.ai_engine import AIEngine
from backend.ai.models import AIRequest, AIResponse
from backend.ai.provider_registry import ProviderRegistry
from backend.ai.gemini_provider import GeminiProvider
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
from backend.tools.builtins import ApplicationRegistry, AppLauncherTool, CalculatorTool, ClipboardTool
from backend.tools.registry import ToolRegistry
from backend.tools.router import ToolRouter
from backend.tools.tool_manager import ToolManager
from core.commands import CommandHandler
from core.config import ConfigManager
from core.conversation import ConversationEngine
from core.logger import AppLogger
from core.paths import APP_ROOT, IS_FROZEN, RESOURCE_ROOT, USER_DATA_ROOT
from core.providers import LocalProvider
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
        self.provider_registry.register(
            "gemini",
            lambda: GeminiProvider(api_key=self.config_manager.get("gemini_api_key") or None),
        )

        provider_key = str(self.config_manager.get("provider", "local"))
        gemini_key_configured = bool(
            self.config_manager.get("gemini_api_key")
            or os.getenv("GEMINI_API_KEY")
            or os.getenv("EGGMAN_GEMINI_API_KEY")
        )
        if provider_key == "gemini" and not gemini_key_configured:
            self.logger.warning("Gemini provider selected but no API key is configured; falling back to local provider")
            provider_key = "local"
        if not self.provider_registry.activate(provider_key):
            self.provider_registry.activate("local")

        provider_cls = self.provider_registry.get()
        self.provider = LocalProvider()
        self.logger.info(
            "Provider registry initialized active=%s available=%s gemini_key_configured=%s",
            self.provider_registry.active_provider_name(),
            self.provider_registry.available_providers(),
            gemini_key_configured,
        )

        self.ai_engine = AIEngine(
            context_builder=self.context_builder,
            memory_manager=self.memory_manager,
            provider_registry=self.provider_registry,
            tool_router=self.tool_router,
            logger=self.logger._logger,
        )
        self.conversation_engine = ConversationEngine(ai_engine=self.ai_engine)

        self.logger.info("Application services initialized")
