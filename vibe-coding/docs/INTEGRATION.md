# Integration Guide

How to drop `vibe_coding` into another project without touching its existing
architecture.

## As a path dependency

Most clean approach for sibling projects:

```toml
# pyproject.toml of the consumer
[project]
dependencies = [
    "vibe-coding @ file:../vibe-coding",
]
```

Then:

```bash
pip install -e .
```

The consumer codebase imports from `vibe_coding` as if it were any third-party
library; no source files need to be copied.

## As a vendored copy

If the consumer cannot tolerate an external path:

```bash
cp -r vibe-coding/src/vibe_coding consumer/lib/vibe_coding
```

Then `from lib.vibe_coding import VibeCoder, MockLLM, ...` (adjust import
roots to taste). When upstream evolves, repeat the copy and run the
consumer's tests.

## With MODstore (or any FastAPI / Django service)

Pattern: keep the consumer's existing skill registry / runtime, *and* expose
a thin endpoint that delegates code-layer work to vibe-coding.

```python
# consumer_service/vibe_routes.py
from fastapi import APIRouter
from vibe_coding import VibeCoder, OpenAILLM

router = APIRouter(prefix="/api/vibe", tags=["vibe-coding"])

_coder = VibeCoder(
    llm=OpenAILLM(api_key=settings.openai_key),
    store_dir=settings.vibe_store_dir,
)

@router.post("/code")
def make_code_skill(brief: str):
    skill = _coder.code(brief)
    return {"skill_id": skill.skill_id, "active_version": skill.active_version}

@router.post("/workflow")
def make_workflow(brief: str):
    return _coder.workflow_with_report(brief).graph.to_dict()

@router.post("/run/{skill_id}")
def run(skill_id: str, payload: dict):
    return _coder.run(skill_id, payload).to_dict()

@router.post("/rollback/{skill_id}/{version}")
def rollback(skill_id: str, version: int):
    skill = _coder.rollback(skill_id, version)
    return {"skill_id": skill.skill_id, "active_version": skill.active_version}
```

The consumer's existing workflow engine remains the source of truth for
business workflows; vibe-coding only owns the *generated* code-layer skills
plus their per-skill self-healing loop. If the consumer wants to consume the
generated workflow as well, call `coder.workflow(brief)` and translate the
returned `VibeWorkflowGraph` into the consumer's own node model.

## Choosing between standalone and upstream

- **Standalone**: simpler dependency surface; code-layer only; ideal for
  research / prototypes / consumers that don't need the full eskill double-
  layer architecture.
- **Upstream `eskill.vibe_coding`**: same NL feature set plus config-layer
  (`ESkill`) integration, dual-layer `ESkillNodeWrapper`, and the full eskill
  audit / strategy stack. Pick this when you want every Skill node in your
  workflow to participate in the existing eskill self-healing ecosystem.

You can run both simultaneously: `eskill.vibe_coding.VibeCoder` for the
production tree, `vibe_coding.VibeCoder` (this package) as a sandbox to
research alternative prompts / retry strategies / patch generators without
touching production.
