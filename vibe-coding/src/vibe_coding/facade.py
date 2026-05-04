"""VibeCoder for the standalone (code-layer only) build.

Differences from the upstream ``eskill.vibe_coding.facade.VibeCoder``:

- Drops the config-layer (``ESkill`` / ``ESkillRuntime`` / ``JsonSkillStore``)
  pieces because the standalone tree does not vendor those modules.
- ``code()`` / ``run()`` / ``execute()`` / ``history()`` / ``rollback()`` /
  ``report()`` work identically.
- ``config_skill()`` raises ``NotImplementedError``; install the upstream
  ``eskill`` package if you need it, or extend this facade.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ._internals import CodeSkill, CodeSkillRun
from .audit import PatchLedger, PatchRecord
from .code_factory import GenerationMode, NLCodeSkillFactory
from .nl.llm import LLMClient
from .runtime import (
    CodeSkillRuntime,
    JsonCodeSkillStore,
    OpenAICodePatchGenerator,
    RuleBasedCodePatchGenerator,
)
from .workflow_engine import VibeWorkflowEngine, WorkflowRunResult
from .workflow_factory import NLWorkflowFactory, WorkflowGenerationReport
from .workflow_models import VibeWorkflowGraph


class VibeCoder:
    """High-level facade for the standalone code-layer flow."""

    def __init__(
        self,
        *,
        llm: LLMClient,
        store_dir: str | Path = "./vibe_coding_data",
        llm_for_repair: bool = True,
        code_runtime: CodeSkillRuntime | None = None,
    ):
        self.llm = llm
        self.store_dir = Path(store_dir)
        self.store_dir.mkdir(parents=True, exist_ok=True)

        self.code_store = JsonCodeSkillStore(self.store_dir / "code_skill_store.json")
        self.code_factory = NLCodeSkillFactory(llm, self.code_store)
        self.workflow_factory = NLWorkflowFactory(llm, self.code_factory)

        self.code_runtime = code_runtime or CodeSkillRuntime(
            self.code_store,
            llm_generator=_build_code_patch_generator(llm) if llm_for_repair else None,
        )
        self.engine = VibeWorkflowEngine(code_runtime=self.code_runtime)
        self.ledger = PatchLedger(code_store=self.code_store)

    # ------------------------------------------------------------------ generation

    def code(
        self,
        brief: str,
        *,
        mode: GenerationMode = "brief_first",
        skill_id: str | None = None,
        dependencies: list[str] | None = None,
    ) -> CodeSkill:
        return self.code_factory.generate(
            brief, mode=mode, skill_id=skill_id, dependencies=dependencies
        )

    def config_skill(self, brief: str, *, skill_id: str | None = None) -> Any:
        raise NotImplementedError(
            "Standalone vibe_coding is code-layer only. Use the upstream eskill.vibe_coding "
            "package for config-layer (template_transform / employee_task / pipeline) skills."
        )

    def workflow(self, brief: str) -> VibeWorkflowGraph:
        return self.workflow_factory.generate(brief)

    def workflow_with_report(self, brief: str) -> WorkflowGenerationReport:
        return self.workflow_factory.generate_with_report(brief)

    # ------------------------------------------------------------------ execution

    def run(self, skill_id: str, input_data: dict[str, Any]) -> CodeSkillRun:
        return self.code_runtime.run(skill_id, input_data)

    def execute(self, graph: VibeWorkflowGraph, input_data: dict[str, Any]) -> WorkflowRunResult:
        return self.engine.run(graph, input_data)

    # ------------------------------------------------------------------ audit

    def history(self, skill_id: str) -> list[PatchRecord]:
        return self.ledger.history(skill_id)

    def evolution_chain(self, skill_id: str) -> list[dict[str, Any]]:
        return self.ledger.evolution_chain(skill_id)

    def rollback(self, skill_id: str, target_version: int) -> CodeSkill:
        return self.ledger.rollback(skill_id, target_version)

    def report(self, skill_id: str | None = None) -> dict[str, Any]:
        return self.ledger.report(skill_id)

    # ------------------------------------------------------------------ list

    def list_code_skills(self) -> list[CodeSkill]:
        return self.code_store.list_code_skills()


def _build_code_patch_generator(llm: LLMClient):
    try:
        from .nl.llm import OpenAILLM

        if isinstance(llm, OpenAILLM):
            return OpenAICodePatchGenerator(api_key=llm.api_key, model=llm.model, base_url=llm.base_url)
    except Exception:  # noqa: BLE001
        pass
    return RuleBasedCodePatchGenerator()
