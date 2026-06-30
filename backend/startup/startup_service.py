from __future__ import annotations

import enum
import threading
import time
import logging
from typing import Dict, Optional, Callable, Any

logger = logging.getLogger("eggman")


class StartupState(enum.Enum):
    INITIALIZING = "INITIALIZING"
    READY = "READY"
    ERROR = "ERROR"


class StartupProfile:
    """Holds timing data for each startup stage."""

    def __init__(self) -> None:
        self.stages: Dict[str, float] = {}
        self._running: Dict[str, float] = {}
        self.total_time: float = 0.0
        self.status: str = StartupState.INITIALIZING.value
        self._start: float = time.perf_counter()

    def start_stage(self, name: str) -> None:
        self._running[name] = time.perf_counter()

    def stop_stage(self, name: str) -> None:
        if name in self._running:
            self.stages[name] = time.perf_counter() - self._running.pop(name)

    def finalize(self, state: StartupState) -> None:
        self.total_time = time.perf_counter() - self._start
        self.status = state.value
        # Close any still-running stages gracefully
        for name in list(self._running.keys()):
            self.stages[name] = time.perf_counter() - self._running.pop(name)


class StartupService:
    """
    Manages EggMan's parallel startup sequence.

    Usage
    -----
    - Create with a populated AppContainer.
    - Call run_async(on_ready, on_error) to begin background init.
    - Check state / profile from the main thread.
    """

    # Internal slash commands always allowed, even during init
    ALWAYS_ALLOWED_COMMANDS = {"/help", "/schedule", "/file", "/dev", "/clear", "/export", "/settings", "/theme"}

    def __init__(self, container: Any) -> None:
        self._container = container
        self._state = StartupState.INITIALIZING
        self._lock = threading.Lock()
        self.profile = StartupProfile()
        self._on_ready: Optional[Callable[[], None]] = None
        self._on_error: Optional[Callable[[str], None]] = None

    # ------------------------------------------------------------------ state

    @property
    def state(self) -> StartupState:
        with self._lock:
            return self._state

    @property
    def is_ready(self) -> bool:
        return self.state == StartupState.READY

    # ---------------------------------------------------------------- blocking check

    def should_block_message(self, message: str) -> bool:
        """Return True if a message should be blocked during startup initialization."""
        if self.is_ready:
            return False
        stripped = message.strip().lower()
        if stripped.startswith("/"):
            command = stripped.split()[0]
            if command in self.ALWAYS_ALLOWED_COMMANDS:
                return False
        return True

    # ----------------------------------------------------------------- async start

    def run_async(
        self,
        on_ready: Callable[[], None],
        on_error: Callable[[str], None],
    ) -> None:
        """Launch background initialization. Calls on_ready or on_error from the background thread."""
        self._on_ready = on_ready
        self._on_error = on_error
        t = threading.Thread(target=self._run, daemon=True, name="StartupService")
        t.start()

    # ------------------------------------------------------------------ pipeline

    def _run(self) -> None:
        logger.info("[STARTUP] Startup sequence started")
        error_message: Optional[str] = None

        try:
            # Phase 1: All independent startup tasks run concurrently
            concurrent_stages = {
                "SessionContext": self._init_session,
                "Scheduler": self._init_scheduler,
                "Voice Initialization": self._init_voice,
                "Configuration": self._verify_config,
                "Ollama Connection": self._connect_ollama,
            }

            # Start all stage timers before launching threads
            for stage_name in concurrent_stages:
                self.profile.start_stage(stage_name)

            threads = []
            for stage_name, fn in concurrent_stages.items():
                t = threading.Thread(target=fn, daemon=True, name=f"Startup-{stage_name}")
                threads.append(t)
                t.start()

            for t in threads:
                t.join()

            # Phase 2: Model warm-up depends on Ollama being available
            self.profile.start_stage("Model Warm-Up")
            self._warmup_model()

            # Phase 3: Reminder check depends on scheduler being initialized
            self.profile.start_stage("Reminder Check")
            self._check_reminders()

            # Finalize
            self.profile.finalize(StartupState.READY)
            with self._lock:
                self._state = StartupState.READY

            logger.info("[STARTUP] Startup completed successfully in %.2fs", self.profile.total_time)
            logger.info(
                "[STARTUP] Stage breakdown: %s",
                {k: f"{v:.3f}s" for k, v in self.profile.stages.items()},
            )

            if self._on_ready:
                self._on_ready()

        except Exception as exc:
            logger.exception("[STARTUP] Startup failed: %s", exc)
            error_message = str(exc)
            self.profile.finalize(StartupState.ERROR)
            with self._lock:
                self._state = StartupState.ERROR
            if self._on_error:
                self._on_error(error_message)

    # ---------------------------------------------------------------- stages

    def _init_session(self) -> None:
        try:
            from backend.session.session_manager import SessionManager
            ctx = SessionManager.get_instance().context
            dev_mode = bool(self._container.settings_manager.get("developer_mode", False))
            ctx.developer_mode = dev_mode
            logger.info("[STARTUP] SessionContext initialized developer_mode=%s", dev_mode)
        except Exception as exc:
            logger.error("[STARTUP] SessionContext init failed: %s", exc)
        finally:
            self.profile.stop_stage("SessionContext")

    def _init_scheduler(self) -> None:
        try:
            if hasattr(self._container, "scheduler"):
                # Scheduler starts its own thread on construction; nothing extra needed here
                logger.info("[STARTUP] Scheduler initialized")
        except Exception as exc:
            logger.error("[STARTUP] Scheduler init failed: %s", exc)
        finally:
            self.profile.stop_stage("Scheduler")

    def _init_voice(self) -> None:
        try:
            # Voice subsystem is initialized lazily; pre-validate it exists
            if hasattr(self._container, "voice_manager"):
                logger.info("[STARTUP] Voice subsystem ready")
        except Exception as exc:
            logger.error("[STARTUP] Voice init failed: %s", exc)
        finally:
            self.profile.stop_stage("Voice Initialization")

    def _verify_config(self) -> None:
        try:
            cfg = self._container.config_manager
            _ = cfg.get("ollama_model")
            _ = cfg.get("ollama_base_url")
            logger.info("[STARTUP] Configuration verified")
        except Exception as exc:
            logger.error("[STARTUP] Configuration verification failed: %s", exc)
        finally:
            self.profile.stop_stage("Configuration")

    def _connect_ollama(self) -> None:
        try:
            from backend.ai.ollama_provider import OllamaProvider
            provider = OllamaProvider(
                base_url=self._container.config_manager.get("ollama_base_url"),
                model_name=self._container.config_manager.get("ollama_model"),
            )
            result = provider.test_connection()
            if result.get("ok"):
                self._container.ollama_startup_error = None
                logger.info(
                    "[STARTUP] Ollama connected model=%s elapsed_ms=%.1f",
                    result.get("model"),
                    result.get("elapsed_ms", 0),
                )
            else:
                err = result.get("error", "Unknown error")
                logger.warning("[STARTUP] Ollama connection failed: %s", err)
                self._container.ollama_startup_error = str(err)
        except Exception as exc:
            logger.error("[STARTUP] Ollama connection error: %s", exc)
            self._container.ollama_startup_error = str(exc)
        finally:
            self.profile.stop_stage("Ollama Connection")

    def _warmup_model(self) -> None:
        try:
            if self._container.ollama_startup_error:
                logger.warning("[STARTUP] Skipping model warm-up — Ollama not available")
                return

            logger.info("[STARTUP] Model warm-up started")
            from backend.ai.ollama_provider import OllamaProvider
            from backend.ai.models import AIRequest
            provider = OllamaProvider(
                base_url=self._container.config_manager.get("ollama_base_url"),
                model_name=self._container.config_manager.get("ollama_model"),
            )
            warmup_request = AIRequest(
                system_prompt="",
                user_message="READY",
                conversation_history=[],
                images=[],
            )
            t_start = time.perf_counter()
            response = provider.generate(warmup_request)
            elapsed = time.perf_counter() - t_start

            if response.successful:
                logger.info("[STARTUP] Model warm-up completed in %.2fs", elapsed)
            else:
                logger.warning("[STARTUP] Model warm-up completed with error: %s (continuing)", response.error)
        except Exception as exc:
            logger.error("[STARTUP] Model warm-up failed: %s — continuing anyway", exc)
        finally:
            self.profile.stop_stage("Model Warm-Up")

    def _check_reminders(self) -> None:
        try:
            if hasattr(self._container, "task_repository"):
                tasks = self._container.task_repository.get_all_tasks()
                overdue_count = len(tasks) if tasks else 0
                logger.info("[STARTUP] Reminder check done active_tasks=%d", overdue_count)
        except Exception as exc:
            logger.error("[STARTUP] Reminder check failed: %s", exc)
        finally:
            self.profile.stop_stage("Reminder Check")
