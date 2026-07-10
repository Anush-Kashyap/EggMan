from __future__ import annotations

import logging
import threading
import subprocess
from typing import List, Optional, Tuple

from backend.profiler.request_profile import RequestProfile

logger = logging.getLogger("eggman")


from backend.registry.capability.decorators import capability

@capability(
    id="developer",
    name="Developer",
    description="Developer Telemetry, Logs, and System Profiling.",
    category="diagnostics",
    version="1.0.0"
)
class PerformanceProfiler:
    """Manages execution profiling, request history, and GPU diagnostics."""

    _instance: Optional[PerformanceProfiler] = None
    _lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> PerformanceProfiler:
        with cls._lock:
            if cls._instance is None:
                cls._instance = PerformanceProfiler()
            return cls._instance

    def __init__(self) -> None:
        self._local = threading.local()
        self.history: List[RequestProfile] = []
        self._counter = 0
        self._history_lock = threading.Lock()

    def start_request(self, user_message: str) -> Optional[RequestProfile]:
        """Initialize a new RequestProfile if Developer Mode is active."""
        from backend.session.session_manager import SessionManager
        try:
            if not SessionManager.get_instance().context.developer_mode:
                return None
        except Exception as exc:
            logger.debug("Safe fallback: SessionManager context access failed (not loaded yet?): %s", exc)
            return None

        with self._history_lock:
            self._counter += 1
            req_num = self._counter

        profile = RequestProfile(req_num, user_message)
        self._local.current_profile = profile
        
        logger.info("[DEV MODE] Request started: #%d - '%s'", req_num, user_message[:30])
        return profile

    def get_current_profile(self) -> Optional[RequestProfile]:
        """Retrieve the RequestProfile bound to the current thread context."""
        return getattr(self._local, "current_profile", None)

    def stop_stage(self, stage_name: str) -> None:
        """Stop profiling for the given stage name on the current thread's profile."""
        profile = self.get_current_profile()
        if profile:
            profile.stop_stage(stage_name)

    def start_stage(self, stage_name: str) -> None:
        """Start profiling for the given stage name on the current thread's profile."""
        profile = self.get_current_profile()
        if profile:
            profile.start_stage(stage_name)

    def finalize_request(self, model_name: str = "Unknown", memory_used: bool = False,
                         knowledge_used: bool = False, vision_used: bool = False,
                         tools_executed: bool = False) -> None:
        """Finalize, log, and append the current RequestProfile to history."""
        profile = self.get_current_profile()
        if not profile:
            return

        profile.model_name = model_name
        profile.memory_used = memory_used
        profile.knowledge_used = knowledge_used
        profile.vision_used = vision_used
        profile.tools_executed = tools_executed
        profile.finalize()

        # Append to history
        with self._history_lock:
            self.history.append(profile)
            # Limit history to latest 50 requests in memory
            if len(self.history) > 50:
                self.history.pop(0)

        # Clear active profile from thread local
        self._local.current_profile = None

        logger.info(
            "[DEV MODE] Request completed: #%d | Duration: %.2fs | Model: %s | Stages: %s",
            profile.request_num,
            profile.total_time,
            profile.model_name,
            {k: f"{v:.3f}s" for k, v in profile.stages.items()}
        )

    def get_gpu_diagnostics(self) -> Tuple[str, str]:
        """Detect GPU and approximate VRAM information using wmic on Windows."""
        try:
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            # Query GPU name and AdapterRAM (VRAM in bytes)
            res = subprocess.run(
                ["wmic", "path", "win32_VideoController", "get", "name,AdapterRAM"],
                capture_output=True, text=True, startupinfo=startupinfo, timeout=2.0
            )
            if res.returncode == 0:
                lines = [line.strip() for line in res.stdout.split("\n") if line.strip()]
                if len(lines) > 1:
                    # Parse name and VRAM from output
                    for line in lines[1:]:
                        parts = line.split()
                        if len(parts) >= 2:
                            # Try to parse VRAM bytes from first column
                            try:
                                vram_bytes = int(parts[0])
                                vram_gb = f"{vram_bytes / (1024**3):.1f} GB"
                            except ValueError:
                                vram_gb = "Unknown"
                            gpu_name = " ".join(parts[1:])
                            if gpu_name:
                                return gpu_name, vram_gb
        except Exception as exc:
            logger.debug("GPU diagnostics query failed (safe fallback to N/A): %s", exc)
        return "N/A", "N/A"
