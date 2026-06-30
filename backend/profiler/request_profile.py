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

        # Egg Inspector v2 Metrics
        self.prompt_tokens: int = 0
        self.output_tokens: int = 0
        self.total_tokens: int = 0
        self.prompt_char_count: int = 0
        self.provider: str = "ollama"
        self.keep_alive: str = "5m (default)"
        self.model_state: str = "Warm"  # "Warm" or "Cold"
        self.first_token_latency: float = 0.0
        self.generation_speed: float = 0.0  # tokens/sec
        self.request_classification: str = "General"
        self.complexity_score: int = 1  # 1-10 future complexity heuristic placeholder
        self.load_duration: float = 0.0
        self.prompt_eval_duration: float = 0.0
        self.eval_duration: float = 0.0

        # Token breakdown
        self.system_prompt_tokens: int = 0
        self.user_prompt_tokens: int = 0
        self.history_tokens: int = 0

    def start_stage(self, stage_name: str) -> None:
        """Record the start time of a performance profiling stage."""
        self._running_stages[stage_name] = time.perf_counter()

    def stop_stage(self, stage_name: str) -> None:
        """Record the stop time and compute elapsed duration for a stage."""
        if stage_name in self._running_stages:
            elapsed = time.perf_counter() - self._running_stages.pop(stage_name)
            # Accumulate if stage was already run (e.g. streaming chunks)
            self.stages[stage_name] = self.stages.get(stage_name, 0.0) + elapsed
            
            # Record first token latency specifically when Ollama First Token finishes
            if stage_name == "Ollama First Token" or stage_name == "Vision Processing":
                self.first_token_latency = self.stages[stage_name]

    def finalize(self) -> None:
        """Calculate total request duration and clean up pending stages."""
        self.total_time = time.perf_counter() - self.start_time
        # Stop any remaining running stages to ensure timings are captured
        for stage_name in list(self._running_stages.keys()):
            self.stop_stage(stage_name)

        # Compute calculated metrics
        self.total_tokens = self.prompt_tokens + self.output_tokens
        if self.eval_duration > 0:
            self.generation_speed = self.output_tokens / self.eval_duration
        elif self.stages.get("Response Generation", 0) > 0:
            self.generation_speed = self.output_tokens / self.stages["Response Generation"]
        else:
            self.generation_speed = 0.0

        if self.load_duration > 0.5:
            self.model_state = "Cold"
        else:
            self.model_state = "Warm"

        # Safe fallback for first token latency if not explicitly set
        if self.first_token_latency == 0.0:
            self.first_token_latency = self.stages.get("Ollama First Token", 0.0) or self.stages.get("Vision Processing", 0.0)
