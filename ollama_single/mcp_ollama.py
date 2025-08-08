# mcp_ollama_demo.py
import asyncio, json
from contextlib import AsyncExitStack
from typing import Any, Dict, List, Optional

import ollama
from mcp import ClientSession, StdioServerParameters, types
from mcp.client.stdio import stdio_client

AZURE_CMD = "npx"
AZURE_ARGS = ["-y", "@azure/mcp@latest", "server", "start"]
FS_CMD = "npx"
FS_ARGS = ["-y", "@modelcontextprotocol/server-filesystem", "."]  # current dir
MODEL = "llama3.1:8b"

SYSTEM_PROMPT = """You are an AI assistant with access to two MCP servers: 'azure' and 'filesystem'.
Use mcp_list_tools to discover tools and mcp_call_tool to invoke them.
Be concise and explain what you did."""

def build_tools():
    return [
        {"type":"function","function":{
            "name":"mcp_list_tools",
            "description":"List available MCP tools. Optional server filter.",
            "parameters":{"type":"object","properties":{
                "server":{"type":"string","enum":["azure","filesystem"]}}}}},
        {"type":"function","function":{
            "name":"mcp_call_tool",
            "description":"Call a tool on a server with arguments object.",
            "parameters":{"type":"object","properties":{
                "server":{"type":"string","enum":["azure","filesystem"]},
                "tool":{"type":"string"},
                "arguments":{"type":"object"},"required":["server","tool","arguments"]}}}}
    ]

class MCP:
    def __init__(self): self.sessions={}
    async def __aenter__(self):
        self.stack = AsyncExitStack()
        az = StdioServerParameters(command=AZURE_CMD,args=AZURE_ARGS)
        fs = StdioServerParameters(command=FS_CMD,args=FS_ARGS)
        # Azure
        az_r, az_w = await self.stack.enter_async_context(stdio_client(az))
        az_sess = await self.stack.enter_async_context(ClientSession(az_r, az_w)); await az_sess.initialize()
        self.sessions["azure"]=az_sess
        # FS
        fs_r, fs_w = await self.stack.enter_async_context(stdio_client(fs))
        fs_sess = await self.stack.enter_async_context(ClientSession(fs_r, fs_w)); await fs_sess.initialize()
        self.sessions["filesystem"]=fs_sess
        return self
    async def __aexit__(self, *a): await self.stack.aclose()
    async def list_tools(self, server: Optional[str]=None):
        out={}
        for name, sess in self.sessions.items():
            if server and name!=server: continue
            tools = await sess.list_tools()
            out[name]=[{"name":t.name,"description":getattr(t,"description","")} for t in tools.tools]
        return out
    async def call(self, server:str, tool:str, args:Dict[str,Any]):
        sess=self.sessions[server]
        res=await sess.call_tool(tool, arguments=args or {})
        if getattr(res,"structuredContent",None) is not None:
            return json.dumps(res.structuredContent, ensure_ascii=False, indent=2)
        parts=[]
        for c in res.content:
            if isinstance(c, types.TextContent): parts.append(c.text)
            else: parts.append(str(c))
        return "\n".join(parts)

async def ollama_chat(messages, tools):
    def _call():
        return ollama.chat(model=MODEL, messages=messages, tools=tools, options={"temperature":0.2})
    return await asyncio.to_thread(_call)

async def main():
    tools_schema = build_tools()
    messages=[{"role":"system","content":SYSTEM_PROMPT}]
    async with MCP() as mcp:
        print("=== MCP tools discovered ===")
        idx=await mcp.list_tools()
        for s, ts in idx.items():
            print(f"[{s}]")
            for t in ts: print("  •", t["name"], "-", t.get("description",""))
        print("\nType 'quit' to exit.\n")
        while True:
            user=input("> ").strip()
            if user.lower() in {"quit","exit"}: break
            if not user: continue
            messages.append({"role":"user","content":user})
            # first round
            resp=await ollama_chat(messages, tools_schema)
            msg=resp.get("message",{})
            tool_calls=msg.get("tool_calls",[]) or []
            if msg.get("content"): print("\n"+msg["content"])
            while tool_calls:
                for call in tool_calls:
                    name=call.get("function",{}).get("name")
                    args=call.get("function",{}).get("arguments") or {}
                    if name=="mcp_list_tools":
                        server=args.get("server")
                        result=await mcp.list_tools(server)
                        out=json.dumps(result, ensure_ascii=False, indent=2)
                    elif name=="mcp_call_tool":
                        server=args.get("server"); tool=args.get("tool"); a=args.get("arguments") or {}
                        if not server or not tool: out="Error: need server + tool"
                        else:
                            try: out=await mcp.call(server, tool, a)
                            except Exception as e: out=f"Error: {e}"
                    else:
                        out=f"Unknown tool: {name}"
                    messages.append({"role":"tool","name":name,"content":out})
                resp=await ollama_chat(messages, tools_schema)
                msg=resp.get("message",{})
                if msg.get("content"): print(msg["content"])
                tool_calls=msg.get("tool_calls",[]) or []
            messages.append({"role":"assistant","content":msg.get("content","")})
            print()

if __name__=="__main__":
    asyncio.run(main())
