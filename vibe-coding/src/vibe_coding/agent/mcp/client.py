"""MCP client bridge — exposes external MCP server tools to AgentLoop.

Config format (``mcp_servers.json`` — same as Cursor)
------------------------------------------------------
    {
      "my-server": {
        "command": "npx",
        "args": ["-y", "@my-org/mcp-server"],
        "env": {"API_KEY": "..."}
      }
    }

Usage
-----
    bridge = MCPBridge.from_config("mcp_servers.json")
    bridge.connect_all()       # launches server processes, fetches tool lists
    reg = ToolRegistry()
    bridge.register_tools(reg) # adds one Tool per exposed MCP function
    bridge.close_all()

The bridge uses subprocess stdio JSON-RPC transport (the MCP spec baseline).
Each tool call is a synchronous ``subprocess.communicate`` round-trip so it
works in any thread without an event loop.
"""

from __future__ import annotations

import json
import os
import subprocess
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..react.tools import Tool, ToolRegistry, ToolResult, tool


@dataclass
class MCPServerConfig:
    """One MCP server entry from config."""

    name: str
    command: str
    args: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)


class MCPSession:
    """Manages one running MCP server subprocess."""

    def __init__(self, config: MCPServerConfig) -> None:
        self.config = config
        self._proc: subprocess.Popen | None = None
        self._lock = threading.Lock()
        self._tools: list[dict[str, Any]] = []

    def start(self) -> None:
        env = {**os.environ, **self.config.env}
        cmd = [self.config.command] + list(self.config.args)
        self._proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            env=env,
            text=True,
            encoding="utf-8",
        )
        # MCP initialise handshake
        self._rpc("initialize", {"protocolVersion": "2024-11-05",
                                  "capabilities": {}, "clientInfo": {"name": "vibe-coding", "version": "2"}})
        self._rpc("notifications/initialized", {})
        # Fetch tool list
        resp = self._rpc("tools/list", {})
        self._tools = (resp.get("result") or {}).get("tools") or []

    def tools(self) -> list[dict[str, Any]]:
        return list(self._tools)

    def call_tool(self, tool_name: str, args: dict[str, Any]) -> Any:
        resp = self._rpc("tools/call", {"name": tool_name, "arguments": args})
        result = (resp.get("result") or {})
        content = result.get("content") or []
        texts = [c.get("text", "") for c in content if isinstance(c, dict) and c.get("type") == "text"]
        return "\n".join(texts) or json.dumps(result, ensure_ascii=False)

    def close(self) -> None:
        if self._proc:
            try:
                self._proc.terminate()
                self._proc.wait(timeout=5)
            except Exception:  # noqa: BLE001
                pass
            self._proc = None

    # ---------------------------------------------------------------- helpers

    def _rpc(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        if not self._proc:
            return {}
        msg_id = str(uuid.uuid4())
        payload = json.dumps({"jsonrpc": "2.0", "id": msg_id, "method": method, "params": params})
        with self._lock:
            try:
                assert self._proc.stdin and self._proc.stdout
                self._proc.stdin.write(payload + "\n")
                self._proc.stdin.flush()
                for _ in range(50):   # up to 5s wait
                    line = self._proc.stdout.readline()
                    if not line:
                        time.sleep(0.1)
                        continue
                    try:
                        data = json.loads(line)
                        if str(data.get("id")) == msg_id:
                            return data
                    except (ValueError, KeyError):
                        continue
            except (OSError, BrokenPipeError, AssertionError):
                pass
        return {}


class MCPBridge:
    """Manages multiple MCP server sessions and exposes their tools."""

    def __init__(self, servers: list[MCPServerConfig]) -> None:
        self._configs = servers
        self._sessions: dict[str, MCPSession] = {}

    @classmethod
    def from_config(cls, config_path: str | Path) -> "MCPBridge":
        path = Path(config_path)
        if not path.is_file():
            return cls([])
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return cls([])
        servers: list[MCPServerConfig] = []
        for name, cfg in data.items():
            if not isinstance(cfg, dict):
                continue
            servers.append(MCPServerConfig(
                name=name,
                command=str(cfg.get("command") or ""),
                args=list(cfg.get("args") or []),
                env={str(k): str(v) for k, v in (cfg.get("env") or {}).items()},
            ))
        return cls(servers)

    def connect_all(self) -> None:
        for cfg in self._configs:
            try:
                sess = MCPSession(cfg)
                sess.start()
                self._sessions[cfg.name] = sess
            except Exception:  # noqa: BLE001
                pass

    def register_tools(self, reg: ToolRegistry) -> None:
        for server_name, session in self._sessions.items():
            for tool_def in session.tools():
                t_name = str(tool_def.get("name") or "")
                t_desc = str(tool_def.get("description") or "")
                input_schema = (tool_def.get("inputSchema") or {}).get("properties") or {}
                required_fields = list((tool_def.get("inputSchema") or {}).get("required") or [])
                if not t_name:
                    continue
                # Prefix with server name to avoid collisions
                full_name = f"mcp_{server_name}_{t_name}"
                arguments = [
                    {
                        "name": pname,
                        "type": pdef.get("type", "string"),
                        "required": pname in required_fields,
                        "description": pdef.get("description", ""),
                    }
                    for pname, pdef in input_schema.items()
                    if isinstance(pdef, dict)
                ]

                # Capture for closure
                _sess = session
                _t_name = t_name

                @tool(full_name, description=f"[MCP:{server_name}] {t_desc}", arguments=arguments)
                def _mcp_tool(**kwargs: Any) -> ToolResult:
                    try:
                        output = _sess.call_tool(_t_name, kwargs)
                        return ToolResult(success=True, observation=str(output)[:6_000], output=output)
                    except Exception as exc:  # noqa: BLE001
                        return ToolResult(success=False, observation=f"MCP error: {exc}", error=str(exc))

                try:
                    reg.register(_mcp_tool)
                except ValueError:
                    pass

    def close_all(self) -> None:
        for sess in self._sessions.values():
            sess.close()
        self._sessions.clear()


def load_mcp_servers(config_path: str | Path | None = None) -> MCPBridge:
    """Convenience wrapper: load config, connect, return bridge."""
    if config_path is None:
        # Try standard locations
        for candidate in [
            Path("mcp_servers.json"),
            Path.home() / ".cursor" / "mcp_servers.json",
        ]:
            if candidate.is_file():
                config_path = candidate
                break
    if not config_path:
        return MCPBridge([])
    bridge = MCPBridge.from_config(config_path)
    bridge.connect_all()
    return bridge


__all__ = ["MCPBridge", "MCPServerConfig", "MCPSession", "load_mcp_servers"]
