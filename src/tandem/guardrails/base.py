"""
Guardrail interfaces and the pipeline that runs them.

Rails run at three stages, mirroring NeMo Guardrails' model:
  - input  rails: screen/redact the user's message before it reaches the model
  - tool   rails: validate a tool call before it executes
  - output rails: screen/redact the model's answer before the user sees it

Each rail is a tiny object with a `check(...)` that returns a GuardrailVerdict.
The Guardrails aggregate runs a list at each stage; the first BLOCK wins, and
text redactions chain. NeMo Guardrails (or any other engine) can be dropped in
later simply by implementing these protocols -- nothing above changes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from tandem.domain.message import ToolCall
from tandem.tools.base import Tool


@dataclass
class GuardrailVerdict:
    """Outcome of one rail. `text` carries a redacted replacement when relevant."""

    allowed: bool = True
    reason: str = ""
    text: str | None = None


class InputGuardrail(Protocol):
    def check(self, text: str) -> GuardrailVerdict: ...


class ToolGuardrail(Protocol):
    def check(self, call: ToolCall, tool: Tool) -> GuardrailVerdict: ...


class OutputGuardrail(Protocol):
    def check(self, text: str) -> GuardrailVerdict: ...


@dataclass
class Guardrails:
    """Holds the rails for each stage and applies them in order."""

    input: list[InputGuardrail] = field(default_factory=list)
    tool: list[ToolGuardrail] = field(default_factory=list)
    output: list[OutputGuardrail] = field(default_factory=list)

    def run_input(self, text: str) -> GuardrailVerdict:
        return _run_text_rails(self.input, text)

    def run_output(self, text: str) -> GuardrailVerdict:
        return _run_text_rails(self.output, text)

    def run_tool(self, call: ToolCall, tool: Tool) -> GuardrailVerdict:
        for rail in self.tool:
            verdict = rail.check(call, tool)
            if not verdict.allowed:
                return verdict
        return GuardrailVerdict(allowed=True)


def _run_text_rails(rails: list, text: str) -> GuardrailVerdict:
    """Run text rails in order: block short-circuits; redactions accumulate."""
    current = text
    for rail in rails:
        verdict = rail.check(current)
        if not verdict.allowed:
            return verdict
        if verdict.text is not None:
            current = verdict.text
    return GuardrailVerdict(allowed=True, text=current)
