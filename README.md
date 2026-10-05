<div align="center">

# ✦ Tandem

**A private, native macOS AI assistant that reasons over and controls your Mac.**

Powered by **NVIDIA Nemotron-3** served on **Nebius Token Factory**.

[![License: MIT](https://img.shields.io/badge/License-MIT-5b4ff5.svg)](./LICENSE)
![Platform: macOS](https://img.shields.io/badge/platform-macOS%2013%2B-black)
![Model: NVIDIA Nemotron-3](https://img.shields.io/badge/model-NVIDIA%20Nemotron--3-76b900)
![Infra: Nebius Token Factory](https://img.shields.io/badge/infra-Nebius%20Token%20Factory-0b84ff)

</div>

---

Tandem lives in your menu bar. Hit **⌥Space**, type what you want in plain English, and it
*does* it — opens and controls apps, reads and triages your mail and calendar, takes notes,
sends messages, searches the web, drives a real browser, and chains these into multi-step
workflows. Everything runs on your machine and your data stays local; the only thing that
leaves is the prompt sent to your own Nemotron endpoint.

## Highlights

- **🖥️ Controls your Mac** — open / switch / quit apps, volume, Dark Mode, Spotlight search, clipboard.
- **📇 Apple apps** — read & act in Mail, Calendar, Reminders, Notes, Contacts, Messages, Maps.
- **💬 Messaging** — WhatsApp (your own account, linked locally over a QR), iMessage.
- **🌐 Real web automation** — a browser sub-agent navigates, clicks, fills forms, and extracts data.
- **🔎 Web search & research** — cited answers that land straight in a note.
- **🧠 Memory & skills** — remembers what matters and turns repeated work into reusable skills.
- **✅ Human-in-the-loop** — consequential actions (send, create, delete) require a one-tap approval.
- **🔒 Private by default** — on-device; no telemetry; your data never leaves your Mac except the model call.

## Powered by NVIDIA Nemotron on Nebius Token Factory

The reasoning engine is **NVIDIA's open Nemotron-3 family**, served over the OpenAI-compatible
**Nebius Token Factory** API:

- **Nemotron-3 Nano (30B)** drives the snappy, everyday command-bar interactions.
- **Nemotron-3 Super (120B)** is routed in for the heavy, multi-step agentic work (e.g. browser automation).

Switching models or endpoints is a one-line change in `.env` — no code changes.

## How it works

```
  ⌥Space ──► Tandem command bar (SwiftUI, menu-bar app)
                     │  HTTP / SSE
                     ▼
            Python backend (FastAPI)
                     │
   ┌─────────────────┼───────────────────────────────┐
   │                 │                                │
 Nemotron-3       Tool layer                    Human-in-the-loop
 (Nebius      native Mac control · apple-mcp ·     approval broker
 Token        WhatsApp · browser automation ·
 Factory)     web search · memory · skills
```

- **Native app:** `mac-app/` — a Swift Package (menu-bar `LSUIElement` app, Carbon ⌥Space hotkey, SwiftUI command bar, Control Center window).
- **Agent & tools:** `src/tandem/` — the agent loop, the OpenAI-compatible LLM client, native macOS tools, an MCP registry (Apple apps, WhatsApp, …), memory and skills.
- **Integrations are composable:** adding an app is one entry in the MCP registry; adding a native tool is one small module.

## Quickstart

**Prerequisites:** macOS 13+, [`uv`](https://docs.astral.sh/uv/), a Swift toolchain (Xcode CLT), and a **Nebius Token Factory** API key.

```bash
# 1. Install Python deps
uv sync

# 2. Configure your model endpoint
cp .env.example .env
#   set in .env:
#   LLM_PROVIDER=nebius
#   LLM_BASE_URL=https://api.tokenfactory.nebius.com/v1/
#   LLM_MODEL=nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B
#   LLM_API_KEY=<your Nebius Token Factory key>

# 3. Run the backend
uv run uvicorn tandem.server:app --host 127.0.0.1 --port 8000

# 4. Build & launch the menu-bar app
cd mac-app && ./build-app.sh && open Tandem.app
```

Then press **⌥Space** and ask it anything. Optional integrations (WhatsApp linking, the browser
sub-agent, extra MCP servers) are documented in [`docs/`](./docs).

## Repository layout

| Path | What |
|---|---|
| `mac-app/` | Native SwiftUI menu-bar app (the command bar + Control Center) |
| `src/tandem/` | Python agent, LLM client, tools, MCP registry, memory, skills |
| `src/tandem/mac/` | Native macOS control (apps, browser, files, media, clipboard, notes) |
| `docs/` | Architecture notes and integration setup guides |
| `infra/` | Optional setup scripts (browser sub-agent, etc.) |

## Privacy & security

- `.env`, API keys, `*.pem`, local databases, and any linked WhatsApp session are **git-ignored** and never committed.
- Consequential actions are gated behind explicit, per-action user approval.

## Acknowledgements

Built on the shoulders of excellent open source: **NVIDIA Nemotron**, **Nebius Token Factory**,
[apple-mcp](https://github.com/supermemoryai/apple-mcp), [browser-use](https://github.com/browser-use/browser-use),
the [Model Context Protocol](https://modelcontextprotocol.io), and [Tavily](https://tavily.com) for web search.

## License

[MIT](./LICENSE) © 2026 Sovit Nayak
