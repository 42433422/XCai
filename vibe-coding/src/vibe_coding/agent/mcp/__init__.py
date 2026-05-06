"""MCP (Model Context Protocol) client for vibe-coding AgentLoop.

Discovers external MCP servers from a JSON config file (same format as
Cursor's ``mcp_servers.json``) and registers their tools into a
:class:`ToolRegistry` so the LLM can call them transparently.
"""

from .client import MCPBridge, MCPServerConfig, load_mcp_servers

__all__ = ["MCPBridge", "MCPServerConfig", "load_mcp_servers"]
