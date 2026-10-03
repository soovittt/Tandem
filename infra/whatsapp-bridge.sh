#!/usr/bin/env bash
#
# Run the WhatsApp bridge — this links your PERSONAL WhatsApp to Tandem (locally)
# and must stay running for the whatsapp tools to work.
#
# First run: a QR code prints in this terminal. On your phone open
#   WhatsApp > Settings > Linked Devices > Link a Device  and scan it.
# The session lasts ~20 days before you re-scan. Everything stays on your Mac
# (messages go into vendor/whatsapp-mcp/whatsapp-bridge/store/messages.db).
#
# Leave this running in its own terminal, then (re)start the Tandem backend.
set -euo pipefail

cd "$(dirname "$0")/../vendor/whatsapp-mcp/whatsapp-bridge"
echo "Starting WhatsApp bridge on :8080 — scan the QR with your phone when it appears."
echo "(Ctrl-C to stop. Keep it running while you use WhatsApp from Tandem.)"
exec go run main.go
