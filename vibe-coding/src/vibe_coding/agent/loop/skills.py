"""Skills loader for AgentLoop.

Skills live in ``store_dir/skills/<name>/SKILL.md`` (or ``SKILL.md`` in any
subdir of ``store_dir/skills/``).

The file format mirrors Cursor skills:

    ---
    description: "One-sentence summary shown in system prompt"
    ---

    # Full skill instructions …

When ``AgentLoop`` initialises it reads **only** the front-matter description
of every skill and appends a brief index to the system prompt.  The full body
is loaded lazily when the LLM calls ``read_skill(name)``.

This keeps the base system prompt small regardless of how many skills are
installed.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..react.tools import Tool, ToolResult, tool


@dataclass
class SkillMeta:
    """Lightweight skill descriptor (front-matter only)."""

    name: str                  # directory / file stem
    description: str
    path: Path


class SkillsLoader:
    """Discovers and lazily loads skills from the filesystem."""

    def __init__(self, skills_dir: Path | str | None = None) -> None:
        self._dir = Path(skills_dir).resolve() if skills_dir else None
        self._cache: dict[str, SkillMeta] = {}
        self._body_cache: dict[str, str] = {}

    def discover(self) -> list[SkillMeta]:
        """Walk skills_dir and return lightweight metadata for each skill."""
        if not self._dir or not self._dir.is_dir():
            return []
        skills: list[SkillMeta] = []
        for skill_file in sorted(self._dir.rglob("SKILL.md")):
            name = skill_file.parent.name
            try:
                text = skill_file.read_text(encoding="utf-8")
            except OSError:
                continue
            desc = _extract_description(text)
            if not desc:
                continue
            meta = SkillMeta(name=name, description=desc, path=skill_file)
            self._cache[name] = meta
            skills.append(meta)
        return skills

    def get_body(self, name: str) -> str | None:
        if name in self._body_cache:
            return self._body_cache[name]
        meta = self._cache.get(name)
        if meta is None:
            # Try to find by name
            self.discover()
            meta = self._cache.get(name)
        if meta is None:
            return None
        try:
            body = meta.path.read_text(encoding="utf-8")
            self._body_cache[name] = body
            return body
        except OSError:
            return None

    def system_index(self) -> str:
        """One-line-per-skill index for the system prompt."""
        skills = self.discover()
        if not skills:
            return ""
        lines = ["## Available Skills\n"]
        for s in skills:
            lines.append(f"- **{s.name}**: {s.description}")
        lines.append("\nCall `read_skill(name=...)` to load full skill instructions.")
        return "\n".join(lines)

    def make_tool(self) -> Tool:
        loader = self

        @tool(
            "read_skill",
            description="Load and return the full instructions for a named skill.",
        )
        def read_skill(name: str) -> ToolResult:
            body = loader.get_body(name)
            if body is None:
                available = [s.name for s in loader.discover()]
                return ToolResult(
                    success=False,
                    observation=f"skill '{name}' not found. Available: {available}",
                    error="not_found",
                )
            return ToolResult(
                success=True,
                observation=body[:8_000],
                output={"name": name, "content": body},
            )

        return read_skill


# ---------------------------------------------------------------- helpers

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---", re.DOTALL)
_DESC_RE = re.compile(r'^description\s*[:=]\s*["\']?(.*?)["\']?\s*$', re.MULTILINE)


def _extract_description(text: str) -> str:
    fm_match = _FRONTMATTER_RE.match(text.lstrip())
    if fm_match:
        fm = fm_match.group(1)
        m = _DESC_RE.search(fm)
        if m:
            return m.group(1).strip()
    # Fallback: first non-empty line after #
    for line in text.splitlines():
        line = line.strip()
        if line and not line.startswith("#") and not line.startswith("---"):
            return line[:120]
    return ""


__all__ = ["SkillMeta", "SkillsLoader"]
