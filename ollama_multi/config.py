from pathlib import Path

# Ollama model config
OLLAMA_MODEL = "llama3.1:8b"
OLLAMA_URL = "http://localhost:11434"  # default

# Filesystem MCP - which directories are allowed
# You can add more than one
FS_ALLOWED_DIRS = [str(Path.cwd())]  # current working dir by default

# Azure MCP command and args (stdio)
AZURE_MCP_CMD = "npx"
AZURE_MCP_ARGS = ["-y", "@azure/mcp@latest", "server", "start"]

# Filesystem MCP command and args (stdio)
FS_MCP_CMD = "npx"
FS_MCP_ARGS = ["-y", "@modelcontextprotocol/server-filesystem", *FS_ALLOWED_DIRS]

# History file and how many messages to keep
HISTORY_PATH = Path(".mcp_ollama_history.json")
HISTORY_MAX_TURNS = 30  # user+assistant+tool turns, roughly
