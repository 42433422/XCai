# vibe-coding

> **Standalone, self-contained Python package** that lets you turn any natural-
> language brief into a sandbox-validated, self-healing Python skill — and
> compose multiple skills into a complete workflow.

This package is the standalone twin of [`eskill.vibe_coding`](../eskill-prototype/src/eskill/vibe_coding)
inside the `eskill-prototype` project. The two stay in sync via the
`scripts/sync_from_eskill.py` helper, but `vibe-coding/` has zero dependency
on the `eskill` package — it carries all the runtime / sandbox / validator
machinery it needs in `src/vibe_coding/runtime/` so you can drop it into any
project (or copy the folder, branch off, and research alternative architectures
without touching the production tree).

## Install

```bash
cd vibe-coding
pip install -e ".[llm,test]"
```

## 30-second tour

```python
from vibe_coding import VibeCoder, MockLLM

coder = VibeCoder(llm=MockLLM([...]), store_dir="./data")

skill  = coder.code("把字符串反转")        # CodeSkill (sandbox-validated)
graph  = coder.workflow("天气查询员工 + 穿衣建议")  # multi-skill workflow
result = coder.execute(graph, {"city": "Beijing"})

coder.history(skill.skill_id)              # patch trail
coder.rollback(skill.skill_id, 1)          # one-click rollback
coder.report()                             # cross-skill health
```

In production, swap `MockLLM` for `OpenAILLM(api_key=...)`.

## Differentiators vs. Trae and other AI IDEs

- Generated code passes the sandbox + every test case **before** you receive it
- Runtime failures auto-diagnose, AST-validate, sandbox-verify, then solidify a new version
- Strict import whitelist + forbidden-builtin AST guards (no `eval` / `exec` / `open`)
- Version history with one-call rollback (`PatchLedger`)
- Config layer + code layer coexist
- True end-to-end "AI-generated workflow": one brief → multi-node graph + all skills built and verified
- Domain guard rejects out-of-scope inputs from polluting LLM repair chains
- Brief-first two-step generation produces sharper code than single-shot

See `docs/P0_P1_CHECKLIST.md` for the full comparison.

## Layout

```
vibe-coding/
├── src/vibe_coding/
│   ├── _internals/    # TriggerPolicy / EvolutionEvent / quality_report / Code* dataclasses
│   ├── runtime/       # CodeValidator + CodeSandbox + CodeSkillRuntime + Hybrid
│   ├── nl/            # LLM client + 4 prompts
│   ├── code_factory.py
│   ├── config_factory.py
│   ├── workflow_*.py
│   ├── audit.py
│   ├── facade.py      # VibeCoder
│   └── cli.py         # python -m vibe_coding ...
├── tests/
├── examples/
├── scripts/sync_from_eskill.py
└── docs/
```

## Sync from the prototype

If `eskill-prototype` evolves the upstream code, sync forward:

```bash
python scripts/sync_from_eskill.py
```

The script copies `eskill.vibe_coding.*` source into `src/vibe_coding/`,
rewrites the few imports that referred to `eskill.code`, `eskill.models`, and
`eskill.static_executor` so the standalone package stays self-contained.

See `docs/UPGRADE_GUIDE.md` for the full workflow.

## License

MIT — same as the upstream `eskill-prototype`.
