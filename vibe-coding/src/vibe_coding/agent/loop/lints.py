"""Post-edit lint runner for AgentLoop.

After any write tool (apply_edit, write_file, apply_project_patch) the loop
calls :func:`run_lints_for_paths` to collect diagnostics from available
adapters and returns them as an ``AgentEvent("lints", ...)`` that gets injected
into the next observation window.

The runner is best-effort: if no linters are on PATH it silently returns an
empty result rather than erroring the loop.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..sandbox import SubprocessSandboxDriver
from ..sandbox.driver import SandboxPolicy
from ..tools.runner import ToolAdapter, ToolReport


def run_lints_for_paths(
    paths: list[str],
    root: Path,
    *,
    adapters: list[ToolAdapter] | None = None,
) -> dict[str, Any]:
    """Run lint adapters over ``root`` for the given changed ``paths``.

    Returns a dict:
        {
            "passed": bool,
            "issues": list[str],   # deduplicated issue lines
            "reports": list[{tool, passed, issues}],
        }

    ``paths`` is currently advisory (adapters run on the whole root); it is
    kept in the API for future per-file adapters.
    """
    if adapters is None:
        adapters = _default_post_edit_adapters()

    sandbox = SubprocessSandboxDriver()
    policy = SandboxPolicy(timeout_s=30, max_output_size=50_000)

    reports_out: list[dict[str, Any]] = []
    all_issues: list[str] = []
    all_passed = True

    for adapter in adapters:
        if not adapter.is_available():
            continue
        try:
            report: ToolReport = adapter.run(root, sandbox=sandbox, policy=policy)
        except Exception as exc:  # noqa: BLE001
            report = ToolReport(
                tool=getattr(adapter, "name", "?"),
                passed=False,
                error=f"{type(exc).__name__}: {exc}",
            )
        reports_out.append({
            "tool": report.tool,
            "passed": report.passed,
            "issues": list(report.issues[:20]),
            "error": report.error,
        })
        if not report.passed:
            all_passed = False
            all_issues.extend(report.issues[:20])

    # deduplicate keeping order
    seen: set[str] = set()
    deduped: list[str] = []
    for issue in all_issues:
        if issue not in seen:
            seen.add(issue)
            deduped.append(issue)

    return {
        "passed": all_passed,
        "issues": deduped[:40],
        "reports": reports_out,
    }


def format_lint_observation(lint_result: dict[str, Any]) -> str:
    """Format lint result as a concise observation string for the LLM."""
    if lint_result.get("passed"):
        return "[lints] all checks passed after edit"
    issues = lint_result.get("issues") or []
    if not issues:
        return "[lints] checks failed (no specific issues returned)"
    header = f"[lints] {len(issues)} issue(s) after edit — please fix:\n"
    lines = "\n".join(f"  {i}" for i in issues[:20])
    return header + lines


def _default_post_edit_adapters() -> list[ToolAdapter]:
    """Return adapters that are cheap to run post-edit."""
    adapters: list[ToolAdapter] = []
    try:
        from ..tools.adapters.ruff import RuffAdapter
        adapters.append(RuffAdapter(format_check=False))
    except ImportError:
        pass
    try:
        from ..tools.adapters.eslint import ESLintAdapter
        adapters.append(ESLintAdapter())
    except ImportError:
        pass
    return adapters


__all__ = ["run_lints_for_paths", "format_lint_observation"]
