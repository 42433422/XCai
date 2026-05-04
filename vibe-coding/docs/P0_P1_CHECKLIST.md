# P0 / P1 Checklist (vs Trae and similar AI IDEs)

A capability matrix to make the differentiation explicit. "Standalone" refers
to this `vibe-coding/` package; "Upstream" refers to `eskill.vibe_coding` in
the prototype.

## P0 — must ship to be called "vibe coding"

| Capability | Trae | Standalone | Upstream |
| --- | :---: | :---: | :---: |
| NL → Python code generation | yes | yes | yes |
| Auto execute generated code | yes | yes | yes |
| Auto-run test cases against generated code (sandbox) | no | yes | yes |
| Auto-repair failing code via LLM with diff feedback | no | yes | yes |
| AST safety check (import whitelist + forbidden builtins) | weak | yes | yes |
| Subprocess sandbox with timeout / mem limit | no | yes | yes |
| Version snapshot per repair (immutable) | no | yes | yes |

## P1 — decides whether the system is competitive

| Capability | Trae | Standalone | Upstream |
| --- | :---: | :---: | :---: |
| Domain guard rejects out-of-scope inputs | no | yes | yes |
| Quality gate (required keys / min_length / regex) | no | yes | yes |
| Regression test on every patch | no | yes | yes |
| Config layer + Code layer coexist | no | no (code only) | yes |
| Workflow orchestration | partial | yes | yes |
| Dual-layer architecture (Employee + Skill) | no | no | yes (`ESkillNodeWrapper`) |
| One-shot NL → multi-skill workflow | partial | yes | yes |
| Patch ledger + one-click rollback | no | yes | yes |
| Brief-first two-stage generation | no | yes | yes |

## Why this matters

Generation alone (Trae's lane) hands the user a draft they still have to
verify. The vibe-coding flow goes one big step further: every artefact you
receive has already executed your test cases inside an isolated subprocess,
and runtime failures during deployment trigger an automatic diagnose →
LLM-repair → AST-validate → sandbox-verify → solidify pipeline. The result
is closer to a self-evolving agent than a code completion tool.

For the upstream tree, the dual-layer architecture extends this to entire
employees: when one Skill node solidifies a new version, the bridge can fan
out and adjust trust / strategy on the owning Employee. The standalone tree
keeps things simple (code layer only) — it's the right entry point if you're
researching the loop or embedding it into a project that doesn't already
depend on eskill.
