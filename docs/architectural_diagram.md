+-------------------+         HTTP(S)          +------------------------+
|                   |  /api/chat (LLM calls)   |                        |
|     Ollama        |<------------------------>|  Your Agent (Python)   |
|   (local model)   |                          |  - REPL / UI           |
|                   |                          |  - Planner (intent)    |
+-------------------+                          |  - MCP Tool Caller     |
                                               +-----------+------------+
                                                           |
                                                           | HTTP(S) + (x-api-key)
                                                           v
                                               +------------------------+
                                               |  Azure MCP Server      |
                                               |  (hosted by Microsoft) |
                                               |  - Tool catalog        |
                                               |  - Tool execution      |
                                               +-----------+------------+
                                                           |
                                                           | Azure auth / RBAC
                                                           v
                                               +------------------------+
                                               |  Azure Services        |
                                               |  - Log Analytics (KQL) |
                                               |  - Monitor Metrics     |
                                               |  - Resource Graph      |
                                               +------------------------+