"""
MCP integration: connect to any Model Context Protocol server and expose its
tools as our tools — with a PERSISTENT session.

MCP's stdio client uses anyio task groups whose context managers must be entered
and exited in the SAME task. So we run the whole session lifecycle inside one
long-lived coroutine on a background event-loop thread, and dispatch tool calls to
it over an asyncio.Queue (each carrying a thread-safe Future the sync caller waits
on). This keeps one server process alive for all calls — no per-call respawn.

The optional `mcp` package is imported lazily, so the rest of the app never
depends on it.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import json
import threading
from typing import Any, Callable

from tandem.domain.tool import ToolResult
from tandem.tools.base import Tool

RemoteCaller = Callable[[str, dict[str, Any]], str]


class RemoteMCPTool(Tool):
    """Adapts one MCP-server tool to our Tool interface."""

    def __init__(
        self,
        *,
        name: str,
        description: str,
        parameters: dict[str, Any],
        caller: RemoteCaller,
    ) -> None:
        self.name = name
        self.description = description or f"Remote MCP tool {name}"
        self.parameters = parameters or {"type": "object", "properties": {}}
        self._caller = caller

    def run(self, **kwargs: Any) -> ToolResult:
        try:
            return ToolResult(content=self._caller(self.name, kwargs))
        except Exception as exc:
            return ToolResult(content=f"MCP tool {self.name!r} failed: {exc}")


class _StdioMCPServer:
    """A persistent connection to one stdio MCP server on a dedicated thread.

    We run `asyncio.run()` on the thread (NOT a hand-managed loop) so asyncio's
    subprocess child-watcher is set up correctly off the main thread — a manually
    run loop fails to spawn the server process. One task owns the session's context
    managers for its whole life; calls are dispatched over an asyncio.Queue.
    """

    def __init__(self, command: list[str], *, connect_timeout: float = 60.0, call_timeout: float = 45.0) -> None:
        self._call_timeout = call_timeout
        self._loop: asyncio.AbstractEventLoop | None = None
        self._queue: asyncio.Queue | None = None
        self._ready_error: Exception | None = None
        self._closed = False
        self.specs: list[dict[str, Any]] = []

        self._ready = threading.Event()
        self._thread = threading.Thread(target=self._thread_main, args=(command,), daemon=True, name="mcp-server")
        self._thread.start()
        if not self._ready.wait(connect_timeout):
            raise RuntimeError("MCP server did not become ready in time")
        if self._ready_error is not None:
            raise self._ready_error

    def _thread_main(self, command: list[str]) -> None:
        try:
            asyncio.run(self._main(command))
        except Exception as exc:
            if self._ready_error is None:
                self._ready_error = exc
            self._ready.set()

    async def _main(self, command: list[str]) -> None:
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client

        self._loop = asyncio.get_running_loop()
        self._queue = asyncio.Queue()
        params = StdioServerParameters(command=command[0], args=command[1:])
        try:
            async with stdio_client(params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    listed = await session.list_tools()
                    self.specs = [
                        {
                            "name": t.name,
                            "description": t.description or "",
                            "parameters": _tool_schema(t),
                        }
                        for t in listed.tools
                    ]
                    self._ready.set()
                    while True:
                        item = await self._queue.get()
                        if item is None:
                            break
                        name, arguments, future = item
                        try:
                            result = await session.call_tool(name, arguments)
                            if not future.done():
                                future.set_result(_content_to_text(result))
                        except Exception as exc:  # per-call error → back to caller
                            if not future.done():
                                future.set_exception(exc)
        finally:
            # Server is gone — fail any waiting/queued calls instead of hanging.
            self._closed = True
            self._drain_pending()

    def _drain_pending(self) -> None:
        if self._queue is None:
            return
        while not self._queue.empty():
            try:
                item = self._queue.get_nowait()
            except Exception:
                break
            if item is None:
                continue
            _, _, future = item
            if not future.done():
                future.set_exception(RuntimeError("MCP server closed"))

    def call(self, name: str, arguments: dict[str, Any]) -> str:
        if self._closed or self._loop is None or self._queue is None:
            return "(MCP server is not available)"
        future: concurrent.futures.Future[str] = concurrent.futures.Future()
        self._loop.call_soon_threadsafe(self._queue.put_nowait, (name, arguments, future))
        try:
            return future.result(timeout=self._call_timeout)
        except concurrent.futures.TimeoutError:
            return "(MCP tool timed out)"

    def close(self) -> None:
        if self._closed:
            return
        if self._loop is not None and self._queue is not None:
            try:
                self._loop.call_soon_threadsafe(self._queue.put_nowait, None)
            except Exception:
                pass


class MCPIntegration:
    """An Integration whose tools are proxied from a persistent MCP server."""

    name = "mcp"

    def __init__(self, tools: list[Tool], server: _StdioMCPServer | None = None) -> None:
        self._tools = tools
        self._server = server

    def tools(self) -> list[Tool]:
        return self._tools

    def close(self) -> None:
        if self._server is not None:
            self._server.close()

    @classmethod
    def from_stdio(cls, command: list[str]) -> "MCPIntegration":
        try:
            import mcp  # noqa: F401
        except ImportError as exc:
            raise RuntimeError(
                "MCP integration needs the `mcp` package. Install with `uv sync --extra mcp`."
            ) from exc

        server = _StdioMCPServer(command)
        tools: list[Tool] = [
            RemoteMCPTool(
                name=spec["name"],
                description=spec["description"],
                parameters=spec["parameters"],
                caller=server.call,
            )
            for spec in server.specs
        ]
        return cls(tools, server)


def _tool_schema(tool: Any) -> dict[str, Any]:
    """The tool's JSON-Schema, tolerant of mcp version field naming."""
    schema = getattr(tool, "input_schema", None) or getattr(tool, "inputSchema", None)
    return schema or {"type": "object", "properties": {}}


def _content_to_text(result: Any) -> str:
    """Flatten an MCP call result into plain text for the model."""
    parts = getattr(result, "content", None)
    if not parts:
        structured = getattr(result, "structuredContent", None)
        return json.dumps(structured) if structured else "(no output)"
    texts = [getattr(p, "text", "") for p in parts]
    return "\n".join(t for t in texts if t) or "(no output)"
