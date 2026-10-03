"""A skill: a reusable procedure the assistant has learned."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Skill:
    """
    Procedural memory. Where a MemoryRecord is a fact, a Skill is a *how-to* --
    a named, reusable set of steps the agent can follow again later.
    """

    name: str
    description: str   # one line, shown to the model so it knows when to use it
    instructions: str  # the actual step-by-step procedure
