"""Function-calling adapter for AgentLoop.

Adds native tool-calling support for OpenAI / Claude / Qwen-compatible LLMs
while keeping a JSON-mode fallback for everything else.

Architecture
------------
The adapter wraps any :class:`vibe_coding.nl.LLMClient` and exposes a single
``chat_with_tools`` method that:

1. Detects whether the underlying client supports native function-calling
   (via the optional ``chat_with_tools`` method or provider heuristics).
2. For capable providers: sends the tools schema in the OpenAI ``tools=``
   format; parses the response into :class:`ToolCallRequest` objects.
3. For all others: falls back to the existing JSON-mode ReAct format
   (``{"thought": ..., "action": {"tool": ..., "args": {...}}, "final_answer": ...}``).

Either path produces the same output type so the caller (``AgentLoop``) is
provider-agnostic.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any

from ...nl.llm import LLMClient, LLMError
from ...nl.parsing import JSONParseError, safe_parse_json_object
from ..react.tools import ToolRegistry


# ---------------------------------------------------------------- types

@dataclass(slots=True)
class ToolCallRequest:
    """A single tool invocation requested by the LLM."""

    tool: str
    args: dict[str, Any] = field(default_factory=dict)
    call_id: str = ""          # provider-assigned call id (OpenAI style)
    thought: str = ""          # reasoning text (from ReAct JSON or <thinking>)


@dataclass(slots=True)
class LLMTurn:
    """Result of one LLM round-trip.

    Either ``tool_calls`` is non-empty (continue loop) or ``final_answer``
    is non-empty (finish).  Never both.
    """

    tool_calls: list[ToolCallRequest] = field(default_factory=list)
    final_answer: str = ""
    thought: str = ""
    raw: str = ""
    parse_error: str = ""
    duration_ms: float = 0.0


# ---------------------------------------------------------------- adapter


_REACT_FORMAT_HINT = """\
Respond with a single JSON object — no markdown fences:

{
  "thought": "<your reasoning>",
  "action": {
    "tool": "<tool_name or empty string to finish>",
    "args": {"<param>": "<value>"}
  },
  "final_answer": "<non-empty only when done, otherwise empty>"
}
"""

_MULTI_TOOL_HINT = """\
You MAY request multiple read-only tools in one turn by returning a JSON array
instead of a single object:

[
  {"thought": "...", "action": {"tool": "tool_a", "args": {...}}, "final_answer": ""},
  {"thought": "...", "action": {"tool": "tool_b", "args": {...}}, "final_answer": ""}
]

