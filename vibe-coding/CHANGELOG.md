# Changelog

## 0.1.0 — 2026-05-04

Initial release. Mirrors `eskill.vibe_coding` from `eskill-prototype` with a
standalone runtime that has no dependency on the `eskill` package.

- `runtime/`: copy of `eskill.code` (validator, sandbox, diagnostics, patch
  generator, code runtime, code store, hybrid runtime) with internals
  rerouted to the local `_internals/` module.
- `_internals/`: `TriggerPolicy`, `EvolutionEvent`, `now_iso`,
  `quality_report`, plus the full `Code*` dataclass family copied verbatim.
- `nl/`: LLM client abstraction + four system prompts.
- `code_factory.py`, `config_factory.py`, `workflow_factory.py`,
  `workflow_engine.py`, `audit.py`, `facade.py`, `cli.py`.
- `scripts/sync_from_eskill.py`: one-shot sync from upstream prototype.
- `tests/`, `examples/`, `docs/` mirroring the upstream additions.
