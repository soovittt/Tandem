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
import subprocess
import threading
import time
import urllib.request
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]


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
