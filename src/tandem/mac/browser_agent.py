"""A real-browser automation sub-agent.

Playwright-style primitives driven by our generic loop aren't enough for messy
live sites, so we delegate whole web tasks to **browser-use** — a specialized
agent loop (navigate / click / type / extract, self-correcting) that is the
proven open-source harness for this. It runs in an isolated venv (it pins
openai==2.x) and we drive it over a subprocess; our harness just hands it a goal
and relays the result. Set it up once with infra/setup-browser.sh.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any

from tandem.config import LLMConfig
from tandem.domain.tool import ToolResult
from tandem.tools.base import Tool

_REPO_ROOT = Path(__file__).resolve().parents[3]
_BROWSER_PYTHON = _REPO_ROOT / ".venv-browser/bin/python"
_WORKER = Path(__file__).resolve().parent / "browse_worker.py"
_MARKER = "@@BROWSE_RESULT@@"

# Model ROUTING: the main command-bar agent runs on Nano (snappy), but browsing
# feeds the model huge per-step page payloads — Nano times out on content-heavy
# pages (HN: 240s+), while Super finishes the same task in ~14s with better
# extraction. So the browser sub-agent uses Super by default (override via env).
_DEFAULT_BROWSE_MODEL = "nvidia/nemotron-3-super-120b-a12b"


def is_available() -> bool:
    """True once infra/setup-browser.sh has built the isolated browser venv."""
    return _BROWSER_PYTHON.exists()


class WebTaskTool(Tool):
    name = "web_task"
    description = (
        "Do a multi-step task in a REAL web browser: search, navigate, click, fill "
        "forms, log in, and pull information from any website. Give ONE clear goal — "
        "e.g. 'find 3 direct flights JFK→SFO next Friday under $400 with times and "
        "airlines' or 'get the top 5 Hacker News story titles and their points'. "
        "Returns what it found. Use this for anything on the web beyond reading the "
        "page the user is already viewing (that's browser_active_tab)."
    )
    parameters = {
        "type": "object",
        "properties": {
            "task": {"type": "string", "description": "The web task / goal, stated clearly."},
            "max_steps": {"type": "integer", "description": "Max browser steps (default 12)."},
        },
        "required": ["task"],
    }
    requires_approval = True  # it acts autonomously on the live web

    def __init__(self, llm: LLMConfig) -> None:
        self._llm = llm

    def run(self, **kwargs: Any) -> ToolResult:
        task = str(kwargs.get("task", "")).strip()
        if not task:
            return ToolResult(content="Give me a clear web task to do.")
        if not is_available():
            return ToolResult(
                content="The browser sub-agent isn't installed yet — run "
                "infra/setup-browser.sh once (it sets up browser-use + Chromium in an "
                "isolated venv), then restart the backend."
            )
        env = {
            "BROWSE_LLM_BASE_URL": self._llm.base_url,
            "BROWSE_LLM_API_KEY": self._llm.api_key,
            "BROWSE_LLM_MODEL": os.getenv("TANDEM_BROWSE_MODEL") or _DEFAULT_BROWSE_MODEL,
            "BROWSE_MAX_STEPS": str(int(kwargs.get("max_steps", 12) or 12)),
            "BROWSER_USE_LOGGING_LEVEL": "result",
            "ANONYMIZED_TELEMETRY": "false",  # private assistant — no phone-home
            "PATH": os.environ.get("PATH", ""),
            "HOME": os.environ.get("HOME", ""),
        }
        try:
            proc = subprocess.run(
                [str(_BROWSER_PYTHON), str(_WORKER)],
                input=task,
                capture_output=True,
                text=True,
                timeout=300,
                env=env,
            )
        except subprocess.TimeoutExpired:
            return ToolResult(content="The web task ran over 5 minutes and was stopped.")
        payload = _extract(proc.stdout)
        if payload is None:
            tail = (proc.stderr or proc.stdout or "no output").strip()[-300:]
            return ToolResult(content=f"The browser sub-agent returned no result. Last output: {tail}")
        if not payload.get("ok"):
            return ToolResult(content=f"Web task failed: {payload.get('error', 'unknown error')}")
        return ToolResult(content=str(payload.get("result") or "(done — nothing to report)"))


def _extract(stdout: str) -> dict | None:
    """Pull the JSON payload that follows the last marker line in stdout."""
    idx = stdout.rfind(_MARKER)
    if idx == -1:
        return None
    try:
        return json.loads(stdout[idx + len(_MARKER):].strip().splitlines()[0])
    except Exception:  # noqa: BLE001
        return None
