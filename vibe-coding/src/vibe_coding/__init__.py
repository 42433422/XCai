"""Standalone vibe-coding: NL → sandbox-validated, self-healing Python skills + workflows.

This package is the standalone twin of ``eskill.vibe_coding``. It carries its
own runtime / sandbox / validator / patch-generator (in :mod:`vibe_coding.runtime`)
copied from the upstream eskill prototype, plus the natural-language layer
(``code_factory``, ``workflow_factory``, ``facade``, …) so it can be installed
and used in any project without a dependency on the ``eskill`` package.

If upstream evolves, run ``python scripts/sync_from_eskill.py`` to refresh the
generated pieces (``runtime/``, ``nl/``, the factories, ``workflow_models``).
``audit.py``, ``facade.py``, ``cli.py``, ``workflow_engine.py`` and this
``__init__`` are hand-maintained because they intentionally drop the config-
layer ``ESkillRuntime`` integration that exists upstream.
"""

from __future__ import annotations

from ._version import __version__
from .audit import PatchLedger, PatchRecord
from .code_factory import NLCodeSkillFactory, VibeCodingError
from .facade import VibeCoder
from .nl.llm import LLMClient, LLMError, MockLLM, OpenAILLM
from .nl.prompts import (
    BRIEF_FIRST_CODE_PROMPT,
    BRIEF_FIRST_SPEC_PROMPT,
    CODE_DIRECT_PROMPT,
    CODE_REPAIR_PROMPT,
    WORKFLOW_PROMPT,
)
from .workflow_engine import VibeWorkflowEngine, WorkflowRunResult
from .workflow_factory import NLWorkflowFactory, WorkflowGenerationReport
from .workflow_models import VibeWorkflowEdge, VibeWorkflowGraph, VibeWorkflowNode

__all__ = [
    "BRIEF_FIRST_CODE_PROMPT",
    "BRIEF_FIRST_SPEC_PROMPT",
    "CODE_DIRECT_PROMPT",
    "CODE_REPAIR_PROMPT",
    "LLMClient",
    "LLMError",
    "MockLLM",
    "NLCodeSkillFactory",
    "NLWorkflowFactory",
    "OpenAILLM",
    "PatchLedger",
    "PatchRecord",
    "VibeCoder",
    "VibeCodingError",
    "VibeWorkflowEdge",
    "VibeWorkflowEngine",
    "VibeWorkflowGraph",
    "VibeWorkflowNode",
    "WORKFLOW_PROMPT",
    "WorkflowGenerationReport",
    "WorkflowRunResult",
    "__version__",
]
