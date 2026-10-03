"""
File-backed skill store: one JSON file per skill in a directory.

Files-on-disk keeps skills inspectable, portable, and diff-able -- you can read,
edit, or share a skill by hand. (Hermes/agentskills.io use markdown for the same
reason; JSON keeps our first version simple and robust.)
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from tandem.domain.skill import Skill


class FileSkillStore:
    """Implements SkillStore as a folder of <name>.json files."""

    def __init__(self, skills_dir: Path) -> None:
        self._dir = skills_dir
        self._dir.mkdir(parents=True, exist_ok=True)

    def add(self, skill: Skill) -> None:
        path = self._dir / f"{_slug(skill.name)}.json"
        path.write_text(
            json.dumps(
                {
                    "name": skill.name,
                    "description": skill.description,
                    "instructions": skill.instructions,
                },
                indent=2,
            )
        )

    def get(self, name: str) -> Skill | None:
        path = self._dir / f"{_slug(name)}.json"
        if not path.exists():
            return None
        return _load(path)

    def all(self) -> list[Skill]:
        return [_load(p) for p in sorted(self._dir.glob("*.json"))]


def _slug(name: str) -> str:
    """Filesystem-safe filename from a skill name."""
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "skill"


def _load(path: Path) -> Skill:
    data = json.loads(path.read_text())
    return Skill(
        name=data["name"],
        description=data["description"],
        instructions=data["instructions"],
    )
