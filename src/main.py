import asyncio, json, logging, requests
from contextlib import AsyncExitStack
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from dotenv import load_dotenv

# Setup logging and load environment variables
logger = logging.getLogger(__name__)
load_dotenv()

# Ollama configuration with llama3
OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL = "llama3"

SYSTEM = """
You are an Azure ops assistant that can call Azure MCP Server tools.

MANDATORY OUTPUT RULES:
- Always output exactly ONE JSON object.
- Never include any text, explanations, or code fences before or after the JSON.
- Do not wrap the JSON in backticks or quotes.
- Do not output more than one JSON object.
- The JSON must be valid and follow the exact structure described below.

WHEN TO CALL A TOOL:
- If the user request needs live Azure data, return:
  {"tool_call":{"name":"<exact tool name from tool_catalog>","arguments":{"command":"<command_name>","parameters":{...}}}}
- If the user request does NOT require a tool, return:
  {"final":{"summary":"<your summary here>"}}

SPECIAL RULES FOR VM METRICS:
1. If metric namespace is unknown, first call:
   {"tool_call":{"name":"monitor","arguments":{"command":"monitor_metrics_definitions","parameters":{"resource":"<vm-name or id>","resource-group":"<rg-name>","resource-type":"Microsoft.Compute/virtualMachines","limit":200}}}}

2. For metric queries, always use:
   name: "monitor"
   command: "monitor_metrics_query"
   parameters: {
       "resource": "<vm-name or full Azure resource ID>",
       "resource-group": "<rg-name>",
       "resource-type": "Microsoft.Compute/virtualMachines",
       "metric-namespace": "Microsoft.Compute/virtualMachines",
       "metric-names": "<comma-separated Azure metric names>",
       "interval": "PT1M",
       "aggregation": "Average"
   }

3. metric-names must be exactly the Azure Monitor names (e.g. "Percentage CPU", "Available Memory Bytes", "Disk Read Bytes", "Disk Write Bytes", "Network In Total", "Network Out Total").
4. metric-names must be a single string, comma-separated (not an array).

DO NOT:
- invent metric names
- change casing or format of metric names
- output snake_case metric names
- output explanations or steps
""".strip()

SUBSCRIPTION_ID = "*************"
DEFAULT_NAMESPACE = "Microsoft.Compute/virtualMachines"
DEFAULT_INTERVAL = "PT1M"
DEFAULT_AGG = "Average"
DEFAULT_METRICS = (
    "Percentage CPU,Available Memory Bytes,Disk Read Bytes,Disk Write Bytes,Network In Total,Network Out Total"
)

def _vm_arm_id(subscription: str, resource_group: str, vm_name: str) -> str:
    return f"/subscriptions/{subscription}/resourceGroups/{resource_group}/providers/Microsoft.Compute/virtualMachines/{vm_name}"

def _ensure_monitor_parameters(tool_name: str, arguments: dict) -> dict:
    """
    Ensure monitor -> monitor_metrics_query has a 'parameters' dict with required keys.
    Non-destructive: only fills what’s missing.
    """
    if tool_name != "monitor":
        return arguments

    command = arguments.get("command")
    if command != "monitor_metrics_query":
        return arguments

    params = dict(arguments.get("parameters") or {})

    # Build full ARM id if only rg/vm given
    if "resource" not in params:
        rg = params.get("resource-group") or arguments.get("resource-group")
        # model might put VM name in 'resource'
        vm_name = params.get("resource") or arguments.get("resource")
        if rg and vm_name and not str(vm_name).startswith("/subscriptions/"):
            params["resource"] = _vm_arm_id(SUBSCRIPTION_ID, rg, vm_name)

    # Required / sensible defaults
    params.setdefault("subscription", SUBSCRIPTION_ID)
    params.setdefault("metric-namespace", DEFAULT_NAMESPACE)
    params.setdefault("metric-names", DEFAULT_METRICS)
    params.setdefault("resource-type", "Microsoft.Compute/virtualMachines")
    params.setdefault("interval", DEFAULT_INTERVAL)
    params.setdefault("aggregation", DEFAULT_AGG)

    # Write back
    new_args = dict(arguments)
    new_args["parameters"] = params
    return new_args

def ask_ollama(messages):
    r = requests.post(
        OLLAMA_URL,
        json={"model": MODEL, "messages": messages, "stream": False,
              "options": {"temperature": 0.2, "num_ctx": 8192}},
        timeout=120
    )
    r.raise_for_status()
    return r.json()["message"]["content"]

async def main():
    params = StdioServerParameters(
        command="npx",
        args=["-y", "@azure/mcp@latest", "server", "start"]
    )

    async with AsyncExitStack() as stack:
        reader, writer = await stack.enter_async_context(stdio_client(params))
        session = await stack.enter_async_context(ClientSession(reader, writer))
        await session.initialize()

        print("Connected to Azure MCP")

        # Tool catalog
        tools = await session.list_tools()
        tool_catalog = [
            {"name": t.name, "description": getattr(t, "description", "") or ""}
            for t in tools.tools
        ]
        print("📦 Tools:", ", ".join(t["name"] for t in tool_catalog) or "(none)")

        # Plain-English prompt
        user_text = input("\nPrompt: ").strip()

        # LLM pass #1
        messages = [
            {"role": "system", "content": SYSTEM},
            {"role": "assistant", "content": json.dumps({"tool_catalog": tool_catalog})},
            {"role": "user", "content": user_text},
        ]
        out = ask_ollama(messages)
        print("\n Model output:\n", out)

        # Try to parse as JSON (single retry if needed)
        try:
            obj = json.loads(out)
        except json.JSONDecodeError:
            messages.append({
                "role": "assistant",
                "content": "Return ONLY the JSON object (either tool_call or final). No extra text."
            })
            out = ask_ollama(messages)
            print("\n Model retry output:\n", out)
            try:
                obj = json.loads(out)
            except json.JSONDecodeError:
                print("Model did not return valid JSON. Raw output:\n", out)
                return

        # Execute tool or print final
        if "tool_call" in obj:
            name = obj["tool_call"]["name"]
            args = obj["tool_call"].get("arguments", {}) or {}

            # 🔧 ADDED: auto-complete monitor_metrics_query parameters
            args = _ensure_monitor_parameters(name, args)
            print("\n🔎 Normalized call:", json.dumps({"name": name, "arguments": args}, indent=2))

            result = await session.call_tool(name, args)
            parts = result.content or []
            rows = [getattr(p, "data", None) or getattr(p, "text", None) for p in parts]
            print("\n Tool result:", rows)
        elif "final" in obj:
            print("\n Final answer:", obj["final"]["summary"])
        else:
            print("Model returned JSON without tool_call or final. JSON was:\n", obj)

if __name__ == "__main__":
    asyncio.run(main())