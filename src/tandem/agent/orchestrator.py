"""
Orchestrator -> subagent pattern (a.k.a. orchestrator-worker).

For a big, multi-part task, one agent doing everything in a single context gets
muddled. The orchestrator instead:

    1. PLANS   -- asks the model to break the task into focused subtasks
    2. DELEGATES -- runs each subtask in its own fresh subagent (own context,
                    shared long-term memory + tools)
    3. SYNTHESIZES -- combines the subagents' answers into one result

Subagents are just Agents with a focused persona, created by a factory the
composition root supplies (so they share memory/tools without this file knowing
how they're wired).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Callable

from tandem.agent.agent import Agent
from tandem.domain import message as msg
from tandem.domain.tool import Source
from tandem.llm.base import LLMBackend

SubagentFactory = Callable[[str], Agent]


@dataclass
class SubTask:
    title: str
    instructions: str


@dataclass
class OrchestratorResult:
    text: str
    subtasks: list[SubTask] = field(default_factory=list)
    sources: list[Source] = field(default_factory=list)


class Orchestrator:
    """Plans a task into subtasks, runs each via a subagent, and synthesizes."""

    def __init__(
        self,
        *,
        llm: LLMBackend,
        subagent_factory: SubagentFactory,
        max_subtasks: int = 4,
    ) -> None:
        self._llm = llm
        self._make_subagent = subagent_factory
        self._max_subtasks = max_subtasks

    def run(self, task: str) -> OrchestratorResult:
        subtasks = self._plan(task)
        sources: list[Source] = []
        answers: list[tuple[SubTask, str]] = []

        for subtask in subtasks:
            subagent = self._make_subagent(
                f"You are a focused worker. Your sole job: {subtask.title}."
            )
            response = subagent.send(subtask.instructions)
            answers.append((subtask, response.text))
            sources.extend(response.sources)

        final_text = self._synthesize(task, answers)
        return OrchestratorResult(text=final_text, subtasks=subtasks, sources=sources)

    # -- internals ------------------------------------------------------------

    def _plan(self, task: str) -> list[SubTask]:
        prompt = (
            f"Break this task into at most {self._max_subtasks} focused subtasks. "
            "Reply with ONLY a JSON array of objects with keys 'title' and "
            f"'instructions'. Task:\n{task}"
        )
        result = self._llm.chat(
            [msg.system("You are a planner."), msg.user(prompt)],
            temperature=0.2,
        )
        parsed = _extract_json_array(result.text)
        subtasks = [
            SubTask(title=item.get("title", "subtask"), instructions=item.get("instructions", ""))
            for item in parsed
            if isinstance(item, dict)
        ][: self._max_subtasks]
        # If planning failed, treat the whole task as one subtask.
        return subtasks or [SubTask(title="complete the task", instructions=task)]

    def _synthesize(self, task: str, answers: list[tuple[SubTask, str]]) -> str:
        joined = "\n\n".join(f"## {st.title}\n{text}" for st, text in answers)
        prompt = (
            f"Original task:\n{task}\n\nSubtask results:\n{joined}\n\n"
            "Synthesize these into one clear, complete answer."
        )
        result = self._llm.chat(
            [msg.system("You are a synthesizer."), msg.user(prompt)],
            temperature=0.3,
        )
        return result.text


def _extract_json_array(text: str) -> list:
    """Pull a JSON array out of a model reply, tolerating code fences/prose."""
    start = text.find("[")
    end = text.rfind("]")
    if start == -1 or end == -1 or end < start:
        return []
    try:
        parsed = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return []
    return parsed if isinstance(parsed, list) else []
