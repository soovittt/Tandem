"""
Composition root.

The ONE place where concrete implementations are chosen and wired together. Every
other module depends only on interfaces; here we pick SQLite/Mem0 for memory,
files for skills, the OpenAI-compatible backend for the model, a subprocess
sandbox, the filesystem integration, and so on. To change an implementation, you
change it here and nowhere else.
"""

from __future__ import annotations

from tandem.agent.agent import Agent
from tandem.agent.approval import ApprovalPolicy, AutoApprove
from tandem.agent.orchestrator import Orchestrator
from tandem.config import AppConfig
from tandem.guardrails.base import Guardrails
from tandem.guardrails.builtin import PIIRedactionGuardrail
from tandem.integrations.base import Integration
from tandem.integrations.filesystem import FilesystemIntegration
from tandem.llm.openai_compatible import OpenAICompatibleLLM
from tandem.memory.base import MemoryStore
from tandem.memory.sqlite_store import SQLiteMemoryStore
from tandem.security.subprocess_sandbox import SubprocessSandbox
from tandem.skills.file_store import FileSkillStore
from tandem.tools.base import ToolRegistry
from tandem.tools.code_execution import RunCommandTool
from tandem.tools.memory_tools import RecallTool, RememberTool
from tandem.tools.skill_tools import SaveSkillTool
from tandem.tools.web_search import TavilyProvider, WebSearchTool
from tandem.mac.pack import mac_app_tools, mac_system_tools
from tandem.mcp_servers import load_mcp_tools

MAC_PERSONA = (
    "You are Tandem, a personal AI that lives on the user's Mac. You can see what "
    "they're working on and control their apps — Calendar, Reminders, Notes, Messages, "
    "files, and (via the universal driver) any other app — to actually get things done, "
    "not just answer. Prefer the most direct tool. Consequential actions require approval. "
    "After acting, say plainly what you did."
)

DEFAULT_PERSONA = (
    "You are Tandem, a private work assistant that partners with one person over "
    "time. You keep the state of their work, connect evidence across sources, and "
    "help them decide the next useful step -- rather than just answering questions."
)


def build_agent(
    config: AppConfig | None = None,
    *,
    approval: ApprovalPolicy | None = None,
    guardrails: Guardrails | None = None,
    persona: str = DEFAULT_PERSONA,
) -> Agent:
    """Assemble a fully-wired Agent from configuration."""
    config = config or AppConfig.from_env()

    llm = OpenAICompatibleLLM(config.llm)
    memory = _build_memory(config)
    skills = FileSkillStore(config.skills_dir)

    tools = ToolRegistry()
    tools.register(RememberTool(memory))
    tools.register(RecallTool(memory))
    tools.register(SaveSkillTool(skills))
    tools.register(RunCommandTool(SubprocessSandbox(config.data_dir / "sandbox")))
    if config.tavily_api_key:
        tools.register(WebSearchTool(TavilyProvider(config.tavily_api_key)))
    for integration in _build_integrations(config):
        for tool in integration.tools():
            tools.register(tool)

    return Agent(
        llm=llm,
        tools=tools,
        memory=memory,
        skills=skills,
        approval=approval or AutoApprove(),
        guardrails=guardrails,  # None => off (private single-user default)
        persona=persona,
        tool_mode=config.tool_mode,
        reasoning=config.reasoning,
    )


