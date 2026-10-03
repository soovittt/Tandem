"""The skill store interface (repository pattern)."""

from __future__ import annotations

from typing import Protocol

from tandem.domain.skill import Skill


class SkillStore(Protocol):
    """Persists and retrieves learned skills."""

    def add(self, skill: Skill) -> None:
        """Save a new skill (or overwrite one with the same name)."""
        ...

    def get(self, name: str) -> Skill | None:
        """Fetch one skill by name, or None."""
        ...

    def all(self) -> list[Skill]:
        """Return every known skill (for injecting the menu into the prompt)."""
        ...
