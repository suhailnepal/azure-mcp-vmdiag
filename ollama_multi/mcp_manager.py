import asyncio
from contextlib import AsyncExitStack
from typing import Any, Dict, List, Tuple

from mcp import ClientSession, StdioServerParameters, types
from mcp.client.stdio import stdio_client

class MCPManager:
    """
    Opens and holds two MCP sessions:
      - 'azure'     -> Azure MCP server
      - 'filesystem'-> Filesystem MCP server
    Provides unified list_tools and call_tool helpers.
    """

    def __init__(
        self,
        azure_cmd: str,
        azure_args: List[str],
        fs_cmd: str,
        fs_args: List[str],
    ) -> None:
        self.azure_params = StdioServerParameters(command=azure_cmd, args=azure_args)
        self.fs_params = StdioServerParameters(command=fs_cmd, args=fs_args)
        self._stack: AsyncExitStack | None = None
        self.sessions: Dict[str, ClientSession] = {}

    async def __aenter__(self) -> "MCPManager":
        self._stack = AsyncExitStack()
        # Azure
        az_read, az_write = await self._stack.enter_async_context(stdio_client(self.azure_params))
        az_session = await self._stack.enter_async_context(ClientSession(az_read, az_write))
        await az_session.initialize()
        self.sessions["azure"] = az_session

        # Filesystem
        fs_read, fs_write = await self._stack.enter_async_context(stdio_client(self.fs_params))
        fs_session = await self._stack.enter_async_context(ClientSession(fs_read, fs_write))
        await fs_session.initialize()
        self.sessions["filesystem"] = fs_session

        return self

    async def __aexit__(self, exc_type, exc, tb):
        if self._stack:
            await self._stack.aclose()

    async def list_tools(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        Returns a map of server -> tool summaries
        Each tool summary: {name, description}
        """
        result: Dict[str, List[Dict[str, Any]]] = {}
        for server, session in self.sessions.items():
            tools = await session.list_tools()
            summaries = []
            for t in tools.tools:
                desc = getattr(t, "description", None)
                summaries.append({"name": t.name, "description": desc or ""})
            result[server] = summaries
        return result

    async def call_tool(self, server: str, tool_name: str, arguments: Dict[str, Any]) -> str:
        """
        Calls a tool on the chosen server and returns a stringified result suitable for LLM context.
        """
        if server not in self.sessions:
            raise ValueError(f"Unknown MCP server: {server}")
        session = self.sessions[server]

        # Invoke the tool
        result = await session.call_tool(tool_name, arguments=arguments or {})

        # Prefer structured content if provided, else flatten text content
        if getattr(result, "structuredContent", None) is not None:
            return _safe_to_str(result.structuredContent)

        # fall back to text content blocks
        parts: List[str] = []
        for c in result.content:
            if isinstance(c, types.TextContent):
                parts.append(c.text)
            else:
                parts.append(_safe_to_str(c.__dict__))
        return "\n".join(parts)

def _safe_to_str(obj: Any) -> str:
    try:
        import json
        return json.dumps(obj, ensure_ascii=False, indent=2)
    except Exception:
        return str(obj)
