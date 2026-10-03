"""
Application configuration -- the single place that reads the environment.

Nothing else in the codebase touches os.environ. Everything is handed a typed
config object, which keeps the rest of the code pure and testable.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


# Known OpenAI-compatible endpoints. Confirm exact model IDs in each console.
PRESETS: dict[str, dict[str, str]] = {
    "nebius": {
        "base_url": "https://api.studio.nebius.com/v1/",
        "model": "nvidia/Llama-3_1-Nemotron-70B-Instruct",
    },
    "nvidia": {
        "base_url": "https://integrate.api.nvidia.com/v1",
        "model": "nvidia/llama-3.1-nemotron-70b-instruct",
    },
}


@dataclass(frozen=True)
class LLMConfig:
    """Everything needed to reach a served model."""

    base_url: str
    api_key: str
    model: str


@dataclass(frozen=True)
class AppConfig:
    """Top-level config: the model + where local data lives."""

    llm: LLMConfig
    data_dir: Path
    db_path: Path
    skills_dir: Path
    tavily_api_key: str | None
    memory_backend: str  # "mem0" (semantic, self-hosted) or "sqlite" (keyword fallback)
    tool_mode: str       # "native" (OpenAI tool_calls) or "prompt" (harness parses <toolcall>)
    reasoning: str       # "off" | "on" | "none" -- Nemotron "detailed thinking" directive

    @classmethod
    def from_env(cls) -> "AppConfig":
        provider = os.getenv("LLM_PROVIDER", "nebius").lower()
        preset = PRESETS.get(provider, PRESETS["nebius"])

        api_key = os.getenv("LLM_API_KEY", "")
        if not api_key:
            raise RuntimeError(
                "LLM_API_KEY is not set. Copy .env.example to .env and add your key."
            )

        llm = LLMConfig(
            base_url=os.getenv("LLM_BASE_URL") or preset["base_url"],
            api_key=api_key,
            model=os.getenv("LLM_MODEL") or preset["model"],
        )

        data_dir = Path(os.getenv("TANDEM_DATA_DIR", ".tandem")).expanduser()
        return cls(
            llm=llm,
            data_dir=data_dir,
            db_path=data_dir / "memory.db",
            skills_dir=data_dir / "skills",
            tavily_api_key=os.getenv("TAVILY_API_KEY") or None,
            memory_backend=os.getenv("MEMORY_BACKEND", "sqlite").lower(),
            tool_mode=os.getenv("TOOL_MODE", "native").lower(),
            reasoning=os.getenv("LLM_REASONING", "off").lower(),
        )
