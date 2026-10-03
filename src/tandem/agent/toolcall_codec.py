"""
The tool-call wire codec.

ONE place that knows how tool calls look as *text*, so the Agent's loops stay about
orchestration, not string surgery. It:
  - renders the available tools + call format into a system prompt (prompt mode),
  - parses the `<toolcall>{json}</toolcall>` blocks we instruct back into ToolCalls,
  - salvages the ad-hoc text formats the model drifts into under native tool calling
    (e.g. `<TOOLCALL>[name, k="v"]`), so an action still runs, and
  - cleans a user-facing answer of reasoning traces and stray tool-call tags.
"""

from __future__ import annotations

import json
import re
from typing import Any

from tandem.domain.message import ToolCall


class ToolCallCodec:
    """Encode/decode the model's tool-call text format(s)."""

    # Strict JSON form we instruct in prompt mode: <toolcall>{"name":..,"arguments":..}</toolcall>
    _JSON_CALL_RE = re.compile(r"<tool_?call>\s*(\{.*?\})\s*</tool_?call>", re.DOTALL | re.IGNORECASE)
    # Any tool-call tag (JSON or ad-hoc, closed or dangling) — for stripping from answers.
    _STRIP_CALL_RE = re.compile(r"<\s*tool_?call\s*>.*?(?:<\s*/\s*tool_?call\s*>|$)", re.DOTALL | re.IGNORECASE)
    # Tag + its inner text — for salvaging the bracket form.
    _CALL_TAG_RE = re.compile(r"<\s*tool_?call\s*>(.*?)(?:<\s*/\s*tool_?call\s*>|$)", re.DOTALL | re.IGNORECASE)
    _BRACKET_CALL_RE = re.compile(r"\[\s*([a-zA-Z_]\w*)\s*(.*?)\]", re.DOTALL)
    _KWARG_RE = re.compile(r'(\w+)\s*=\s*"([^"]*)"')
    # Reasoning traces from "detailed thinking on" models.
    _THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)
    _DANGLING_THINK_RE = re.compile(r"<think>.*$", re.DOTALL | re.IGNORECASE)

    def tools_prompt(self, specs: list[dict[str, Any]]) -> str:
        """Describe the tools + the exact call format for prompt-based tool calling."""
        if not specs:
            return ""
        lines = [
            "You can call tools. To call one, output EXACTLY this and nothing else:",
            '<toolcall>{"name": "<tool_name>", "arguments": {<args>}}</toolcall>',
            'Call one tool at a time. You MUST include the tool "name". After you see the '
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

    def parse(self, text: str) -> list[ToolCall]:
        """Extract the `<toolcall>{json}</toolcall>` blocks (the prompt-mode format)."""
        calls: list[ToolCall] = []
        for i, match in enumerate(self._JSON_CALL_RE.finditer(text or "")):
            try:
                obj = json.loads(match.group(1))
            except json.JSONDecodeError:
                continue
            name = obj.get("name")
            if not name:
                continue  # unnamed call — can't dispatch safely
            calls.append(ToolCall(id=f"call_{i}", name=name, arguments=obj.get("arguments") or {}))
        return calls

    def salvage(self, text: str) -> list[ToolCall]:
        """Recover tool calls the model emitted as TEXT instead of native calls —
        both the JSON form and the ad-hoc bracket form `<TOOLCALL>[name, k="v", ...]`."""
        if not text:
            return []
        json_calls = self.parse(text)
        if json_calls:
            return json_calls
        out: list[ToolCall] = []
        for tag in self._CALL_TAG_RE.finditer(text):
            bracket = self._BRACKET_CALL_RE.search(tag.group(1))
            if not bracket:
                continue
            args = dict(self._KWARG_RE.findall(bracket.group(2)))
            out.append(ToolCall(id=f"salvaged_{len(out)}", name=bracket.group(1), arguments=args))
        return out

    def clean(self, text: str) -> str:
        """Strip reasoning traces (<think>..) and any tool-call tags from a final,
        user-facing answer. The model occasionally leaks these into its content."""
        text = self._THINK_RE.sub("", text or "")
        text = self._DANGLING_THINK_RE.sub("", text)
        return self._STRIP_CALL_RE.sub("", text).strip()
