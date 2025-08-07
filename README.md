# Azure MCP VM Diagnostics

This project explores how to leverage the [Azure MCP Server](https://github.com/Azure/azure-mcp) in combination with GitHub Copilot Agent to monitor and troubleshoot Azure Virtual Machines.

## 🔍 Objective

The goal is to build a natural language-driven diagnostics solution that can:

- Use **GitHub Copilot Agent** to issue diagnostic and monitoring queries
- Leverage **Azure’s hosted MCP server** to interact with Azure resources
- Collect and analyze **VM diagnostics and performance data**
- Trigger appropriate actions based on findings (e.g., high CPU, failed boot, etc.)

## 🧠 Architecture Overview

- **MCP Server**: Azure-hosted MCP server for handling model-context interactions
- **Copilot Agent**: Acts as the MCP client, sending prompts and receiving structured responses
- **Python**: Main scripting language for local tooling and extensions
- **Ollama (optional)**: Used as an on-device NLP engine to translate natural language to CLI/KQL commands (exploration in progress)

## ⚙️ Tech Stack

- Azure CLI & Monitor
- Azure MCP Server
- GitHub Copilot Agent (Agent Mode in VS Code)
- Python 3.12.6
- Ollama (for local LLM experimentation)
- KQL (for querying Azure Monitor / Log Analytics)

## 🚧 Status

This is a **hobby project** aimed at deepening understanding of:
- Azure’s MCP architecture
- Copilot’s agent mode
- AI-assisted diagnostics in cloud infrastructure

Expect frequent updates as the project evolves.

## 👤 Contributor

- **Suhail Nepal**
- **Jonathan Mason**