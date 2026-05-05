"""测试 :mod:`modstore_server.integrations.vibe_eskill_adapter` 与
:func:`eskill_runtime._execute_logic` 的派发分支。
"""

from __future__ import annotations

import importlib.util

import pytest

if importlib.util.find_spec("vibe_coding") is None:
    pytest.skip("vibe-coding 未安装,跳过 ESkill adapter 测试", allow_module_level=True)


def test_render_brief_substitutes_placeholders():
    from modstore_server.integrations.vibe_eskill_adapter import _render_brief

    out = _render_brief({"brief": "求 {{x}} 的平方"}, {"x": 5})
    assert out == "求 5 的平方"


def test_render_brief_falls_back_to_input_json():
    from modstore_server.integrations.vibe_eskill_adapter import _render_brief

    out = _render_brief({}, {"text": "hello"})
    assert "hello" in out


def test_execute_vibe_code_kind_uses_run_input_mapping(monkeypatch):
    class _Skill:
        skill_id = "vc-eskill-1"

        def to_dict(self):
            return {"skill_id": self.skill_id, "code": "..."}

    class _Run:
        def to_dict(self):
            return {"output": 42}

    class _StubCoder:
        def code(self, brief, *, mode="brief_first", skill_id=None):
            return _Skill()

        def run(self, sid, input_data):
            assert input_data == {"a": 1}
            return _Run()

    monkeypatch.setattr(
        "modstore_server.integrations.vibe_adapter.get_vibe_coder",
        lambda **kw: _StubCoder(),
    )
    monkeypatch.setattr(
        "modstore_server.integrations.vibe_eskill_adapter._resolve_provider_model",
        lambda logic, uid: {"provider": "openai", "model": "gpt-4o-mini"},
    )

    from modstore_server.integrations.vibe_eskill_adapter import execute_vibe_code_kind

    result = execute_vibe_code_kind(
        {
            "type": "vibe_code",
            "brief": "压平 {{a}}",
            "run_input_mapping": {"a": "src"},
            "output_var": "vibe_out",
        },
        {"src": 1, "extra": 9},
        user_id=1,
    )
    assert result["ok"] is True
    assert result["vibe_run"]["output"] == 42
    assert result["vibe_out"]["output"] == 42


def test_execute_vibe_workflow_kind_runs_graph(monkeypatch):
    class _Graph:
        def to_dict(self):
            return {"nodes": [{"id": "n1"}], "edges": []}

    class _RunResult:
        def to_dict(self):
            return {"status": "completed", "output": {"x": 1}}

    class _StubCoder:
        def workflow(self, brief):
            assert brief
            return _Graph()

        def execute(self, graph, input_data):
            assert isinstance(graph, _Graph)
            return _RunResult()

    monkeypatch.setattr(
        "modstore_server.integrations.vibe_adapter.get_vibe_coder",
        lambda **kw: _StubCoder(),
    )
    monkeypatch.setattr(
        "modstore_server.integrations.vibe_eskill_adapter._resolve_provider_model",
        lambda logic, uid: {"provider": "openai", "model": "gpt-4o-mini"},
    )

    from modstore_server.integrations.vibe_eskill_adapter import execute_vibe_workflow_kind

    out = execute_vibe_workflow_kind(
        {"type": "vibe_workflow", "brief": "拆 {{topic}}"},
        {"topic": "演示"},
        user_id=1,
    )
    assert out["ok"] is True
    assert out["vibe_graph"]["nodes"][0]["id"] == "n1"
    assert out["vibe_workflow_run"]["output"] == {"x": 1}


def test_eskill_runtime_dispatches_vibe_code(monkeypatch):
    """``eskill_runtime._execute_logic`` 在 type=vibe_code 时委派到本适配器。"""
    monkeypatch.setattr(
        "modstore_server.integrations.vibe_eskill_adapter.execute_vibe_kind",
        lambda logic, input_data, *, user_id: {
            "eskill_logic_type": str(logic.get("type") or ""),
            "ok": True,
            "vibe_skill": {"skill_id": "x"},
            "stub_payload": dict(input_data),
            "user_id_seen": user_id,
        },
    )
    from modstore_server.eskill_runtime import ESkillRuntime

    runtime = ESkillRuntime()
    out = runtime._execute_logic(
        {"type": "vibe_code", "brief": "x"},
        {"k": "v"},
        user_id=7,
    )
    assert out["ok"] is True
    assert out["stub_payload"] == {"k": "v"}
    assert out["user_id_seen"] == 7
