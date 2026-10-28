"""Remote Adapters: Webhook, Cron, and CLI runners for headless execution."""

import asyncio
from typing import Any, Dict, Optional
from ..core.types import Message, Role
from .engine import HeadlessHarness


class WebhookAdapter:
    """Handles external HTTP webhooks (e.g., Slack bot, GitHub issue, Linear webhook) to trigger runs."""

    def __init__(self, harness: Optional[HeadlessHarness] = None):
        self.harness = harness or HeadlessHarness()

    async def handle_payload(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        task = payload.get("task") or payload.get("text") or payload.get("message")
        if not task:
            return {"status": "error", "message": "No task found in payload"}

        run_id = payload.get("run_id") or payload.get("event_id")
        result = await self.harness.execute_task(task=task, run_id=run_id)
        return {
            "status": "completed",
            "run_id": run_id,
            "result": result,
        }


class CronAdapter:
    """Scheduled autonomous runner for nightly jobs, test suite audits, and repo maintenance."""

    def __init__(self, harness: Optional[HeadlessHarness] = None):
        self.harness = harness or HeadlessHarness()

    async def execute_job(self, job_name: str, task: str) -> str:
        run_id = f"cron_{job_name}"
        return await self.harness.execute_task(task=task, run_id=run_id)

