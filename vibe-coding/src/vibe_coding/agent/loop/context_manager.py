"""ContextManager — token-efficient conversation context for AgentLoop.

Responsibilities
----------------
1. **Observation trimming**: keep the last N observations in full; summarise
   older ones with a single LLM call (or heuristic truncation when no LLM
   is available).
2. **File-fingerprint dedup**: remember MD5 of every file read this turn;
   on subsequent reads of the same path, prepend a hint so the LLM skips
   re-reading and uses its memory.
3. **Build user prompt**: assemble goal + context + observations into the
   user-turn string sent each round.
"""

from __future__ import annotations

import hashlib
import textwrap
from typing import Any

from ...nl.llm import LLMClient


_SUMMARISE_SYSTEM = textwrap.dedent("""\
    You are a concise summariser.  Given a sequence of agent-tool observation
    messages, produce a SHORT summary (≤ 300 words) that preserves:
    - Key facts discovered
    - Files modified and what changed
    - Errors encountered and their root-cause if identified
    - Current state / progress

    Respond with ONLY the summary text, no JSON.
""")


class ContextManager:
    """Manages the rolling conversation history for one AgentLoop run.

    Parameters
    ----------
    max_full_observations:
        How many recent observations to keep verbatim. Older ones are
        summarised into a single block.
    max_obs_chars:
        Per-observation character cap before the entry is itself truncated.
    llm:
        Optional LLM client used for summarisation.  When ``None``, falls
        back to a heuristic head+tail truncation.
    """

    def __init__(
        self,
        *,
        max_full_observations: int = 14,
        max_obs_chars: int = 6_000,
        llm: LLMClient | None = None,
    ) -> None:
        self.max_full = max_full_observations
        self.max_obs_chars = max_obs_chars
        self.llm = llm
        self._observations: list[tuple[int, str]] = []   # (step_index, text)
        self._archived_summary: str = ""
        self._file_fingerprints: dict[str, str] = {}     # path → md5 of content

    # ---------------------------------------------------------------- public

    def add_observation(self, step_index: int, text: str) -> None:
        trimmed = _trim_observation(text, self.max_obs_chars)
        self._observations.append((step_index, trimmed))
        if len(self._observations) > self.max_full + 4:
            self._maybe_archive()

    def note_file_read(self, path: str, content: str) -> bool:
        """Record that ``path`` was read.

        Returns ``True`` if this path was already read this run (LLM hint
        should be added); ``False`` for first access.
        """
        fingerprint = hashlib.md5(content.encode("utf-8", errors="replace")).hexdigest()
        was_known = path in self._file_fingerprints
        self._file_fingerprints[path] = fingerprint
        return was_known

    def build_user_prompt(
        self,
        goal: str,
        context: str = "",
        *,
        todo_summary: str = "",
    ) -> str:
        sections: list[str] = [f"## Goal\n{goal.strip()}"]
        if context:
            sections.append(f"## Context\n{context.strip()[:8_000]}")
        if todo_summary:
            sections.append(f"## Current todos\n{todo_summary}")
        if self._archived_summary:
            sections.append(f"## Archived observations (summary)\n{self._archived_summary}")
        recent = self._observations[-self.max_full:]
        for idx, (step_idx, obs) in enumerate(recent):
            sections.append(f"## Observation {step_idx}\n```\n{obs}\n```")
        return "\n\n".join(sections)

    def clear(self) -> None:
        self._observations.clear()
        self._archived_summary = ""
        self._file_fingerprints.clear()

    # ---------------------------------------------------------------- internals

    def _maybe_archive(self) -> None:
        """Archive the oldest observations beyond the full-keep window."""
        overflow = self._observations[: len(self._observations) - self.max_full]
        self._observations = self._observations[-self.max_full:]
        if not overflow:
            return
        combined = "\n---\n".join(
            f"[step {idx}] {obs}" for idx, obs in overflow
        )
        if self.llm is not None:
            try:
                summary = self.llm.chat(
                    _SUMMARISE_SYSTEM,
                    combined[:12_000],
                    json_mode=False,
                )
                summary = summary.strip()[:1_500]
            except Exception:  # noqa: BLE001
                summary = _heuristic_summary(combined)
        else:
            summary = _heuristic_summary(combined)

        if self._archived_summary:
            self._archived_summary = (
                self._archived_summary.rstrip() + "\n\n[later]\n" + summary
            )
        else:
            self._archived_summary = summary


# ---------------------------------------------------------------- helpers


def _trim_observation(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    half = max_chars // 2
    return text[:half] + f"\n... [truncated {len(text) - max_chars} chars] ...\n" + text[-half:]


def _heuristic_summary(combined: str, max_chars: int = 800) -> str:
    lines = combined.splitlines()
    head = "\n".join(lines[:20])
    tail = "\n".join(lines[-20:])
    summary = head
    if tail and tail != head:
        summary += "\n...\n" + tail
    return summary[:max_chars]


__all__ = ["ContextManager"]
