"""AI Evals & Observability Layer: Benchmarks, Regressions, and Replays."""

import json
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
from pydantic import BaseModel, Field
from ..core.config import settings
from ..runtime.bus import AgentEvent, default_event_bus
from ..runtime.engine import HeadlessHarness


class EvalMetric(BaseModel):
    name: str
    score: float  # 0.0 to 1.0
    passed: bool
    details: Dict[str, Any] = Field(default_factory=dict)


class BenchmarkCase(BaseModel):
    id: str
    description: str
    task: str
    expected_keywords: List[str] = Field(default_factory=list)
    max_steps_allowed: int = 15


class ObservabilityTracer:
    """Live tracing engine capturing step events, tool correctness, latency, and tokens."""

    def __init__(self):
        self.traces: List[Dict[str, Any]] = []
        default_event_bus.subscribe(self._on_event)

    def _on_event(self, event: AgentEvent):
        self.traces.append({
            "run_id": event.run_id,
            "type": event.event_type,
            "timestamp": event.timestamp,
            "payload": event.payload,
        })

    def get_run_trace(self, run_id: str) -> List[Dict[str, Any]]:
        return [t for t in self.traces if t["run_id"] == run_id]


class BenchmarkRunner:
    """Executes benchmarks & regression tests against the harness engine."""

    def __init__(self, harness: Optional[HeadlessHarness] = None):
        self.harness = harness or HeadlessHarness()

    async def run_benchmark(self, case: BenchmarkCase) -> EvalMetric:
        start_time = time.time()
        run_id = f"eval_{case.id}_{int(start_time)}"
        
        try:
            result = await self.harness.execute_task(task=case.task, run_id=run_id, max_steps=case.max_steps_allowed)
            duration = time.time() - start_time

            # Verification
            matches = [kw for kw in case.expected_keywords if kw.lower() in result.lower()]
            match_score = len(matches) / max(len(case.expected_keywords), 1)
            passed = match_score >= 0.75

            return EvalMetric(
                name=f"benchmark:{case.id}",
                score=round(match_score, 2),
                passed=passed,
                details={
                    "duration_sec": round(duration, 2),
                    "matched": matches,
                    "expected": case.expected_keywords,
                },
            )
        except Exception as e:
            return EvalMetric(
                name=f"benchmark:{case.id}",
                score=0.0,
                passed=False,
                details={"error": str(e)},
            )


default_tracer_obs = ObservabilityTracer()

