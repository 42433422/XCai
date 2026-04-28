from __future__ import annotations

import asyncio
from pathlib import Path

from modstore_server.workbench_script_runner import run_script_job, validate_script


def test_validate_script_blocks_dangerous_import():
    errors = validate_script("import subprocess\nprint('x')\n")
    assert errors
    assert "subprocess" in ";".join(errors)


def test_run_script_job_fallback_generates_output(tmp_path, monkeypatch):
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
    assert result["ok"] is True
    assert result["outputs"]
    assert Path(result["outputs"][0]["path"]).is_file()


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
