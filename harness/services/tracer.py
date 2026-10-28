import json
import time
import uuid
from pathlib import Path
from typing import Any, Dict
from ..core.config import settings


class ExecutionTracer:
    def __init__(self, run_id: str = None):
        self.run_id = run_id or uuid.uuid4().hex[:12]
        self.trace_file = settings.workspace_root / ".traces" / f"trace_{self.run_id}.jsonl"
        self.trace_file.parent.mkdir(parents=True, exist_ok=True)

    def log(self, event: str, **kwargs: Any):
        entry = {
            "run": self.run_id,
            "timestamp": time.time(),
            "event": event,
            **kwargs,
        }
        with open(self.trace_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")


default_tracer = ExecutionTracer()
