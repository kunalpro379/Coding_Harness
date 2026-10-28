"""Persistent Run & Checkpoint Store tracking state, steps, and execution status."""

import json
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from ..core.config import settings


class RunStatus(str, Enum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class AgentRun(BaseModel):
    id: str
    status: RunStatus = RunStatus.QUEUED
    task: str
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    result: Optional[str] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class RunStore:
    """Persists Run records & checkpoints on disk for replay and state-machine tracking."""

    def __init__(self, storage_dir: Optional[Path] = None):
        base = storage_dir or (Path.home() / ".agents" / "runs")
        self.dir = base
        self.dir.mkdir(parents=True, exist_ok=True)

    def _path(self, run_id: str) -> Path:
        return self.dir / f"{run_id}.json"

    def create(self, run_id: str, task: str, metadata: Optional[Dict[str, Any]] = None) -> AgentRun:
        run = AgentRun(id=run_id, task=task, metadata=metadata or {})
        self.save(run)
        return run

    def save(self, run: AgentRun):
        run.updated_at = datetime.now().isoformat()
        with open(self._path(run.id), "w", encoding="utf-8") as f:
            f.write(run.model_dump_json(indent=2))

    def get(self, run_id: str) -> Optional[AgentRun]:
        p = self._path(run_id)
        if not p.exists():
            return None
        return AgentRun.model_validate_json(p.read_text(encoding="utf-8"))

    def list_runs(self) -> List[AgentRun]:
        runs = []
        for file in sorted(self.dir.glob("*.json"), key=lambda f: f.stat().st_mtime, reverse=True):
            try:
                runs.append(AgentRun.model_validate_json(file.read_text(encoding="utf-8")))
            except Exception:
                pass
        return runs


default_run_store = RunStore()

