"""
Manages the local WhatsApp bridge (the Go whatsmeow process) so the user never
touches a terminal: start it on demand, report its QR + connection status to the
app for an in-app "Connect WhatsApp" flow, and reconnect from the saved session on
boot. Everything stays on-device.

The bridge serves an HTTP API on :8080 (the whatsapp MCP server + this manager both
use it). We just start the process and proxy its /api/qr.
"""

from __future__ import annotations

import json
import re
import sqlite3
import subprocess
import threading
import time
import urllib.request
from pathlib import Path
from typing import Any

from tandem.domain.tool import ToolResult
from tandem.tools.base import Tool

_REPO_ROOT = Path(__file__).resolve().parents[2]
_BRIDGE_DIR = _REPO_ROOT / "vendor/whatsapp-mcp/whatsapp-bridge"
_CHATS_DB = _BRIDGE_DIR / "store" / "messages.db"
_SEND_URL = "http://localhost:8080/api/send"
_NOISE = re.compile(r"\b(group|chat|jid|the|on whatsapp|whatsapp)\b", re.IGNORECASE)


class WhatsAppBridge:
    """Owns the whatsmeow bridge subprocess + its QR/connection status."""

    def __init__(self, bridge_dir: Path | None = None) -> None:
        self._dir = bridge_dir or (_REPO_ROOT / "vendor/whatsapp-mcp/whatsapp-bridge")
        self._binary = self._dir / "whatsapp-bridge"
        self._status_url = "http://localhost:8080/api/qr"
        self._proc: subprocess.Popen | None = None
        self._lock = threading.Lock()

    def has_session(self) -> bool:
        """True if WhatsApp was linked before (a device store exists) — so we can
        reconnect automatically without showing a QR."""
        return (self._dir / "store" / "whatsapp.db").exists()

    def status(self) -> dict:
        """{running, connected, qr}. Hits the bridge's /api/qr; unreachable => the
        bridge isn't up yet. `qr` is the pairing code string (render it client-side)."""
        try:
            with urllib.request.urlopen(self._status_url, timeout=3) as resp:
                data = json.loads(resp.read())
            return {
                "running": True,
                "connected": bool(data.get("connected")),
                "qr": data.get("qr") or None,
            }
        except Exception:
            return {"running": False, "connected": False, "qr": None}

    def ensure_running(self) -> dict:
        """Start the bridge if it isn't already serving, then return status()."""
        if self.status()["running"]:
            return self.status()
        with self._lock:
            if self.status()["running"]:  # double-checked under lock
                return self.status()
            if not self._binary.exists():
                return {"running": False, "connected": False, "qr": None,
                        "error": "bridge not built — run docs/whatsapp-setup build step"}
            (self._dir / "store").mkdir(parents=True, exist_ok=True)
            self._proc = subprocess.Popen(
                [str(self._binary)],
                cwd=str(self._dir),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
            )
        for _ in range(12):  # wait up to ~6s for its REST server + QR
            time.sleep(0.5)
            if self.status()["running"]:
                break
        return self.status()

    def stop(self) -> None:
        with self._lock:
            if self._proc and self._proc.poll() is None:
                self._proc.terminate()
            self._proc = None


class WhatsAppSendTool(Tool):
    """Send a WhatsApp message by NAME. The 8B tends to pass a placeholder like
    'Bhaisexuals group JID' instead of a real JID, which hangs the bridge — so we
    resolve the person/group name to its actual chat JID ourselves (from the bridge's
    local chat DB) before sending. Also accepts a phone number or a raw JID."""

    name = "send_message"
    description = "Send a WhatsApp message to a person or group by name (I find the right chat)."
    parameters = {
        "type": "object",
        "properties": {
            "recipient": {"type": "string",
                          "description": "Person or group NAME (e.g. 'Mom', 'Climbing Crew'), a phone number, or a JID."},
            "message": {"type": "string", "description": "The message text to send."},
        },
        "required": ["recipient", "message"],
    }
    requires_approval = True

    def run(self, **kwargs: Any) -> ToolResult:
        recipient = str(kwargs.get("recipient", "")).strip()
        message = str(kwargs.get("message", ""))
        jid = self._resolve_jid(recipient)
        if "@" not in jid and not jid.replace("+", "").isdigit():
            return ToolResult(
                content=f"Couldn't find a WhatsApp chat matching '{recipient}'. "
                "Try the exact contact/group name, or a phone number."
            )
        try:
            body = json.dumps({"recipient": jid, "message": message}).encode()
            req = urllib.request.Request(_SEND_URL, data=body, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=20) as resp:
                data = json.loads(resp.read())
        except Exception as exc:
            return ToolResult(content=f"WhatsApp send failed: {exc}")
        if data.get("success"):
            return ToolResult(content=f"Sent WhatsApp message to {recipient}.")
        return ToolResult(content=f"WhatsApp: {data.get('message', 'send failed')}")

    def _resolve_jid(self, recipient: str) -> str:
        """Map a person/group name to its chat JID. Passes through JIDs/phone numbers."""
        if "@" in recipient:
            return recipient
        if recipient.replace("+", "").isdigit():
            return recipient.lstrip("+")
        query = _NOISE.sub("", recipient).strip().lower()
        if not query or not _CHATS_DB.exists():
            return recipient
        try:
            conn = sqlite3.connect(f"file:{_CHATS_DB}?mode=ro", uri=True)
            rows = conn.execute(
                "SELECT jid, name FROM chats WHERE name IS NOT NULL ORDER BY last_message_time DESC"
            ).fetchall()
            conn.close()
        except Exception:
            return recipient
        fuzzy: str | None = None
        for jid, name in rows:
            low = (name or "").strip().lower()
            if low == query:
                return jid  # exact (case-insensitive) wins
            if fuzzy is None and (query in low or low in query):
                fuzzy = jid
        return fuzzy or recipient
