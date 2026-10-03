"""
Composition root.

The ONE place where concrete implementations are chosen and wired together. Every
other module depends only on interfaces; here we pick SQLite/Mem0 for memory,
files for skills, the OpenAI-compatible backend for the model, a subprocess
sandbox, the filesystem integration, and so on. To change an implementation, you
change it here and nowhere else.
"""

from __future__ import annotations

from collections.abc import Iterable

from tandem.agent.agent import Agent
from tandem.agent.approval import ApprovalPolicy, AutoApprove
from tandem.config import AppConfig
from tandem.guardrails.base import Guardrails
from tandem.integrations.base import Integration
from tandem.integrations.filesystem import FilesystemIntegration
from tandem.llm.openai_compatible import OpenAICompatibleLLM
from tandem.memory.base import MemoryStore
from tandem.memory.sqlite_store import SQLiteMemoryStore
from tandem.security.subprocess_sandbox import SubprocessSandbox
from tandem.skills.base import SkillStore
from tandem.skills.file_store import FileSkillStore
from tandem.tools.base import Tool, ToolRegistry
from tandem.tools.code_execution import RunCommandTool
from tandem.tools.memory_tools import RememberTool
from tandem.tools.skill_tools import SaveSkillTool
from tandem.tools.web_search import TavilyProvider, WebSearchTool
from tandem.mac.pack import mac_system_tools
from tandem.mcp_servers import load_mcp_tools
from tandem.whatsapp_bridge import WhatsAppSendTool

MAC_PERSONA = (
    "You are Tandem, a friendly, highly capable personal AI running on the user's Mac. "
    "You CAN control this Mac RIGHT NOW through your tools: open, switch, minimize and "
    "hide apps; and read or act in Calendar, Reminders, Notes, Messages, Mail, Contacts, "
    "Maps and WhatsApp. When the user asks you to DO one of these (e.g. 'open WhatsApp', "
    "'make a note', 'text Mom'), just DO IT by calling the matching tool. NEVER reply "
    "that you can't perform the action, and never give step-by-step instructions for "
    "something you can do yourself — if a tool exists for it, use the tool. "
    "You're also a great general assistant: answer questions, write, explain, do math "
    "and chat directly from your own knowledge when no action is needed. Consequential "
    "actions (sending a message, creating an event) need the user's approval. After "
    "acting, say plainly what you did. Be concise and warm."
)

DEFAULT_PERSONA = (
    "You are Tandem, a private work assistant that partners with one person over "
    "time. You keep the state of their work, connect evidence across sources, and "
    "help them decide the next useful step -- rather than just answering questions."
)

def _assemble_agent(
    config: AppConfig,
    *,
    memory: MemoryStore,
    skills: SkillStore,
    persona: str,
    approval: ApprovalPolicy | None,
    guardrails: Guardrails | None,
    extra_tools: Iterable[Tool] = (),
    max_steps: int = 6,
) -> Agent:
    """Wire an Agent: LLM backend + the always-on memory/skills tools + any extras.

    The single place the common Agent assembly lives, so every builder stays in
    sync. Duplicate tool names among `extra_tools` are skipped (native vs MCP).
    """
    tools = ToolRegistry()
    tools.register(RememberTool(memory))
    # No RecallTool: relevant memory is auto-injected each turn, and the small model
    # otherwise spuriously calls recall instead of the tool the user actually wants.
    tools.register(SaveSkillTool(skills))
    for tool in extra_tools:
        try:
            tools.register(tool)
        except ValueError:
            pass  # a tool with this name already won (native beats MCP, etc.)

    return Agent(
        llm=OpenAICompatibleLLM(config.llm),
        tools=tools,
        memory=memory,
        skills=skills,
        approval=approval or AutoApprove(),
        guardrails=guardrails,  # None => off (private single-user default)
        persona=persona,
        tool_mode=config.tool_mode,
        reasoning=config.reasoning,
        max_steps=max_steps,
    )


