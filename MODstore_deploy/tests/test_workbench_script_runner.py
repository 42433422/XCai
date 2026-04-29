from __future__ import annotations

import asyncio
from modstore_server.workbench_script_runner import run_script_job, validate_script


def test_validate_script_blocks_dangerous_import():
    errors = validate_script("import subprocess\nprint('x')\n")
    assert errors
    assert "subprocess" in ";".join(errors)


def test_run_script_job_requires_llm_when_no_provider(tmp_path, monkeypatch):
    import modstore_server.workbench_script_runner as runner

    monkeypatch.setattr(runner, "SCRIPT_ROOT", tmp_path)
    result = asyncio.run(
        run_script_job(
            db=None,
            user_id=1,
            session_id="test-session",
            brief="汇总 Excel",
            files=[{"filename": "input.xlsx", "content": _xlsx_bytes()}],
            provider=None,
            model=None,
        )
    )
    assert result["ok"] is False
    assert result["outputs"] == []
    assert result["errors"]
    assert "LLM" in "".join(result["errors"]) or "供应商" in "".join(result["errors"])


def _xlsx_bytes() -> bytes:
    import io
    import openpyxl

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["姓名", "工资"])
    ws.append(["张三", 100])
    raw = io.BytesIO()
    wb.save(raw)
    return raw.getvalue()
