"""
The concrete LLM backend for OpenAI-compatible endpoints (Nebius, NVIDIA, ...).

This is the ONLY file that imports the openai SDK. If we ever change providers or
SDKs, this is the single file that changes.
"""

from __future__ import annotations

import json
from typing import Any

from openai import OpenAI

from collections.abc import Iterator

from tandem.config import LLMConfig
from tandem.domain.message import ToolCall, WireMessage
from tandem.llm.base import ChatResult


class OpenAICompatibleLLM:
    """Implements LLMBackend against any OpenAI-compatible chat endpoint."""

    def __init__(self, config: LLMConfig) -> None:
        self._model = config.model
        self._reasoning = config.reasoning
        self._client = OpenAI(base_url=config.base_url, api_key=config.api_key)

    def _request_kwargs(
        self,
        messages: list[WireMessage],
        tools: list[dict[str, Any]] | None,
        temperature: float,
        max_tokens: int,
    ) -> dict[str, Any]:
        # Omit `tools` entirely when there are none (some servers reject an empty list).
        kwargs: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if tools:
            kwargs["tools"] = tools
        # Nemotron-3's reasoning toggle rides in chat_template_kwargs (the old
        # "detailed thinking off" system line is a no-op on this model). With
        # thinking off the model skips its hidden chain-of-thought — fast, and it
        # never blows the token budget mid-thought (which would truncate the
        # tool_call and surface as an empty "couldn't handle that" reply).
        if self._reasoning in ("off", "on"):
            kwargs["extra_body"] = {
                "chat_template_kwargs": {"enable_thinking": self._reasoning == "on"}
            }
        return kwargs

    def chat(
        self,
        messages: list[WireMessage],
        *,
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> ChatResult:
        response = self._client.chat.completions.create(
            **self._request_kwargs(messages, tools, temperature, max_tokens)
        )
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

    def chat_stream(
        self,
        messages: list[WireMessage],
        *,
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> "StreamingCompletion":
        """Stream the reply. Iterate it for content deltas; afterwards its `.result`
        holds the assembled ChatResult (full text + reassembled tool_calls)."""
        raw = self._client.chat.completions.create(
            stream=True, **self._request_kwargs(messages, tools, temperature, max_tokens)
        )
        return StreamingCompletion(raw)


class StreamingCompletion:
    """A streaming chat response. Iterating yields content-token deltas; once the
    iterator is exhausted, `.result` holds the full ChatResult (text + tool_calls
    reassembled from their streamed fragments)."""

    def __init__(self, raw_stream: Any) -> None:
        self._raw = raw_stream
        self.result: ChatResult | None = None

    def __iter__(self) -> Iterator[str]:
        content: list[str] = []
        calls: dict[int, dict[str, Any]] = {}
        for chunk in self._raw:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            if getattr(delta, "content", None):
                content.append(delta.content)
                yield delta.content
            for tc in getattr(delta, "tool_calls", None) or []:
                slot = calls.setdefault(tc.index, {"id": None, "name": None, "args": ""})
                if tc.id:
                    slot["id"] = tc.id
                if tc.function and tc.function.name:
                    slot["name"] = tc.function.name
                if tc.function and tc.function.arguments:
                    slot["args"] += tc.function.arguments
        self.result = self._assemble("".join(content), calls)

    @staticmethod
    def _assemble(text: str, calls: dict[int, dict[str, Any]]) -> ChatResult:
        tool_calls: list[ToolCall] = []
        raw_msgs: list[dict[str, Any]] = []
        for idx in sorted(calls):
            c = calls[idx]
            if not c["name"]:
                continue
            cid = c["id"] or f"call_{idx}"
            raw_args = c["args"] or "{}"
            try:
                args = json.loads(raw_args)
            except json.JSONDecodeError:
                args = {}
            tool_calls.append(ToolCall(id=cid, name=c["name"], arguments=args))
            raw_msgs.append(
                {"id": cid, "type": "function", "function": {"name": c["name"], "arguments": raw_args}}
            )
        message: WireMessage = {"role": "assistant", "content": text}
        if raw_msgs:
            message["tool_calls"] = raw_msgs
        return ChatResult(
            text=text, tool_calls=tool_calls, assistant_message=message,
            prompt_tokens=0, completion_tokens=0,
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
