import asyncio
import json
from typing import Any, Dict, List, Optional

from .config import (
    OLLAMA_MODEL,
    OLLAMA_URL,
    AZURE_MCP_CMD,
    AZURE_MCP_ARGS,
    FS_MCP_CMD,
    FS_MCP_ARGS,
    HISTORY_PATH,
    HISTORY_MAX_TURNS,
)
from .mcp_manager import MCPManager
from .ollama_llm import OllamaLLM, build_mcp_tools_schema
from .history import load_history, save_history, trim_history

SYSTEM_PROMPT = """You are an AI assistant with access to two MCP servers: 'azure' and 'filesystem'.
You can discover tools with mcp_list_tools, then invoke them with mcp_call_tool.
When you need to interact with Azure or the local filesystem, call an MCP tool.
Prefer to call mcp_list_tools first if you are unsure about arguments or available tools.
Be concise and explain what you did."""

class ChatApp:
    def __init__(self) -> None:
        self.messages: List[Dict[str, Any]] = []
        self.llm = OllamaLLM(model=OLLAMA_MODEL, url=OLLAMA_URL)
        self.mcp: Optional[MCPManager] = None
        self.tools_schema = build_mcp_tools_schema()

    async def start(self) -> None:
        # Restore prior history (optional)
        self.messages = load_history(HISTORY_PATH)
        if not self.messages or self.messages[0].get("role") != "system":
            self.messages = [{"role": "system", "content": SYSTEM_PROMPT}]

        # Start MCP sessions
        self.mcp = await MCPManager(
            AZURE_MCP_CMD, AZURE_MCP_ARGS, FS_MCP_CMD, FS_MCP_ARGS
        ).__aenter__()

        # Print a short tools index at startup
        await self._print_tool_index()

        # CLI loop
        print("\nType your prompt. Type 'quit' to exit.\n")
        while True:
            user = input("> ").strip()
            if user.lower() in {"quit", "exit"}:
                break
            if not user:
                continue

            # add user message
            self.messages.append({"role": "user", "content": user})

            # loop: model may request tools multiple times
            final_text = await self._answer_with_tools()
            print(f"\n{final_text}\n")

            # Persist rolling history
            self.messages = trim_history(self.messages, HISTORY_MAX_TURNS)
            save_history(HISTORY_PATH, self.messages)

        # Cleanup
        if self.mcp:
            await self.mcp.__aexit__(None, None, None)

    async def _answer_with_tools(self) -> str:
        assert self.mcp is not None
        # 1st pass
        resp = await self.llm.chat(self.messages, tools=self.tools_schema)
        msg = resp.get("message", {})
        tool_calls = msg.get("tool_calls", []) or []

        # Accumulate assistant visible text as we go
        assistant_text_chunks: List[str] = []
        if msg.get("content"):
            assistant_text_chunks.append(msg["content"])

        # Handle tool calls until none remain
        while tool_calls:
            for call in tool_calls:
                fn = call.get("function", {}) or {}
                name = fn.get("name")
                args = fn.get("arguments", {}) or {}

                if name == "mcp_list_tools":
                    server = args.get("server")
                    tools_map = await self.mcp.list_tools()
                    if server:
                        result = {server: tools_map.get(server, [])}
                    else:
                        result = tools_map
                    tool_output = json.dumps(result, ensure_ascii=False, indent=2)

                elif name == "mcp_call_tool":
                    server = args.get("server")
                    tool = args.get("tool")
                    arguments = args.get("arguments") or {}
                    if not server or not tool:
                        tool_output = "Error: mcp_call_tool requires 'server' and 'tool'."
                    else:
                        try:
                            tool_output = await self.mcp.call_tool(server, tool, arguments)
                        except Exception as e:
                            tool_output = f"Error calling {server}.{tool}: {e}"
                else:
                    tool_output = f"Unknown tool request: {name}"

                # Feed the tool result back to the model
                self.messages.append({"role": "tool", "content": tool_output, "name": name})

            # ask model again with the tool results included
            resp = await self.llm.chat(self.messages, tools=self.tools_schema)
            msg = resp.get("message", {})
            if msg.get("content"):
                assistant_text_chunks.append(msg["content"])
            tool_calls = msg.get("tool_calls", []) or []

        # append final assistant message to history
        final_text = "\n".join([t for t in assistant_text_chunks if t])
        self.messages.append({"role": "assistant", "content": final_text})
        return final_text

    async def _print_tool_index(self) -> None:
        try:
            tools_map = await self.mcp.list_tools()
        except Exception as e:
            print(f"Could not fetch tools list: {e}")
            return
        print("\n=== MCP tools discovered ===")
        for server, tools in tools_map.items():
            print(f"[{server}]")
            for t in tools:
                name = t["name"]
                desc = f" - {t['description']}" if t.get("description") else ""
                print(f"  • {name}{desc}")

def main():
    asyncio.run(ChatApp().start())

if __name__ == "__main__":
    main()
