from __future__ import annotations

import time
from typing import Dict, Optional, Any


class RequestProfile:
    """Holds timing and metadata metrics for a single request lifecycle."""

    def __init__(self, request_num: int, user_message: str) -> None:
        self.request_num = request_num
        self.user_message = user_message
        self.start_time = time.perf_counter()
        self.total_time: float = 0.0
        
        # Meta flags
        self.model_name: str = "Unknown"
        self.memory_used: bool = False
        self.knowledge_used: bool = False
        self.vision_used: bool = False
        self.tools_executed: bool = False

        # Stage timings: stage_name -> elapsed_seconds
        self.stages: Dict[str, float] = {}
        self._running_stages: Dict[str, float] = {}

    def start_stage(self, stage_name: str) -> None:
        """Record the start time of a performance profiling stage."""
        self._running_stages[stage_name] = time.perf_counter()

    def stop_stage(self, stage_name: str) -> None:
        """Record the stop time and compute elapsed duration for a stage."""
        if stage_name in self._running_stages:
            elapsed = time.perf_counter() - self._running_stages.pop(stage_name)
            # Accumulate if stage was already run (e.g. streaming chunks)
            self.stages[stage_name] = self.stages.get(stage_name, 0.0) + elapsed

    def finalize(self) -> None:
        """Calculate total request duration and clean up pending stages."""
        self.total_time = time.perf_counter() - self.start_time
        # Stop any remaining running stages to ensure timings are captured
        for stage_name in list(self._running_stages.keys()):
            self.stop_stage(stage_name)
