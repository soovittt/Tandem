"""
The integration interface.

An Integration is a connection to an external system (a lab notebook, a ticketing
system, a drive, an MCP server). Its one job is to expose that system as a set of
Tools the agent can call. The composition root asks each configured integration
for its tools and registers them -- so adding a new system never touches the agent.
"""

from __future__ import annotations

from typing import Protocol

from tandem.tools.base import Tool


class Integration(Protocol):
    """A source of tools backed by some external system."""

    name: str

    def tools(self) -> list[Tool]:
        """Return the tools this integration contributes to the agent."""
        ...
