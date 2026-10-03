"""
End-to-end test of the agent loop with a fake LLM backend.

Because the app depends on the LLMBackend *protocol* (not a concrete provider),
we can drop in a scripted fake and exercise the entire loop -- tool dispatch,
real SQLite memory, result feedback, final answer -- with no network or API key.
That testability is the payoff of the dependency-inversion design.

Run directly:  uv run python tests/test_agent_loop.py
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from tandem.agent.agent import Agent
from tandem.agent.approval import AutoApprove
from tandem.domain.message import ToolCall
from tandem.llm.base import ChatResult
from tandem.memory.sqlite_store import SQLiteMemoryStore
from tandem.skills.file_store import FileSkillStore
from tandem.tools.base import ToolRegistry
from tandem.tools.memory_tools import RecallTool, RememberTool


class FakeLLM:
    """A scripted LLMBackend: returns pre-baked ChatResults in order."""

    def __init__(self, script: list[ChatResult]) -> None:
        self._script = script
        self._i = 0

    def chat(self, messages, *, tools=None, temperature=0.7, max_tokens=1024):  # noqa: ANN001
        result = self._script[self._i]
        self._i += 1
        return result


def _assistant_tool_call(call_id: str, name: str, arguments_json: str) -> dict:
    return {
        "role": "assistant",
        "content": "",
        "tool_calls": [
            {"id": call_id, "type": "function", "function": {"name": name, "arguments": arguments_json}}
        ],
    }


def _build(tmp: Path, llm: FakeLLM) -> tuple[Agent, SQLiteMemoryStore]:
    memory = SQLiteMemoryStore(tmp / "memory.db")
    skills = FileSkillStore(tmp / "skills")
    tools = ToolRegistry()
    tools.register(RememberTool(memory))
    tools.register(RecallTool(memory))
    agent = Agent(
        llm=llm,
        tools=tools,
        memory=memory,
        skills=skills,
        approval=AutoApprove(),
        persona="You are a test assistant.",
    )
    return agent, memory


def test_tool_call_persists_and_answers() -> None:
    """The model calls `remember`, we run it, feed the result back, it answers."""
    args = '{"content": "Sample A-7 delaminated at 80C", "kind": "observation"}'
    llm = FakeLLM(
        [
            # Turn 1: the model decides to store an observation.
            ChatResult(
                text="",
                tool_calls=[
                    ToolCall(id="c1", name="remember", arguments={
                        "content": "Sample A-7 delaminated at 80C", "kind": "observation"
                    })
                ],
                assistant_message=_assistant_tool_call("c1", "remember", args),
                prompt_tokens=10,
                completion_tokens=4,
            ),
            # Turn 2: with the tool result in context, it gives a final answer.
            ChatResult(
                text="Logged that Sample A-7 delaminated at 80C.",
                tool_calls=[],
                assistant_message={"role": "assistant", "content": "Logged that Sample A-7 delaminated at 80C."},
                prompt_tokens=20,
                completion_tokens=8,
            ),
        ]
    )

    with tempfile.TemporaryDirectory() as d:
        agent, memory = _build(Path(d), llm)
        response = agent.send("Sample A-7 delaminated when we ran it at 80C.")

        assert response.text == "Logged that Sample A-7 delaminated at 80C."
        assert response.steps == 2
        stored = memory.all()
        assert len(stored) == 1
        assert stored[0].content == "Sample A-7 delaminated at 80C"
        assert stored[0].kind == "observation"


def test_memory_recall_across_turns() -> None:
    """A memory saved earlier is retrievable by keyword search later."""
    with tempfile.TemporaryDirectory() as d:
        memory = SQLiteMemoryStore(Path(d) / "memory.db")
        from tandem.domain.memory import MemoryRecord

        memory.add(MemoryRecord(content="The coating oven runs 10C hot", kind="fact"))
        hits = memory.search("oven temperature")
        assert any("oven" in h.content for h in hits)


if __name__ == "__main__":
    test_tool_call_persists_and_answers()
    test_memory_recall_across_turns()
    print("OK — agent loop, tool dispatch, and SQLite memory all work end-to-end.")
