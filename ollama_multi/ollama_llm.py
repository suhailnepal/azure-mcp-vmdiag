import asyncio
from typing import Any, Dict, List, Optional

import ollama

class OllamaLLM:
    """
    Minimal wrapper for ollama.chat with support for tool calling.
    """

    def __init__(
        self,
        model: str,
        url: str = "http://localhost:11434",
        temperature: float = 0.2,
        max_tokens: Optional[int] = None,
    ) -> None:
        self.model = model
        self.url = url
        self.temperature = temperature
        self.max_tokens = max_tokens

    async def chat(self, messages: List[Dict[str, Any]], tools: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        """
        Calls ollama.chat in a thread so the asyncio loop isn't blocked.
        Returns the full response dict:
          { 'message': {'role': 'assistant', 'content': str, 'tool_calls': [...]}, ... }
        """
        def _call():
            kwargs = dict(model=self.model, messages=messages, options={"temperature": self.temperature})
            if self.max_tokens:
                kwargs["options"]["num_predict"] = self.max_tokens
            if tools:
                kwargs["tools"] = tools
            return ollama.chat(**kwargs)

        return await asyncio.to_thread(_call)

def build_mcp_tools_schema() -> List[Dict[str, Any]]:
    """
    We expose two generic tools to the model:
      - mcp_list_tools(server?: 'azure' | 'filesystem') -> get names + descriptions
      - mcp_call_tool(server: 'azure' | 'filesystem', tool: string, arguments: object)
    This avoids having to mirror every server's JSON schema 1:1 while still giving the model full MCP access.
    """
    return [
        {
            "type": "function",
            "function": {
                "name": "mcp_list_tools",
                "description": "List the available tools for one or all MCP servers.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "server": {
                            "type": "string",
                            "enum": ["azure", "filesystem"],
                            "description": "If omitted, list tools for both servers.",
                        }
                    }
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "mcp_call_tool",
                "description": "Call a tool by name on a specific MCP server. Provide arguments as an object.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "server": {
                            "type": "string",
                            "enum": ["azure", "filesystem"],
                        },
                        "tool": {"type": "string"},
                        "arguments": {
                            "type": "object",
                            "description": "Key-value arguments for the target tool. Check mcp_list_tools first."
                        },
                    },
                    "required": ["server", "tool", "arguments"],
                },
            },
        },
    ]