Use this ONLY for tools that are independent and read-only (grep, read_file,
glob_files, find_symbol, …). Write tools must be requested one at a time.
"""


class FunctionCallingAdapter:
    """Wraps an LLMClient to add tool-calling capabilities.

    Parameters
    ----------
    llm:
        Any ``LLMClient`` (mock, OpenAI, Qwen, Claude, …).
    registry:
        The ``ToolRegistry`` whose schema will be sent to the LLM.
    allow_parallel:
        Whether to instruct the LLM it may batch read-only tool calls.
        Defaults to ``True``; set ``False`` for strict one-at-a-time mode.
    native_tools:
        If ``None`` (default), capability is auto-detected from the
        LLM's optional ``chat_with_tools`` method.  Pass ``True`` / ``False``
        to override.
    """

    def __init__(
        self,
        llm: LLMClient,
        registry: ToolRegistry,
        *,
        allow_parallel: bool = True,
        native_tools: bool | None = None,
    ) -> None:
        self.llm = llm
        self.registry = registry
        self.allow_parallel = allow_parallel
        # Native tool-calling: use provider method if available.
        if native_tools is None:
            self._use_native = callable(getattr(llm, "chat_with_tools", None))
        else:
            self._use_native = native_tools

    # ---------------------------------------------------------------- public

    def build_system_addendum(self) -> str:
        """Return tool schema + format instructions to append to system prompt."""
        if self._use_native:
            return ""   # schema injected via tools= parameter
        parts = ["## Tools\n\n" + self.registry.to_prompt_schema()]
        parts.append(_REACT_FORMAT_HINT)
        if self.allow_parallel:
            parts.append(_MULTI_TOOL_HINT)
        return "\n\n".join(parts)

    def call(
        self,
        system: str,
        user: str,
        *,
        max_steps: int = 20,
    ) -> LLMTurn:
        """One LLM round-trip, returning normalised ``LLMTurn``."""
        t0 = time.perf_counter()
        if self._use_native:
            result = self._call_native(system, user)
        else:
            result = self._call_json(system, user)
        result.duration_ms = round((time.perf_counter() - t0) * 1000, 3)
        return result

    # ---------------------------------------------------------------- native

    def _call_native(self, system: str, user: str) -> LLMTurn:
        """Use provider-native ``chat_with_tools`` when available."""
        tools_schema = _build_openai_tools_schema(self.registry)
        try:
            # ``chat_with_tools`` returns (content, tool_calls_list)
            content, tool_calls_raw = self.llm.chat_with_tools(  # type: ignore[attr-defined]
                system, user, tools=tools_schema
            )
        except (AttributeError, TypeError):
            # Fallback if the method signature doesn't match
            return self._call_json(system, user)
        except LLMError as exc:
            return LLMTurn(parse_error=str(exc))

        if tool_calls_raw:
            calls = []
            for tc in tool_calls_raw:
                name = tc.get("function", {}).get("name") or tc.get("name") or ""
                raw_args = tc.get("function", {}).get("arguments") or tc.get("arguments") or {}
                if isinstance(raw_args, str):
                    try:
                        raw_args = json.loads(raw_args)
                    except (TypeError, ValueError):
                        raw_args = {}
                calls.append(
                    ToolCallRequest(
                        tool=name,
                        args=raw_args if isinstance(raw_args, dict) else {},
                        call_id=tc.get("id") or "",
                    )
                )
            return LLMTurn(tool_calls=calls, raw=str(content or ""))
        return LLMTurn(final_answer=str(content or "").strip(), raw=str(content or ""))

    # ---------------------------------------------------------------- JSON

    def _call_json(self, system: str, user: str) -> LLMTurn:
        """JSON-mode ReAct format — works with any provider."""
        try:
            raw = self.llm.chat(system, user, json_mode=True)
        except LLMError as exc:
            return LLMTurn(parse_error=f"llm_error: {exc}")

        # Try to parse as array (multi-tool batch)
        stripped = raw.strip()
        if stripped.startswith("["):
            return self._parse_multi(raw)
        return self._parse_single(raw)

    def _parse_single(self, raw: str) -> LLMTurn:
        try:
            payload = safe_parse_json_object(raw)
        except JSONParseError as exc:
            return LLMTurn(parse_error=f"json_parse: {exc}", raw=raw)

        thought = str(payload.get("thought") or "")
        action = payload.get("action") or {}
        tool_name = ""
        args: dict[str, Any] = {}
        if isinstance(action, dict):
            tool_name = str(action.get("tool") or "")
            raw_args = action.get("args") or {}
            if isinstance(raw_args, dict):
                args = raw_args
        final_answer = str(payload.get("final_answer") or "").strip()

        if final_answer or not tool_name:
            return LLMTurn(
                final_answer=final_answer or "(no answer)",
                thought=thought,
                raw=raw,
            )
        return LLMTurn(
            tool_calls=[ToolCallRequest(tool=tool_name, args=args, thought=thought)],
            thought=thought,
            raw=raw,
        )

    def _parse_multi(self, raw: str) -> LLMTurn:
        """Parse array form ``[{thought, action}, ...]``."""
        try:
            import json as _json
            items = _json.loads(raw)
            if not isinstance(items, list):
                return self._parse_single(raw)
        except (TypeError, ValueError):
            return self._parse_single(raw)

        calls: list[ToolCallRequest] = []
        thought_parts: list[str] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            fa = str(item.get("final_answer") or "").strip()
            if fa:
                return LLMTurn(final_answer=fa, raw=raw)
            thought = str(item.get("thought") or "")
            if thought:
                thought_parts.append(thought)
            action = item.get("action") or {}
            tool_name = str(action.get("tool") or "") if isinstance(action, dict) else ""
            raw_args = action.get("args") or {} if isinstance(action, dict) else {}
            if not isinstance(raw_args, dict):
                raw_args = {}
            if tool_name:
                calls.append(ToolCallRequest(tool=tool_name, args=raw_args, thought=thought))

        if not calls:
            return self._parse_single(raw)
        return LLMTurn(
            tool_calls=calls,
            thought=" | ".join(thought_parts),
            raw=raw,
        )


# ---------------------------------------------------------------- helpers


def _build_openai_tools_schema(registry: ToolRegistry) -> list[dict[str, Any]]:
    """Convert ToolRegistry to OpenAI-compatible ``tools`` list."""
    out: list[dict[str, Any]] = []
    seen: set[int] = set()
    for t in registry:
        if id(t) in seen:
            continue
        seen.add(id(t))
        properties: dict[str, Any] = {}
        required: list[str] = []
        for arg in t.arguments:
            name = arg["name"]
            typ = arg.get("type", "string")
            # Map our type strings to JSON Schema types
            json_type = _to_json_schema_type(typ)
            properties[name] = {
                "type": json_type,
                "description": arg.get("description", ""),
            }
            if arg.get("required", True):
                required.append(name)
        out.append({
            "type": "function",
            "function": {
                "name": t.name,
                "description": t.description.strip(),
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                },
            },
        })
    return out


def _to_json_schema_type(vibe_type: str) -> str:
    mapping = {
        "string": "string",
        "integer": "integer",
        "number": "number",
        "boolean": "boolean",
        "array": "array",
        "object": "object",
    }
    return mapping.get(vibe_type, "string")


__all__ = [
    "FunctionCallingAdapter",
    "LLMTurn",
    "ToolCallRequest",
    "_build_openai_tools_schema",
]
