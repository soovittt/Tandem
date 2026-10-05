#!/usr/bin/env python
"""Standalone browser-use worker — runs in the ISOLATED .venv-browser, never our
main venv (browser-use pins openai==2.x, which conflicts with our openai>=3.x).

Reads the task from stdin and the LLM config from the environment, runs a
browser-use agent with vision OFF (text-only: cheap, fast, and the right fit for
a text model like Nemotron), and prints the final result as one JSON line behind
a marker so the caller can parse it even if libraries scribble on stdout.
"""

import asyncio
import json
import os
import sys

MARKER = "@@BROWSE_RESULT@@"


def _force_thinking_off() -> None:
    """browser-use's ChatOpenAI exposes no extra_body, so there's no supported way
    to send Nemotron's reasoning toggle. Left on, every browser step emits a huge
    hidden chain-of-thought that blows browser-use's 75s per-call timeout and never
    converges. We wrap the OpenAI SDK's chat-completions call to always inject
    chat_template_kwargs.enable_thinking=false — fast, and the actions still stream."""
    from openai.resources.chat.completions import AsyncCompletions

    original = AsyncCompletions.create

    def patched(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        extra = dict(kwargs.get("extra_body") or {})
        ctk = dict(extra.get("chat_template_kwargs") or {})
        ctk.setdefault("enable_thinking", False)
        extra["chat_template_kwargs"] = ctk
        kwargs["extra_body"] = extra
        return original(self, *args, **kwargs)

    AsyncCompletions.create = patched


async def _run(task: str) -> dict:
    _force_thinking_off()
    from browser_use import Agent, ChatOpenAI

    llm = ChatOpenAI(
        model=os.environ["BROWSE_LLM_MODEL"],
        base_url=os.environ["BROWSE_LLM_BASE_URL"],
        api_key=os.environ.get("BROWSE_LLM_API_KEY", ""),
    )
    agent = Agent(task=task, llm=llm, use_vision=False)
    history = await agent.run(max_steps=int(os.environ.get("BROWSE_MAX_STEPS", "12")))
    try:
        result = history.final_result()
    except Exception:  # noqa: BLE001
        result = None
    return {"ok": True, "result": result or "(the agent finished but returned no summary)"}


def main() -> None:
    task = sys.stdin.read().strip()
    if not task:
        print(MARKER + json.dumps({"ok": False, "error": "empty task"}))
        return
    try:
        out = asyncio.run(_run(task))
    except Exception as exc:  # noqa: BLE001
        out = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
    print(MARKER + json.dumps(out))


if __name__ == "__main__":
    main()
