"""
Declarative registry of MCP servers the Mac agent can load.

This is the "connect to any amount of apps" layer: each MCP server contributes
its tools to the agent (universal accessibility control, Apple apps, files, and
later Slack/GitHub/Notion/etc.). Enable them by name via the TANDEM_MCP_SERVERS
env var (comma-separated), e.g. TANDEM_MCP_SERVERS=open-computer-use,apple-mcp.

Adding a server = one entry here. Nothing else in the app changes — MCPIntegration
wraps each server's tools into our Tool interface. Servers that aren't installed
(or the optional `mcp` package) are skipped with a warning, never crash the agent.
"""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from tandem.integrations.mcp import MCPIntegration
from tandem.tools.base import Tool

_REPO_ROOT = Path(__file__).resolve().parents[2]
_UV = shutil.which("uv") or "uv"


def _whatsapp_command() -> list[str]:
    """Launch the whatsapp-mcp Python server (cloned under vendor/) over stdio.

    Invoke its own venv Python directly — NOT `uv run`, which hangs when nested
    inside our already-uv-managed backend process. Run `uv sync` in that dir once
    (see docs/whatsapp-setup.md) so the venv exists; we fall back to `uv run` only
    if it doesn't.
    """
    base = Path(os.getenv("WHATSAPP_MCP_DIR") or (_REPO_ROOT / "vendor/whatsapp-mcp/whatsapp-mcp-server"))
    venv_python = base / ".venv/bin/python"
    if venv_python.exists():
        return [str(venv_python), str(base / "main.py")]
    return [_UV, "--directory", str(base), "run", "main.py"]


@dataclass(frozen=True)
class McpServerConfig:
    name: str
    command: list[str]
    note: str = ""
    # Tool names that can perform consequential writes → require user approval.
    approval_tools: tuple[str, ...] = ()


# The catalog. These are launched over stdio; install each per its own README.
MCP_SERVERS: list[McpServerConfig] = [
    McpServerConfig(
        name="open-computer-use",
        command=["npx", "-y", "@qwen-code/open-computer-use", "mcp"],
        note="Universal Mac control via Accessibility + OCR (any app). Needs Accessibility + Screen Recording grants.",
    ),
    McpServerConfig(
        name="apple-mcp",
        command=["/opt/homebrew/bin/bunx", "apple-mcp@latest"],
        note="Apple apps: Messages, Notes, Mail, Reminders, Calendar, Contacts, Maps.",
        # These tools can send/create/modify → gate behind approval.
        approval_tools=("messages", "mail", "notes", "reminders", "calendar"),
    ),
    McpServerConfig(
        # Universal computer-use via Cua Driver (trycua/cua, MIT) — the OSS framework's
        # own background driver. Drives ANY native macOS app through the accessibility
        # tree (get_window_state → structured elements + Markdown), clicks/types/menus,
        # without stealing focus. Prebuilt binary (brew cask cuadriver → /Applications/
        # CuaDriver.app + /opt/homebrew/bin/cua-driver). Requires a one-time Accessibility
        # + Screen Recording grant: `cua-driver permissions grant`.
        name="macos",
        command=["/opt/homebrew/bin/cua-driver", "mcp"],
        note="Universal background computer-use (Cua Driver): control any native macOS app "
        "via the accessibility tree — get_window_state to read a window's elements, then "
        "click / invoke_menu / type / hotkey. The fallback for apps with no dedicated tool.",
    ),
    McpServerConfig(
        name="filesystem",
        command=["npx", "-y", "@modelcontextprotocol/server-filesystem", str(Path.home())],
        note="Read/write files under the home directory.",
    ),
    McpServerConfig(
        name="playwright",
        command=["npx", "-y", "@playwright/mcp@latest"],
        note="Full browser automation (navigate, click, fill forms, scrape any site) via "
        "Microsoft's open-source Playwright MCP. Heavier than the native browser tools; "
        "enable when you need real web ACTIONS, not just reading the current tab.",
    ),
    McpServerConfig(
        name="whatsapp",
        command=_whatsapp_command(),
        note="WhatsApp (your personal account via a local whatsmeow bridge): read/send "
        "messages incl. GROUPS, search contacts/chats. Needs the Go bridge running + a "
        "one-time QR link — see docs/whatsapp-setup.md. Data stays local (on-device).",
        # Sends are consequential → gate behind approval; reads (search/list/get) are open.
        approval_tools=("send_message", "send_file", "send_audio_message"),
    ),
]

_BY_NAME = {s.name: s for s in MCP_SERVERS}


def enabled_server_names() -> list[str]:
    raw = os.getenv("TANDEM_MCP_SERVERS", "").strip()
    return [n.strip() for n in raw.split(",") if n.strip()]


def load_mcp_tools(names: list[str] | None = None) -> tuple[list[Tool], list[MCPIntegration]]:
    """Connect to the enabled MCP servers; return (all tools, the integrations).

    The integrations are returned so the caller can close() them (releasing the
    server subprocesses) when the owning agent is evicted.
    """
    wanted = names if names is not None else enabled_server_names()
    tools: list[Tool] = []
    integrations: list[MCPIntegration] = []
    for name in wanted:
        config = _BY_NAME.get(name)
        if config is None:
            print(f"[mcp] unknown server '{name}' — skipping")
            continue
        try:
            integration = MCPIntegration.from_stdio(config.command)
            server_tools = integration.tools()
            for tool in server_tools:
                if tool.name in config.approval_tools:
                    tool.requires_approval = True  # consequential → needs user approval
            tools.extend(server_tools)
            integrations.append(integration)
            print(f"[mcp] loaded {len(server_tools)} tools from '{name}'")
        except Exception as exc:  # never let a missing server break the agent
            print(f"[mcp] could not load '{name}': {exc}")
    return tools, integrations
