"""
The tool-call wire codec.

ONE place that knows how tool calls look as *text*, so the Agent's loops stay about
orchestration, not string surgery. It:
  - renders the available tools + call format into a system prompt (prompt mode),
  - decodes the tool calls the model emits as text — across every format it uses:
    the `<toolcall>{json}</toolcall>` we instruct (prompt mode), the
    `<TOOLCALL>[{json}, ...]` JSON array it streams (vLLM doesn't run its tool
    parser while streaming), and the ad-hoc `<TOOLCALL>[name, k="v"]` bracket form
    it drifts into — so an action still runs, and
  - cleans a user-facing answer of reasoning traces and stray tool-call tags.
"""

from __future__ import annotations

import json
import re
from typing import Any

from tandem.domain.message import ToolCall


class ToolCallCodec:
    """Encode/decode the model's tool-call text format(s)."""

    # A tool-call tag + its inner text (closed or dangling), for decoding.
    _CALL_TAG_RE = re.compile(r"<\s*tool_?call\s*>(.*?)(?:<\s*/\s*tool_?call\s*>|$)", re.DOTALL | re.IGNORECASE)
    # The whole tag, for stripping from a user-facing answer.
    _STRIP_CALL_RE = re.compile(r"<\s*tool_?call\s*>.*?(?:<\s*/\s*tool_?call\s*>|$)", re.DOTALL | re.IGNORECASE)
    # Ad-hoc pythonic form inside the tag: [name, key="value", ...]
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

    def decode(self, text: str) -> list[ToolCall]:
        """Extract every tool call the model emitted as text, whatever the format."""
        out: list[ToolCall] = []
        for tag in self._CALL_TAG_RE.finditer(text or ""):
            out.extend(self._calls_from_tag(tag.group(1), len(out)))
        return out

    def _calls_from_tag(self, inner: str, start: int) -> list[ToolCall]:
        """Parse one <toolcall> tag's inner text into ToolCalls. `start` seeds ids."""
        inner = inner.strip()
        # JSON form — a single {name, arguments} object or a [list] of them.
        try:
            data: Any = json.loads(inner)
        except json.JSONDecodeError:
            data = None
        if isinstance(data, dict):
            data = [data]
        if isinstance(data, list):
            calls = [
                ToolCall(id=f"call_{start + i}", name=obj["name"], arguments=obj.get("arguments") or {})
                for i, obj in enumerate(data)
                if isinstance(obj, dict) and obj.get("name")
            ]
            if calls:
                return calls
        # Ad-hoc pythonic bracket form: [name, key="value", ...]
        bracket = self._BRACKET_CALL_RE.search(inner)
        if bracket:
            args = dict(self._KWARG_RE.findall(bracket.group(2)))
            return [ToolCall(id=f"call_{start}", name=bracket.group(1), arguments=args)]
        return []

    def clean(self, text: str) -> str:
        """Strip reasoning traces (<think>..) and any tool-call tags from a final,
        user-facing answer. The model occasionally leaks these into its content."""
        text = self._THINK_RE.sub("", text or "")
        text = self._DANGLING_THINK_RE.sub("", text)
        return self._STRIP_CALL_RE.sub("", text).strip()
