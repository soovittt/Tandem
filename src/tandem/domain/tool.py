"""Types produced by tools: their result text plus any sources cited."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Source:
    """A citation. Every factual claim the agent makes should trace to one."""

    title: str
    url: str


@dataclass
class ToolResult:
    """What a tool hands back: text for the model, plus sources for the user."""

    content: str
    sources: list[Source] = field(default_factory=list)
