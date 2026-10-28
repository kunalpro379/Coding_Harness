"""Core Configuration Management for the Coding Harness."""

import os
from pathlib import Path
from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Production Settings loaded from Environment Variables or .env."""

    model_config = SettingsConfigDict(
        env_file=(".env", str(Path.home() / ".agents" / "env")),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # LLM Settings
    base_url: str = Field(
        default="https://integrate.api.nvidia.com/v1",
        description="LLM provider Base URL (NVIDIA NIM, OpenAI, DeepSeek, etc.)",
    )
    api_key: str = Field(
        default="dummy-key",
        description="API Key for the provider",
    )
    model: str = Field(
        default="nvidia/nemotron-3.5-bolt-e4b",
        description="Default LLM model identifier",
    )
    fallback_model: Optional[str] = Field(
        default=None,
        description="Optional fallback model on rate limits",
    )

    # Token & Context Window
    context_window: int = Field(
        default=128_000,
        description="Max token context window of primary model",
    )
    compact_at: float = Field(
        default=0.82,
        description="Ratio of context window that triggers proactive compaction",
    )
    compact_to: float = Field(
        default=0.35,
        description="Ratio of context window to retain when compacting",
    )

    # Workspace & Limits
    workspace_root: Path = Field(
        default_factory=Path.cwd,
        description="Current workspace root directory",
    )
    subagent_max_turns: int = Field(
        default=15,
        description="Maximum turns allowed for an exploration subagent",
    )
    tool_timeout_seconds: int = Field(
        default=30,
        description="Maximum execution seconds for shell commands",
    )
    max_tool_output_chars: int = Field(
        default=10_000,
        description="Max characters of tool output before paging/spilling to disk",
    )
    tool_stub_chars: int = Field(
        default=300,
        description="Characters kept after a turn finishes (turn stripping)",
    )

    # Security & Sandbox Mode
    auto_approve_readonly: bool = Field(
        default=True,
        description="Auto-approve read-only tools (read_file, find, inspect)",
    )
    require_approval_commands: bool = Field(
        default=False,
        description="Prompt user before running destructive bash commands",
    )
    no_sandbox: bool = Field(
        default=False,
        description="Disable sandbox isolation; allow full OS filesystem and execution freedom",
    )
    desktop_enabled: bool = Field(
        default=True,
        description="Enable desktop GUI automation tools (mouse, keyboard, screenshot, window management)",
    )

    # Parallel Search & Cost Budget Ledger
    parallel_api_key: Optional[str] = Field(
        default=None,
        description="Parallel Search API Key from platform.parallel.ai",
    )
    parallel_search_mode: str = Field(
        default="fast",
        description="Default Parallel Search mode ('fast' or 'advanced')",
    )
    max_run_usd: float = Field(
        default=1.00,
        description="Maximum USD cost budget per agent run",
    )
    max_run_steps: int = Field(
        default=25,
        description="Maximum execution tool steps per user turn",
    )


settings = Settings()
