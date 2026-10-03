# WhatsApp support (local, private)

Tandem talks to **your own WhatsApp** through a local bridge — no cloud, no third
party. Messages stay on your Mac. It can read chats, search contacts, and send
messages to **people and groups**. Sends are approval-gated like every other
consequential action.

This uses [lharries/whatsapp-mcp](https://github.com/lharries/whatsapp-mcp) (a Go
`whatsmeow` bridge + a Python MCP server), vendored under `vendor/whatsapp-mcp/`.

## Architecture

```
Tandem agent ──stdio──> whatsapp MCP server (Python) ──HTTP/SQLite──> WhatsApp bridge (Go, :8080) ──> WhatsApp
```

- **Bridge** (Go): links your account via QR, keeps a local SQLite of messages, sends.
- **MCP server** (Python): exposes 12 tools (`list_chats`, `search_contacts`,
  `send_message`, …) — Tandem launches it over stdio automatically.

## One-time setup

Prereqs (already present on this machine): `go`, `uv`, `ffmpeg`.

1. **Install the Python MCP server deps** (creates its venv — Tandem runs this venv's
   Python directly; do NOT use `uv run`, it hangs when nested in the backend):
   ```bash
   uv --directory vendor/whatsapp-mcp/whatsapp-mcp-server sync
   ```

2. **Start the bridge and link your WhatsApp** (leave it running in its own terminal):
   ```bash
   ./infra/whatsapp-bridge.sh
   ```
   Scan the QR with your phone: **WhatsApp > Settings > Linked Devices > Link a Device**.
   (Session lasts ~20 days.)

3. **Enable it for Tandem** — already done in `.env`:
   ```
   TANDEM_MCP_SERVERS=apple-mcp,whatsapp
   ```
   Restart the backend. You should see `[mcp] loaded 12 tools from 'whatsapp'`.

## Using it

Now Tandem can do things like:
- *"what are my latest WhatsApp messages?"*
- *"send 'running late' to the Climbing group on WhatsApp"* ⚠️ (approval card)
- *"text [contact] on WhatsApp: see you at 6"* ⚠️

It resolves a group/contact by name via `search_contacts` / `list_chats`, then sends
to the right JID — which fixes the "it guessed a phone number" problem Apple Messages
had with groups.

## Notes

- If the bridge isn't running, the whatsapp tools still load but calls fail
  gracefully (you'll get an error turn, not a crash).
- `WHATSAPP_MCP_DIR` env var overrides the server location if you clone it elsewhere.
- This is an **unofficial** WhatsApp connection (whatsmeow). Use your own account.
