"""
The concrete LLM backend for OpenAI-compatible endpoints (Nebius, NVIDIA, ...).

This is the ONLY file that imports the openai SDK. If we ever change providers or
SDKs, this is the single file that changes.
"""

from __future__ import annotations

import json
from typing import Any

from openai import OpenAI

from tandem.config import LLMConfig
from tandem.domain.message import ToolCall, WireMessage
from tandem.llm.base import ChatResult


class OpenAICompatibleLLM:
    """Implements LLMBackend against any OpenAI-compatible chat endpoint."""

    def __init__(self, config: LLMConfig) -> None:
        self._model = config.model
        self._client = OpenAI(base_url=config.base_url, api_key=config.api_key)

    def chat(
        self,
        messages: list[WireMessage],
        *,
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> ChatResult:
        # Build kwargs so we omit `tools` entirely when there are none (some
        # servers reject an empty list).
        kwargs: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if tools:
            kwargs["tools"] = tools

        response = self._client.chat.completions.create(**kwargs)
        choice = response.choices[0].message

        tool_calls = _parse_tool_calls(choice.tool_calls)
        usage = response.usage

        return ChatResult(
            text=choice.content or "",
            tool_calls=tool_calls,
            assistant_message=_assistant_message(choice.content, choice.tool_calls),
            prompt_tokens=getattr(usage, "prompt_tokens", 0) or 0,
            completion_tokens=getattr(usage, "completion_tokens", 0) or 0,
        )


def _parse_tool_calls(raw_tool_calls: Any) -> list[ToolCall]:
    """Turn the SDK's tool_call objects into our typed, ready-to-dispatch form."""
    if not raw_tool_calls:
        return []
    parsed: list[ToolCall] = []
    for tc in raw_tool_calls:
        try:
            arguments = json.loads(tc.function.arguments or "{}")
        except json.JSONDecodeError:
            arguments = {}  # model produced malformed JSON; treat as no args
        parsed.append(ToolCall(id=tc.id, name=tc.function.name, arguments=arguments))
    return parsed


def _assistant_message(content: str | None, raw_tool_calls: Any) -> WireMessage:
    """
    Rebuild the assistant message exactly as it must be appended to history.

    We keep the original `arguments` STRING (not our parsed dict) so the message
    we send back matches what the model produced -- servers can be picky here.
    """
    message: WireMessage = {"role": "assistant", "content": content or ""}
    if raw_tool_calls:
        message["tool_calls"] = [
            {
                "id": tc.id,
                "type": "function",
                "function": {"name": tc.function.name, "arguments": tc.function.arguments},
            }
            for tc in raw_tool_calls
        ]
    return message
