# Tandem — Mac Personal AI

A private, always-on assistant that **reasons over and controls your Mac apps**,
powered by an NVIDIA **Nemotron** model (self-hosted on AWS vLLM now, Nebius later).

## Architecture (built to extend to any number of apps)

```
            ┌──────────────── Agent harness (reused) ────────────────┐
            │  ReAct loop · memory · skills · guardrails · approval   │
            │  tool_mode: native (Nebius Super) | prompt (self-host)  │
            └───────────────┬────────────────────────────────────────┘
                            │ tools come from 3 composable sources
   ┌────────────────────────┼───────────────────────────────────────────┐
   │                        │                                            │
memory/skills      native Mac tools  (src/tandem/mac/)        MCP servers (src/tandem/mcp_servers.py)
remember/recall    one module per app, AppleScript-backed      universal control + Apple apps + files…
save_skill         Calendar·Reminders·Notes·Messages·system     open-computer-use · apple-mcp · filesystem
                   (reliable core)                              (enable via TANDEM_MCP_SERVERS)
                            │
                   Reasoning: Nemotron via OpenAI-compatible endpoint
                   (AWS vLLM today → Nebius by changing LLM_BASE_URL)
```

**Key idea:** every capability is a `Tool`. Native tools are reliable for core Apple
apps; MCP servers add universal accessibility control (any app) + more systems.

## Add a new core app (native)
1. Create `src/tandem/mac/apps/<app>.py` with `Tool` subclasses + `def tools() -> list[Tool]`.
2. Use `run_applescript()` + `as_applescript_string()` from `mac/osascript.py` (safe escaping).
3. Mark consequential actions `requires_approval = True`.
4. Add the module to `_APP_MODULES` in `mac/pack.py`. Done.

## Add any other app/system (MCP)
Add an entry to `MCP_SERVERS` in `mcp_servers.py`, then enable it:
```
TANDEM_MCP_SERVERS=open-computer-use,apple-mcp
```
`open-computer-use` gives accessibility + OCR control of **any** app; `apple-mcp`
covers Mail/Messages/Notes/etc. They're launched over stdio and wrapped into our
Tool interface automatically. Needs the optional `mcp` package (`uv sync --extra mcp`).

## macOS permissions (one-time)
Grant in System Settings → Privacy & Security:
- **Accessibility** — read focused app / control UI (`mac_frontmost_app`, MCP control)
- **Automation** — script Calendar/Reminders/Notes/Messages (prompts per app on first use)
- **Screen Recording** — only if using screenshot/OCR MCP tools

## Run
```
# 1) model: self-hosted Nemotron (AWS) — see infra/aws/, then set LLM_BASE_URL in .env
# 2) backend
uv run uvicorn tandem.server:app --port 8000       # /chat = the Mac agent
# 3) web UI
cd web && npm run dev
```
Switch to Nebius for submission: set `LLM_BASE_URL` to the Nebius endpoint,
`LLM_MODEL=nvidia/nemotron-3-super-120b-a12b`, and `TOOL_MODE=native`.

## Safety
Consequential actions (send message, create event, run shortcut) are
`requires_approval` — they pass through the `ApprovalPolicy` before running.
