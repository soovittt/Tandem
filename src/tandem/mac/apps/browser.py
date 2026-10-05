"""Browser control for Safari and Chrome-family browsers via AppleScript.

Reading the current tab's URL/title and listing tabs needs no special grant.
Reading page TEXT needs the browser's "Allow JavaScript from Apple Events"
developer setting; we try it and fall back to just URL + title if it's off.
"""

from __future__ import annotations

from typing import Any

from tandem.domain.tool import ToolResult
from tandem.mac.osascript import as_applescript_string, run_applescript, running_app_names
from tandem.tools.base import Tool

# Chrome-family browsers share one AppleScript dictionary ("active tab of front
# window"). Safari uses "current tab" and `name` instead of `title`.
_CHROME_FAMILY = ["Google Chrome", "Brave Browser", "Microsoft Edge", "Arc", "Chromium"]
_SAFARI = "Safari"


def _pick_browser() -> tuple[str, str] | None:
    """Return (app_name, family) of a running browser, preferring the frontmost one.
    family is 'chrome' or 'safari'. None if no supported browser is open."""
    running = running_app_names()
    ok, front = run_applescript(
        'tell application "System Events" to get name of first application process whose frontmost is true'
    )
    for name in ([front] if ok else []) + _CHROME_FAMILY + [_SAFARI]:
        if name not in running:
            continue
        if name == _SAFARI:
            return name, "safari"
        if name in _CHROME_FAMILY:
            return name, "chrome"
    return None


def _page_text(app: str, family: str) -> str:
    """Best-effort visible text of the current tab (empty if the browser's
    'Allow JavaScript from Apple Events' setting is off)."""
    a = as_applescript_string(app)
    if family == "safari":
        script = f'tell application {a} to do JavaScript "document.body.innerText" in current tab of front window'
    else:
        script = f'tell application {a} to execute active tab of front window javascript "document.body.innerText"'
    ok, out = run_applescript(script, timeout=15)
    return out if ok else ""


class ActiveTabTool(Tool):
    name = "browser_active_tab"
    description = (
        "Read the URL, title, and visible text of the browser tab the user is currently "
        "viewing. Use to summarize or answer questions about the page they're on."
    )
    parameters = {
        "type": "object",
        "properties": {
            "include_text": {
                "type": "boolean",
                "description": "Also fetch the page's visible text (default true).",
            }
        },
    }

    def run(self, **kwargs: Any) -> ToolResult:
        picked = _pick_browser()
        if picked is None:
            return ToolResult(content="No supported browser (Safari or Chrome) is open.")
        app, family = picked
        a = as_applescript_string(app)
        if family == "safari":
            script = f'tell application {a} to (URL of current tab of front window) & "|||" & (name of current tab of front window)'
        else:
            script = f'tell application {a} to (URL of active tab of front window) & "|||" & (title of active tab of front window)'
        ok, out = run_applescript(script, timeout=10)
        if not ok:
            if "timed out" in out.lower():
                out += (
                    f" — grant Automation access for {app} once in System Settings ▸ "
                    "Privacy & Security ▸ Automation (a prompt may be waiting on screen)."
                )
            return ToolResult(content=f"Couldn't read {app}: {out}")
        url, _, title = out.partition("|||")
        result = f"Title: {title.strip()}\nURL: {url.strip()}"
        if kwargs.get("include_text", True):
            text = _page_text(app, family).strip()
            if text:
                result += f"\n\nText:\n{text[:6000]}"
            else:
                result += "\n\n(Page text unavailable — enable the browser's Develop ▸ 'Allow JavaScript from Apple Events' to read page content.)"
        return ToolResult(content=result)


class OpenURLTool(Tool):
    name = "browser_open_url"
    description = "Open a web page (URL) in the default browser."
    parameters = {
        "type": "object",
        "properties": {"url": {"type": "string", "description": "The URL or domain to open."}},
        "required": ["url"],
    }

    def run(self, **kwargs: Any) -> ToolResult:
        url = str(kwargs.get("url", "")).strip()
        if not url:
            return ToolResult(content="Give me a URL to open.")
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        ok, out = run_applescript(f"open location {as_applescript_string(url)}")
        return ToolResult(content=f"Opened {url}" if ok else f"Error: {out}")


class ListTabsTool(Tool):
    name = "browser_list_tabs"
    description = "List the open tabs (title + URL) in the current browser window."
    parameters = {"type": "object", "properties": {}}

    def run(self, **kwargs: Any) -> ToolResult:
        picked = _pick_browser()
        if picked is None:
            return ToolResult(content="No supported browser (Safari or Chrome) is open.")
        app, family = picked
        a = as_applescript_string(app)
        title_prop = "name" if family == "safari" else "title"
        script = (
            f"tell application {a}\n"
            "  set out to \"\"\n"
            "  repeat with t in tabs of front window\n"
            f"    set out to out & ({title_prop} of t) & \" — \" & (URL of t) & linefeed\n"
            "  end repeat\n"
            "  return out\n"
            "end tell"
        )
        ok, out = run_applescript(script, timeout=10)
        if not ok:
            return ToolResult(content=f"Couldn't list tabs in {app}: {out}")
        return ToolResult(content=out.strip() or f"No open tabs in {app}.")


def tools() -> list[Tool]:
    return [ActiveTabTool(), OpenURLTool(), ListTabsTool()]
