"""
The agent: the ReAct loop.

Supports two tool-calling modes so it works with ANY served model:

  - "native": the model/endpoint supports OpenAI tool_calls natively (Nebius
    Nemotron Super, OpenAI, etc.). We pass `tools=` and read `tool_calls`.
  - "prompt": the harness owns tool calling. We describe the tools in the system
    prompt and ask the model to emit `<toolcall>{"name":..,"arguments":..}</toolcall>`,
    which we parse ourselves. This works even when the serving engine has no
    matching tool parser (e.g. self-hosted Nemotron-Mini on vLLM).

Both modes share the same loop shape: screen input → recall memory → ask →
run tools (guardrail + approval) → feed results back → repeat, capped by max_steps.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from tandem.agent.approval import ApprovalPolicy
from tandem.domain import message as msg
from tandem.domain.message import ToolCall, WireMessage
from tandem.domain.tool import Source
from tandem.guardrails.base import Guardrails
from tandem.llm.base import LLMBackend
from tandem.memory.base import MemoryStore
from tandem.skills.base import SkillStore
from tandem.tools.base import ToolRegistry


_log = logging.getLogger("tandem.agent")

# Tool routing wants steady, near-deterministic output. High temperature makes the
# 8B drift off its native tool-call format into ad-hoc text, so keep it low.
_TOOL_TEMPERATURE = 0.3

# Keep the prompt bounded: once a session exceeds _HISTORY_TRIM_AT user turns, drop
# older turns down to _HISTORY_KEEP (preserving the system message + role
# alternation). Trimming in chunks (not every turn) limits prefix-cache churn.
_HISTORY_TRIM_AT = 16
_HISTORY_KEEP = 12


@dataclass
class AgentResponse:
    text: str
    sources: list[Source] = field(default_factory=list)
    steps: int = 0


class Agent:
    """A persistent, tool-using, memory-backed assistant for one session."""

    def __init__(
        self,
        *,
        llm: LLMBackend,
        tools: ToolRegistry,
        memory: MemoryStore,
        skills: SkillStore,
        approval: ApprovalPolicy,
        persona: str,
        guardrails: Guardrails | None = None,
        tool_mode: str = "native",
        reasoning: str = "off",
        max_steps: int = 6,
    ) -> None:
        self._llm = llm
        self._tools = tools
        self._memory = memory
        self._skills = skills
        self._approval = approval
        self._guardrails = guardrails or Guardrails()
        self._tool_mode = tool_mode
        self._reasoning = reasoning
        self._max_steps = max_steps
        self._history: list[WireMessage] = [msg.system(self._build_system_prompt(persona))]
        # Closable resources (MCP servers, DB connections) released on close().
        self._resources: list[Any] = []

    def add_resource(self, resource: Any) -> None:
        """Register a resource with a .close() to release when the agent is evicted."""
        self._resources.append(resource)

    def close(self) -> None:
        for resource in self._resources:
            closer = getattr(resource, "close", None)
            if callable(closer):
                try:
                    closer()
                except Exception:
                    pass
        self._resources.clear()

    def send(self, user_text: str, *, images: list[str] | None = None) -> AgentResponse:
        verdict = self._guardrails.run_input(user_text)
        if not verdict.allowed:
            return AgentResponse(text=f"I can't help with that: {verdict.reason}", steps=0)
        if verdict.text is not None:
            user_text = verdict.text

        # Fold recalled memory INTO the user turn (not a separate mid-prompt system
        # message) so everything before it stays byte-identical turn-to-turn and
        # vLLM's prefix cache is reused. History is strictly append-only.
        # The model's training is frozen in the past, so it has no idea what day it
        # is and will invent dates (e.g. schedule "today" in 2023). Tell it the real
        # current date/time every turn so it resolves "today/tomorrow/this afternoon"
        # correctly. Folded into the user turn to keep the system-prompt prefix stable.
        now = datetime.now().astimezone()
        preamble = [
            "Current date and time: "
            + now.strftime("%A, %Y-%m-%d, %I:%M %p %Z").replace(" 0", " ")
            + ". Resolve any relative dates/times from this."
        ]
        memories = self._memory.search(user_text)
        if memories:
            block = "\n".join(f"- ({m.kind}) {m.content}" for m in memories)
            preamble.append(f"[Relevant memory]\n{block}")
        user_text = "\n\n".join(preamble + [user_text])

        self._trim_history()  # bound the prompt before adding this turn

        # Checkpoint so a failed turn leaves the history exactly as it was — a
        # dangling user/assistant/tool message would break role alternation on
        # the next turn too.
        checkpoint = len(self._history)
        if images:
            self._history.append(msg.user_with_images(user_text, images))
        else:
            self._history.append(msg.user(user_text))
        try:
            if self._tool_mode == "prompt":
                return self._loop_prompt()
            return self._loop_native()
        except Exception:
            del self._history[checkpoint:]
            raise

    # -- native tool-calling loop --------------------------------------------
    def _loop_native(self) -> AgentResponse:
        sources: list[Source] = []
        last_text = ""
        for step in range(1, self._max_steps + 1):
            result = self._llm.chat(
                self._history, tools=self._tools.specs() or None, temperature=_TOOL_TEMPERATURE
            )
            last_text = result.text
            if not result.tool_calls:
                # The 8B sometimes abandons native function-calling on complex turns
                # and emits tool calls as TEXT (`<TOOLCALL>[name, k="v"]`), which the
                # server parser misses. Salvage those so the action still runs; feed
                # results back as a user turn (no tool role after a plain assistant).
                salvaged = _salvage_tool_calls(result.text)
                if salvaged:
                    _log.info("salvaged %d text tool-call(s) from drifted output", len(salvaged))
                    self._history.append(msg.assistant_text(result.text))
                    for call in salvaged:
                        content, call_sources = self._run_tool_call(call)
                        sources.extend(call_sources)
                        self._history.append(msg.user(f"[tool result: {call.name}]\n{content}"))
                    continue
                self._history.append(result.assistant_message)
                return self._finalize(result.text, sources, step)
            # Serialize tool calls into one (assistant -> tool) pair each. The
            # model may request several at once, but strict chat templates reject
            # an assistant turn carrying multiple tool_calls, so we never append
            # one assistant message with several calls + consecutive tool results.
            for call in result.tool_calls:
                self._history.append(msg.assistant_tool_call(call))
                content, call_sources = self._run_tool_call(call)
                sources.extend(call_sources)
                self._history.append(msg.tool_result(call.id, content))
        return self._finalize(last_text or "(stopped: step limit)", sources, self._max_steps)

    # -- prompt-based tool-calling loop (harness-owned) -----------------------
    def _loop_prompt(self) -> AgentResponse:
        sources: list[Source] = []
        last_text = ""
        for step in range(1, self._max_steps + 1):
            result = self._llm.chat(self._history, temperature=_TOOL_TEMPERATURE)  # no native tools
            last_text = result.text
            self._history.append(msg.assistant_text(result.text))
            calls = _parse_toolcalls(result.text)
            if not calls:
                return self._finalize(result.text, sources, step)
            for call in calls:
                content, call_sources = self._run_tool_call(call)
                sources.extend(call_sources)
                # Feed the result back as a user turn (no native tool role here).
                self._history.append(msg.user(f"[tool result: {call.name}]\n{content}"))
        return self._finalize(last_text or "(stopped: step limit)", sources, self._max_steps)

    # -- shared internals ----------------------------------------------------
    def _finalize(self, text: str, sources: list[Source], steps: int) -> AgentResponse:
        # Nemotron reasoning models emit <think>..</think> traces; never show them.
        text = _strip_think(text)
        verdict = self._guardrails.run_output(text)
        final = _strip_toolcalls(verdict.text if verdict.text is not None else text)
        if not final:
            # The whole message was stripped (e.g. the model emitted only a stray
            # tool-call tag). Don't show a blank bubble.
            final = "Done." if steps > 1 else "I couldn't quite handle that — mind rephrasing?"
        return AgentResponse(text=final, sources=sources, steps=steps)

    def _run_tool_call(self, call: ToolCall) -> tuple[str, list[Source]]:
        tool = self._tools.get(call.name)
        if tool is None:
            return f"Error: unknown tool {call.name!r}.", []
        verdict = self._guardrails.run_tool(call, tool)
        if not verdict.allowed:
            return f"Blocked by policy: {verdict.reason}", []
        if tool.requires_approval and not self._approval.approve(call, tool):
            return "The user declined to approve this action.", []
        _log.info("tool call %s(%s)", call.name, call.arguments)
        try:
            result = tool.run(**call.arguments)
        except Exception as exc:
            _log.exception("tool %s raised", call.name)
            return f"Tool {call.name!r} failed: {exc}", []
        _log.info("tool %s -> %s", call.name, (result.content or "")[:400])
        return result.content, result.sources

    def _trim_history(self) -> None:
        """Bound the conversation so prompts (and prefill cost) don't grow forever.

        Keeps the system message + the last _HISTORY_KEEP user turns. Cutting at the
        start of a user message preserves strict role alternation (the remaining
        history after the system prompt always begins with a user turn).
        """
        user_idxs = [i for i, m in enumerate(self._history) if m.get("role") == "user"]
        if len(user_idxs) <= _HISTORY_TRIM_AT:
            return
        cut_end = user_idxs[-_HISTORY_KEEP]
        del self._history[1:cut_end]

    def _build_system_prompt(self, persona: str) -> str:
        parts: list[str] = []
        # Nemotron "detailed thinking" toggle. MUST be the first system line.
        # "off" keeps the command bar snappy and tool calls clean; "none" omits it
        # entirely for non-Nemotron models.
        if self._reasoning in ("off", "on"):
            parts.append(f"detailed thinking {self._reasoning}")
        parts += [persona, _OPERATING_RULES]
        skills = self._skills.all()
        if skills:
            menu = "\n".join(f"- {s.name}: {s.description}" for s in skills)
            parts.append(f"Learned skills you can follow:\n{menu}")
        if self._tool_mode == "prompt":
            tool_help = _tools_prompt(self._tools)
            if tool_help:
                parts.append(tool_help)
        return "\n\n".join(parts)


_OPERATING_RULES = (
    "Operating rules:\n"
    "- Before answering, recall relevant memory; after learning something durable, remember it.\n"
    "- Ground factual claims in sources and cite them.\n"
    "- Prefer using a tool over guessing. Say so when evidence is insufficient.\n"
    "- When you work out a repeatable procedure, save it as a skill."
)

_TOOLCALL_RE = re.compile(r"<tool_?call>\s*(\{.*?\})\s*</tool_?call>", re.DOTALL | re.IGNORECASE)
_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)
_DANGLING_THINK_RE = re.compile(r"<think>.*$", re.DOTALL | re.IGNORECASE)


def _strip_think(text: str) -> str:
    """Drop Nemotron reasoning traces: closed <think>..</think> blocks and any
    dangling <think> with no close (truncated reasoning) before showing the user."""
    text = _THINK_RE.sub("", text or "")
    return _DANGLING_THINK_RE.sub("", text)


def _tools_prompt(tools: ToolRegistry) -> str:
    """Describe the tools + the exact call format for prompt-based tool calling."""
    specs = tools.specs()
    if not specs:
        return ""
    lines = [
        "You can call tools. To call one, output EXACTLY this and nothing else:",
        '<toolcall>{"name": "<tool_name>", "arguments": {<args>}}</toolcall>',
        "Call one tool at a time. You MUST include the tool \"name\". After you see the "
        "result, continue; when finished, reply normally with no <toolcall>.",
        "",
        "Available tools:",
    ]
    for spec in specs:
        fn = spec["function"]
        props = (fn.get("parameters") or {}).get("properties") or {}
        args = ", ".join(props.keys())
        lines.append(f"- {fn['name']}({args}): {fn['description']}")
    return "\n".join(lines)


def _parse_toolcalls(text: str) -> list[ToolCall]:
    """Extract <toolcall>{...}</toolcall> blocks from model text into ToolCalls."""
    calls: list[ToolCall] = []
    for i, match in enumerate(_TOOLCALL_RE.finditer(text or "")):
        try:
            obj = json.loads(match.group(1))
        except json.JSONDecodeError:
            continue
        name = obj.get("name")
        if not name:
            continue  # unnamed call — can't dispatch safely
        calls.append(ToolCall(id=f"call_{i}", name=name, arguments=obj.get("arguments") or {}))
    return calls


_STRIP_TOOLCALL_RE = re.compile(
    r"<\s*tool_?call\s*>.*?(?:<\s*/\s*tool_?call\s*>|$)", re.DOTALL | re.IGNORECASE
)


_TEXT_CALL_TAG_RE = re.compile(r"<\s*tool_?call\s*>(.*?)(?:<\s*/\s*tool_?call\s*>|$)", re.DOTALL | re.IGNORECASE)
_BRACKET_CALL_RE = re.compile(r"\[\s*([a-zA-Z_]\w*)\s*(.*?)\]", re.DOTALL)
_KWARG_RE = re.compile(r'(\w+)\s*=\s*"([^"]*)"')


def _salvage_tool_calls(text: str) -> list[ToolCall]:
    """Recover tool calls the model emitted as TEXT instead of native calls.

    Handles both our JSON form `<toolcall>{"name":..,"arguments":..}</toolcall>`
    and the ad-hoc bracket form the 8B drifts into: `<TOOLCALL>[name, k="v", ...]`.
    """
    if not text:
        return []
    json_calls = _parse_toolcalls(text)  # strict <toolcall>{json}</toolcall> form
    if json_calls:
        return json_calls
    out: list[ToolCall] = []
    for tag in _TEXT_CALL_TAG_RE.finditer(text):
        bracket = _BRACKET_CALL_RE.search(tag.group(1))
        if not bracket:
            continue
        name = bracket.group(1)
        args = dict(_KWARG_RE.findall(bracket.group(2)))
        out.append(ToolCall(id=f"salvaged_{len(out)}", name=name, arguments=args))
    return out


def _strip_toolcalls(text: str) -> str:
    """Remove tool-call tags from a user-facing answer — JSON or ad-hoc inner form,
    closed or dangling, any case. In native tool mode the model occasionally emits
    a call as text (e.g. `<TOOLCALL>[recall, ...]`) instead of a native call; never
    show that raw syntax to the user."""
    return _STRIP_TOOLCALL_RE.sub("", text or "").strip()
