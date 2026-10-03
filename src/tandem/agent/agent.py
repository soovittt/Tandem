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

import logging
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from tandem.agent.approval import ApprovalPolicy
from tandem.agent.toolcall_codec import ToolCallCodec
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
        self._codec = ToolCallCodec()  # parses/salvages/cleans the tool-call wire format
        self._base_system = self._build_system_prompt(persona)
        self._history: list[WireMessage] = [msg.system(self._base_system)]
        # Closable resources (MCP servers, DB connections) released on close().
        self._resources: list[Any] = []

    def seed_history(self, turns: list[dict[str, str]]) -> None:
        """Restore prior conversation turns (plain user/assistant text) after the
        system prompt, so the model keeps context across restarts. Call once, right
        after building, before the first send."""
        for turn in turns:
            text = turn.get("text", "")
            if turn.get("role") == "user":
                self._history.append(msg.user(text))
            elif turn.get("role") == "assistant" and text:
                self._history.append(msg.assistant_text(text))

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
        ok, user_text = self._screen_input(user_text)
        if not ok:
            return AgentResponse(text=user_text, steps=0)  # user_text holds the refusal
        checkpoint = self._open_turn(user_text, images)
        try:
            return self._loop_prompt() if self._tool_mode == "prompt" else self._loop_native()
        except Exception:
            del self._history[checkpoint:]
            raise

    def stream(self, user_text: str, *, images: list[str] | None = None) -> Iterator[dict[str, Any]]:
        """Run the turn, yielding events as it goes: {"type":"token","text":..} for
        the answer streaming live, {"type":"tool","name":..} per tool run, and a
        final {"type":"done","text":..,"steps":..,"sources":[..]} with the
        authoritative cleaned answer. Prompt mode has no token stream (just done)."""
        if self._tool_mode == "prompt":
            resp = self.send(user_text, images=images)
            yield self._done_event(resp.text, resp.steps, resp.sources)
            return
        ok, user_text = self._screen_input(user_text)
        if not ok:
            yield self._done_event(user_text, 0, [])
            return
        checkpoint = self._open_turn(user_text, images)
        try:
            yield from self._loop_stream()
        except Exception:
            del self._history[checkpoint:]
            _log.exception("stream turn failed")
            yield self._done_event("Sorry — I hit an error handling that one.", 0, [])

    # -- per-turn setup (shared by send + stream) ----------------------------
    def _screen_input(self, user_text: str) -> tuple[bool, str]:
        """Input guardrails + fold current date/time and recalled memory into the
        user turn. Returns (ok, text); on a blocked input ok=False and text is the
        refusal message."""
        verdict = self._guardrails.run_input(user_text)
        if not verdict.allowed:
            return False, f"I can't help with that: {verdict.reason}"
        if verdict.text is not None:
            user_text = verdict.text
        return True, self._fold_context(user_text)

    def _fold_context(self, user_text: str) -> str:
        """Prefix the user turn with any recalled memory (used silently). The current
        date/time lives in the system prompt instead (see _refresh_system_date) so the
        model treats it as background and doesn't parrot it back."""
        memories = self._memory.search(user_text)
        if not memories:
            return user_text
        block = "\n".join(f"- ({m.kind}) {m.content}" for m in memories)
        return f"[Relevant memory — use silently, don't restate]\n{block}\n\n{user_text}"

    def _refresh_system_date(self) -> None:
        """Keep the real current date/time in the SYSTEM prompt (the model's training
        is frozen in the past, so it invents dates otherwise). Appended AFTER the base
        prompt so the Nemotron 'detailed thinking' directive stays the first line."""
        now = datetime.now().astimezone()
        when = now.strftime("%A, %Y-%m-%d, %I:%M %p %Z").replace(" 0", " ")
        self._history[0] = msg.system(
            f"{self._base_system}\n\nThe current date and time is {when}. Use it directly "
            "whenever the user asks about the date/time or you need it for scheduling."
        )

    def _open_turn(self, user_text: str, images: list[str] | None) -> int:
        """Refresh the date, trim, then append the user turn. Returns a checkpoint to
        roll back to if the turn fails — a dangling user/assistant/tool message would
        break role alternation on the next turn too."""
        self._refresh_system_date()
        self._trim_history()
        checkpoint = len(self._history)
        self._history.append(
            msg.user_with_images(user_text, images) if images else msg.user(user_text)
        )
        return checkpoint

    def _done_event(self, text: str, steps: int, sources: list[Source]) -> dict[str, Any]:
        return {
            "type": "done",
            "text": text,
            "steps": steps,
            "sources": [{"title": s.title, "url": s.url} for s in sources],
        }

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
                salvaged = self._codec.decode(result.text)
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
            calls = self._codec.decode(result.text)
            if not calls:
                return self._finalize(result.text, sources, step)
            for call in calls:
                content, call_sources = self._run_tool_call(call)
                sources.extend(call_sources)
                # Feed the result back as a user turn (no native tool role here).
                self._history.append(msg.user(f"[tool result: {call.name}]\n{content}"))
        return self._finalize(last_text or "(stopped: step limit)", sources, self._max_steps)

    # -- streaming native loop (yields events) -------------------------------
    def _loop_stream(self) -> Iterator[dict[str, Any]]:
        sources: list[Source] = []
        last_text = ""
        for step in range(1, self._max_steps + 1):
            gate = StreamGate()  # hides <think>/<toolcall> drift from the live stream
            completion = self._llm.chat_stream(
                self._history, tools=self._tools.specs() or None, temperature=_TOOL_TEMPERATURE
            )
            for delta in completion:
                shown = gate.feed(delta)
                if shown:
                    yield {"type": "token", "text": shown}
            tail = gate.flush()
            if tail:
                yield {"type": "token", "text": tail}

            result = completion.result
            last_text = result.text
            if not result.tool_calls:
                salvaged = self._codec.decode(result.text)
                if salvaged:  # model emitted a tool call as text; the gate hid it
                    _log.info("salvaged %d text tool-call(s) from drifted output", len(salvaged))
                    self._history.append(msg.assistant_text(result.text))
                    for call in salvaged:
                        yield {"type": "tool", "name": call.name}
                        content, srcs = self._run_tool_call(call)
                        sources.extend(srcs)
                        self._history.append(msg.user(f"[tool result: {call.name}]\n{content}"))
                    continue
                self._history.append(result.assistant_message)
                resp = self._finalize(result.text, sources, step)
                yield self._done_event(resp.text, resp.steps, resp.sources)
                return
            for call in result.tool_calls:
                self._history.append(msg.assistant_tool_call(call))
                yield {"type": "tool", "name": call.name}
                content, srcs = self._run_tool_call(call)
                sources.extend(srcs)
                self._history.append(msg.tool_result(call.id, content))
        resp = self._finalize(last_text or "(stopped: step limit)", sources, self._max_steps)
        yield self._done_event(resp.text, resp.steps, resp.sources)

    # -- shared internals ----------------------------------------------------
    def _finalize(self, text: str, sources: list[Source], steps: int) -> AgentResponse:
        # Strip reasoning traces + any stray tool-call tags before the user sees it.
        cleaned = self._codec.clean(text)
        verdict = self._guardrails.run_output(cleaned)
        final = verdict.text if verdict.text is not None else cleaned
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
            tool_help = self._codec.tools_prompt(self._tools.specs())
            if tool_help:
                parts.append(tool_help)
        return "\n\n".join(parts)


