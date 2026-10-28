from typing import List, Tuple
from ..core.config import settings
from ..core.types import TokenUsage

SEARCH_PRICE = {"fast": 0.001, "advanced": 0.005}
EXTRACT_PRICE_PER_URL = 0.001
LLM_PRICE = {"input": 4.00, "cache_write": 5.00, "cache_read": 0.20, "output": 20.00}


class CostLedger:
    def __init__(self, max_usd: float = None, max_steps: int = None, max_advanced: int = 2):
        self.max_usd = max_usd if max_usd is not None else settings.max_run_usd
        self.max_steps = max_steps if max_steps is not None else settings.max_run_steps
        self.max_advanced = max_advanced
        self.usd = 0.0
        self.steps = 0
        self.advanced_calls = 0
        self.lines: List[Tuple[str, float]] = []

    def reset(self):
        self.usd = 0.0
        self.steps = 0
        self.advanced_calls = 0
        self.lines.clear()

    def charge(self, item: str, amount_usd: float):
        self.usd += amount_usd
        self.lines.append((item, round(amount_usd, 6)))

    def charge_search(self, mode: str):
        cost = SEARCH_PRICE.get(mode.lower(), SEARCH_PRICE["fast"])
        if mode.lower() == "advanced":
            self.advanced_calls += 1
        self.charge(f"parallel_search:{mode}", cost)

    def charge_extract(self, url_count: int):
        self.charge("parallel_extract", url_count * EXTRACT_PRICE_PER_URL)

    def charge_llm(self, usage: TokenUsage):
        cost = (
            usage.prompt_tokens * LLM_PRICE["input"]
            + (getattr(usage, "cached_tokens", 0) or 0) * LLM_PRICE["cache_read"]
            + usage.completion_tokens * LLM_PRICE["output"]
        ) / 1_000_000.0
        self.charge("llm_tokens", cost)

    def can_spend(self, amount_usd: float, reserve_ratio: float = 0.2) -> bool:
        return (self.usd + amount_usd) <= (self.max_usd * (1.0 - reserve_ratio))

    def is_step_limit_reached(self) -> bool:
        return self.steps >= self.max_steps

    def is_budget_exceeded(self) -> bool:
        return self.usd >= self.max_usd


default_ledger = CostLedger()
