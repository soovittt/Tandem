"""
Message types and wire-format builders.

A "conversation" sent to an OpenAI-compatible model is a list of plain dicts.
Rather than scatter dict literals across the codebase, this module is the ONE
place that knows the wire shape. Everyone else calls these builders.
"""

from __future__ import annotations

import base64
import json
import mimetypes
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

Role = Literal["system", "user", "assistant", "tool"]

# A single message on the wire.
WireMessage = dict[str, Any]


@dataclass(frozen=True)
class ToolCall:
    """A model's request to invoke one tool, already parsed for dispatch."""

    id: str
    name: str
    arguments: dict[str, Any]


def system(content: str) -> WireMessage:
    return {"role": "system", "content": content}


def user(content: str) -> WireMessage:
    return {"role": "user", "content": content}


def assistant_text(content: str) -> WireMessage:
    """A plain assistant message (used in prompt-based tool mode)."""
    return {"role": "assistant", "content": content}


def assistant_tool_call(call: "ToolCall") -> WireMessage:
    """An assistant turn that invokes EXACTLY ONE tool.

    Strict chat templates (e.g. Llama-3.1) require conversation roles to alternate
    between user/tool and assistant, and reject an assistant turn that carries
    several tool_calls (which would be followed by consecutive tool messages). So
    we serialize parallel tool calls into one of these per call.
    """
    return {
        "role": "assistant",
        "content": "",
        "tool_calls": [
            {
                "id": call.id,
                "type": "function",
                "function": {"name": call.name, "arguments": json.dumps(call.arguments)},
            }
        ],
    }


def tool_result(tool_call_id: str, content: str) -> WireMessage:
    """The result of running a tool, fed back so the model can continue."""
    return {"role": "tool", "tool_call_id": tool_call_id, "content": content}


def user_with_images(text: str, images: list[str]) -> WireMessage:
    """
    A user message carrying one or more images (the multimodal path).

    `images` may be http(s) URLs, data: URLs, or local file paths (which we encode
    to data URLs). This is the OpenAI-compatible vision format that Nemotron's
    multimodal models accept -- content becomes a list of text/image parts.
    """
    content: list[dict[str, Any]] = [{"type": "text", "text": text}]
    for image in images:
        content.append({"type": "image_url", "image_url": {"url": _image_url(image)}})
    return {"role": "user", "content": content}


def _image_url(image: str) -> str:
    if image.startswith(("http://", "https://", "data:")):
        return image
    return image_data_url(Path(image))


def image_data_url(path: Path) -> str:
    """Encode a local image file as a base64 data URL for inline transport."""
    mime = mimetypes.guess_type(path.name)[0] or "image/jpeg"
    encoded = base64.b64encode(path.read_bytes()).decode()
    return f"data:{mime};base64,{encoded}"
