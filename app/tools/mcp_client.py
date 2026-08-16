"""
Thin MCP client used by LangGraph nodes to call the tools defined in
mcp_server/server.py. Spawns the server as a subprocess over stdio, per the
MCP spec, and reuses a single session for the lifetime of the process.
"""
from __future__ import annotations

import pathlib
from contextlib import AsyncExitStack

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

SERVER_SCRIPT = pathlib.Path(__file__).resolve().parents[2] / "mcp_server" / "server.py"


class MCPToolClient:
    """Lazily-initialized MCP session, reused across calls."""

    def __init__(self) -> None:
        self._session: ClientSession | None = None
        self._stack: AsyncExitStack | None = None

    async def _ensure_session(self) -> ClientSession:
        if self._session is not None:
            return self._session

        self._stack = AsyncExitStack()
        params = StdioServerParameters(command="python", args=[str(SERVER_SCRIPT)])
        read, write = await self._stack.enter_async_context(stdio_client(params))
        session = await self._stack.enter_async_context(ClientSession(read, write))
        await session.initialize()
        self._session = session
        return session

    async def call_tool(self, name: str, arguments: dict) -> dict:
        session = await self._ensure_session()
        result = await session.call_tool(name, arguments=arguments)
        # MCP returns content blocks; our tools return a single JSON-ish dict
        for block in result.content:
            if hasattr(block, "text"):
                import json

                return json.loads(block.text) if _looks_like_json(block.text) else {"text": block.text}
        return {}

    async def close(self) -> None:
        if self._stack is not None:
            await self._stack.aclose()
            self._session = None
            self._stack = None


def _looks_like_json(text: str) -> bool:
    text = text.strip()
    return text.startswith("{") or text.startswith("[")


_client: MCPToolClient | None = None


def get_mcp_client() -> MCPToolClient:
    global _client
    if _client is None:
        _client = MCPToolClient()
    return _client
