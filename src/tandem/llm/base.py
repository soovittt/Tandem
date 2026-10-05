"""
The LLM backend interface.

The rest of the app depends on THIS protocol, never on a concrete provider. That
is dependency inversion: swap Nebius for NVIDIA, or a fake for tests, and nothing
above this line changes.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any, Protocol

from tandem.domain.message import ToolCall, WireMessage


@dataclass
class ChatResult:
    """One model response, in the form the agent loop needs."""

    text: str                    # the assistant's text (may be empty if it called tools)
    tool_calls: list[ToolCall]   # tools it wants to run (empty => it's done)
    assistant_message: WireMessage  # the raw message to append back to history verbatim
    prompt_tokens: int           # PREFILL cost (see the KV-cache discussion)
    completion_tokens: int       # DECODE cost


class StreamingHandle(Protocol):
    """A streaming completion: iterate for content-token deltas, then read `result`
    (populated once the iterator is exhausted)."""

    result: ChatResult | None

    def __iter__(self) -> Iterator[str]: ...


class LLMBackend(Protocol):
    """Anything that can turn a message list (+ optional tools) into a reply."""

    def chat(
        self,
        messages: list[WireMessage],
        *,
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> ChatResult: ...

    def chat_stream(
        self,
        messages: list[WireMessage],
        *,
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> StreamingHandle: ...