_OPERATING_RULES = (
    "Operating rules:\n"
    "- You are a full general assistant: answer general questions directly from your own "
    "knowledge. You do NOT need a tool for everything, and never refuse a question just "
    "because it isn't about the Mac.\n"
    "- Use a tool only to take an action on the Mac or to fetch the user's own data "
    "(messages, files, calendar, contacts…). Relevant memory is already provided to you.\n"
    "- Remember durable facts the user shares about themselves.\n"
    "- When you work out a repeatable procedure, save it as a skill."
)


class StreamGate:
    """Holds back the opening characters of streamed content so a drifted tool-call
    (`<TOOLCALL>[...]`) or a <think> block never flashes before it's recognized.
    Once the content is clearly plain text it flushes and passes tokens straight
    through. (The final answer in the `done` event is authoritative regardless.)"""

    _MARKERS = ("<think", "<tool")

    def __init__(self) -> None:
        self._buffer = ""
        self._passthrough = False
        self._suppressed = False

    def feed(self, delta: str) -> str:
        """Return the portion of `delta` that's safe to show now (may be empty)."""
        if self._suppressed:
            return ""
        if self._passthrough:
            return delta
        self._buffer += delta
        stripped = self._buffer.lstrip().lower()
        if not stripped:
            return ""  # only whitespace so far — keep buffering
        if stripped.startswith(self._MARKERS):
            self._suppressed = True  # it's a reasoning/tool-call tag; hide the whole step
            self._buffer = ""
            return ""
        if stripped[0] == "<" and any(m.startswith(stripped) for m in self._MARKERS):
            return ""  # could still become a marker (e.g. "<", "<t", "<thi") — wait
        return self._open()

    def flush(self) -> str:
        """Emit whatever's safely buffered once the stream ends."""
        return "" if self._suppressed else self._open()

    def _open(self) -> str:
        self._passthrough = True
        out, self._buffer = self._buffer, ""
        return out
