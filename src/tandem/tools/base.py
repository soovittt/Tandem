"""
The Tool abstraction and the registry that holds them.

A Tool is a capability the model can call. Each one declares:
  - name/description  -> so the model knows what it is and when to use it
  - parameters        -> a JSON Schema describing its arguments (the model fills it)
  - requires_approval -> whether a human must okay it before it runs
  - run(**kwargs)     -> the actual behavior, returning a ToolResult

The ToolRegistry is the single collection the agent asks for (a) the JSON specs
to send the model and (b) the tool object to execute a call. New capability =
new Tool subclass + one register() call. Nothing else changes.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from tandem.domain.tool import ToolResult


class Tool(ABC):
    """Base class for every capability. Subclasses set the class attributes."""

    name: str
    description: str
    parameters: dict[str, Any]  # JSON Schema (an "object" schema)
    requires_approval: bool = False

    @abstractmethod
    def run(self, **kwargs: Any) -> ToolResult:
        """Execute the tool with model-supplied arguments."""
        raise NotImplementedError

    def spec(self) -> dict[str, Any]:
        """The tool definition in the OpenAI function-calling format."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


class ToolRegistry:
    """An ordered, name-indexed collection of tools."""

    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        if tool.name in self._tools:
            raise ValueError(f"Duplicate tool name: {tool.name!r}")
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def specs(self) -> list[dict[str, Any]]:
        """All tool definitions, to send to the model each turn."""
        return [tool.spec() for tool in self._tools.values()]

    def __len__(self) -> int:
        return len(self._tools)
