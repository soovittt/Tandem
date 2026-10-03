"""Tool that lets the model save a reusable skill it has figured out."""

from __future__ import annotations

from typing import Any

from tandem.domain.skill import Skill
from tandem.domain.tool import ToolResult
from tandem.skills.base import SkillStore
from tandem.tools.base import Tool


class SaveSkillTool(Tool):
    """Turn a procedure the agent just worked out into reusable procedural memory."""

    name = "save_skill"
    description = (
        "Save a reusable, step-by-step procedure as a named skill so it can be "
        "followed again in future sessions. Use after working out how to do "
        "something worth repeating."
    )
    parameters = {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Short skill name."},
            "description": {
                "type": "string",
                "description": "One line: when to use this skill.",
            },
            "instructions": {
                "type": "string",
                "description": "The step-by-step procedure.",
            },
        },
        "required": ["name", "description", "instructions"],
    }

    def __init__(self, store: SkillStore) -> None:
        self._store = store

    def run(self, **kwargs: Any) -> ToolResult:
        skill = Skill(
            name=kwargs["name"],
            description=kwargs["description"],
            instructions=kwargs["instructions"],
        )
        self._store.add(skill)
        return ToolResult(content=f"Saved skill: {skill.name}")