def build_agent(
    config: AppConfig | None = None,
    *,
    approval: ApprovalPolicy | None = None,
    guardrails: Guardrails | None = None,
    persona: str = DEFAULT_PERSONA,
) -> Agent:
    """A general-purpose assistant (web search + sandboxed shell + file access).
    Used by the CLI REPL."""
    config = config or AppConfig.from_env()
    memory = _build_memory(config)

    extra: list[Tool] = [RunCommandTool(SubprocessSandbox(config.data_dir / "sandbox"))]
    if config.tavily_api_key:
        extra.append(WebSearchTool(TavilyProvider(config.tavily_api_key)))
    for integration in _build_integrations(config):
        extra.extend(integration.tools())

    return _assemble_agent(
        config,
        memory=memory,
        skills=FileSkillStore(config.skills_dir),
        persona=persona,
        approval=approval,
        guardrails=guardrails,
        extra_tools=extra,
    )


def build_mac_agent(
    config: AppConfig | None = None,
    *,
    approval: ApprovalPolicy | None = None,
    guardrails: Guardrails | None = None,
    mcp: tuple[list[Tool], list] | None = None,
) -> Agent:
    """
    The Mac personal AI: Nemotron reasoning + native Mac app control + MCP tools.

    Tools come from three composable sources (all behind the same Tool interface):
      1. memory/skills tools (remember / recall / save_skill) — via _assemble_agent
      2. system control (frontmost / open / minimize / hide / shortcut) — always on
      3. MCP servers (apple-mcp for Apple apps, cua for any app) via TANDEM_MCP_SERVERS.

    `mcp`: optional pre-loaded (tools, integrations) so MANY session agents share one
    set of MCP servers (the server loads them once at startup, avoiding a per-session
    subprocess cold-start). If None, this agent loads and OWNS its own servers
    (standalone use — CLI, tests — closes them on eviction).
    """
    config = config or AppConfig.from_env()
    pdir = config.data_dir / "mac"
    memory = _build_project_memory(config, 0, pdir)  # project 0 = personal Mac memory

    owns_mcp = mcp is None
    mcp_tools, mcp_integrations = mcp if mcp is not None else load_mcp_tools()

    extra: list[Tool] = list(mac_system_tools())
    # Replace the raw whatsapp `send_message` with our name-resolving version (the
    # model passes group/contact NAMES, not JIDs). Keep all other MCP tools as-is.
    extra.extend(t for t in mcp_tools if t.name != "send_message")
    if any(t.name == "send_message" for t in mcp_tools):
        extra.append(WhatsAppSendTool())

    agent = _assemble_agent(
        config,
        memory=memory,
        skills=FileSkillStore(pdir / "skills"),
        persona=MAC_PERSONA,
        approval=approval,
        guardrails=guardrails,
        extra_tools=extra,
        max_steps=8,
    )
    agent.add_resource(memory)  # per-agent memory handle, released on eviction
    # Only own (and close) MCP servers we loaded ourselves; shared ones belong to
    # the caller (the server closes them once at shutdown).
    if owns_mcp:
        for integration in mcp_integrations:
            agent.add_resource(integration)
    return agent


def _build_memory(config: AppConfig) -> MemoryStore:
    """Pick the memory backend. Mem0 = semantic (self-hosted); SQLite = fallback."""
    if config.memory_backend == "mem0":
        # Imported lazily so the heavy mem0ai/torch deps are only needed if chosen.
        from tandem.memory.mem0_store import Mem0Store

        return Mem0Store(llm=config.llm, storage_dir=config.data_dir / "mem0")
    return SQLiteMemoryStore(config.db_path)


def _build_project_memory(config: AppConfig, project_id: int, pdir) -> MemoryStore:
    """Project-isolated memory. Mem0 keys by project; SQLite uses a per-project file."""
    if config.memory_backend == "mem0":
        from tandem.memory.mem0_store import Mem0Store

        return Mem0Store(llm=config.llm, storage_dir=pdir / "mem0", user_id=f"project-{project_id}")
    return SQLiteMemoryStore(pdir / "memory.db")


def _build_integrations(config: AppConfig) -> list[Integration]:
    """Wire the integrations available to the agent. Extend here."""
    return [FilesystemIntegration(config.data_dir / "files")]