def build_project_agent(
    config: AppConfig,
    *,
    project_id: int,
    project_name: str,
    integration_names: list[str],
    approval: ApprovalPolicy | None = None,
) -> Agent:
    """
    An agent scoped to ONE project: its memory and skills live under the project's
    own directory (isolated from other projects), and its persona knows the
    project name + which systems are connected. This is what makes the assistant
    actually "know" the workspace it's in.
    """
    pdir = config.data_dir / "projects" / str(project_id)

    llm = OpenAICompatibleLLM(config.llm)
    memory = _build_project_memory(config, project_id, pdir)
    skills = FileSkillStore(pdir / "skills")

    tools = ToolRegistry()
    tools.register(RememberTool(memory))
    tools.register(RecallTool(memory))
    tools.register(SaveSkillTool(skills))
    tools.register(RunCommandTool(SubprocessSandbox(pdir / "sandbox")))
    if config.tavily_api_key:
        tools.register(WebSearchTool(TavilyProvider(config.tavily_api_key)))
    for integration in _build_integrations(config):
        for tool in integration.tools():
            tools.register(tool)

    connected = ", ".join(integration_names) if integration_names else "none connected yet"
    persona = (
        f"{DEFAULT_PERSONA}\n\n"
        f"You are the assistant for the '{project_name}' project. Connected systems "
        f"you may draw on: {connected}. Keep memory and answers scoped to this project."
    )
    return Agent(
        llm=llm,
        tools=tools,
        memory=memory,
        skills=skills,
        approval=approval or AutoApprove(),
        persona=persona,
        tool_mode=config.tool_mode,
        reasoning=config.reasoning,
    )


def build_mac_agent(
    config: AppConfig | None = None,
    *,
    approval: ApprovalPolicy | None = None,
    guardrails: Guardrails | None = None,
) -> Agent:
    """
    The Mac personal AI: Nemotron reasoning + native Mac app control + MCP tools.

    Tools come from three composable sources (all behind the same Tool interface):
      1. memory/skills tools (remember / recall / save_skill)
      2. native Mac app pack (Calendar, Reminders, Notes, Messages, system) — reliable
      3. MCP servers (universal accessibility control, Apple apps, files, ...) — enabled
         via TANDEM_MCP_SERVERS. Native tools win on name clashes.
    """
    config = config or AppConfig.from_env()
    pdir = config.data_dir / "mac"

    llm = OpenAICompatibleLLM(config.llm)
    memory = _build_project_memory(config, 0, pdir)  # project 0 = personal Mac memory
    skills = FileSkillStore(pdir / "skills")

    tools = ToolRegistry()
    tools.register(RememberTool(memory))
    tools.register(RecallTool(memory))
    tools.register(SaveSkillTool(skills))

    # System tools always on (no MCP server covers frontmost/open/shortcut).
    for tool in mac_system_tools():
        tools.register(tool)

    # MCP servers (apple-mcp for Apple apps, open-computer-use/cua for any app).
    mcp_tools, mcp_integrations = load_mcp_tools()
    for tool in mcp_tools:
        try:
            tools.register(tool)
        except ValueError:
            pass  # skip duplicate tool names

    # Native Apple-app tools are a reliable FALLBACK — only when no MCP server
    # already covers those apps (avoids confusing duplicates + double approval).
    _apple_app_tools = {"messages", "notes", "reminders", "calendar", "mail", "contacts"}
    if not any(t.name in _apple_app_tools for t in mcp_tools):
        for tool in mac_app_tools():
            try:
                tools.register(tool)
            except ValueError:
                pass

    agent = Agent(
        llm=llm,
        tools=tools,
        memory=memory,
        skills=skills,
        approval=approval or AutoApprove(),
        guardrails=guardrails,
        persona=MAC_PERSONA,
        tool_mode=config.tool_mode,
        reasoning=config.reasoning,
        max_steps=8,
    )
    # Release MCP subprocesses + the DB connection when this agent is evicted.
    for integration in mcp_integrations:
        agent.add_resource(integration)
    agent.add_resource(memory)
    return agent


def build_orchestrator(
    config: AppConfig | None = None,
    *,
    approval: ApprovalPolicy | None = None,
) -> Orchestrator:
    """Build an Orchestrator whose subagents share this config's memory + tools."""
    config = config or AppConfig.from_env()
    llm = OpenAICompatibleLLM(config.llm)

    def subagent_factory(focused_persona: str) -> Agent:
        # Each subagent is a fresh Agent over the SAME stores (shared memory),
        # just with a narrower persona.
        return build_agent(config, approval=approval, persona=focused_persona)

    return Orchestrator(llm=llm, subagent_factory=subagent_factory)


def build_guardrails() -> Guardrails:
    """A sensible enterprise/team preset. Off by default in build_agent."""
    return Guardrails(
        input=[PIIRedactionGuardrail()],
        output=[PIIRedactionGuardrail()],
    )


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
