"""员工包生成后可被运行时加载与执行器识别。"""

from __future__ import annotations

import asyncio
import io
import json
import tempfile
import zipfile
from pathlib import Path


def test_employee_pack_parser_adds_web_rankings_config():
    from modstore_server.employee_ai_scaffold import parse_employee_pack_llm_json

    manifest, err = parse_employee_pack_llm_json(
        json.dumps(
            {
                "id": "ai-rankings-stats",
                "name": "AI 模型排行统计员工",
                "version": "1.0.0",
                "description": "上网获取 AI 模型排行榜并统计来源和结论",
                "employee": {"id": "ai-rankings", "label": "AI 排行统计", "capabilities": ["web.rankings"]},
            },
            ensure_ascii=False,
        )
    )

    assert err == ""
    assert manifest is not None
    assert manifest["employee_config_v2"]["perception"]["type"] == "web_rankings"
    assert manifest["employee_config_v2"]["actions"]["handlers"] == ["echo"]


def test_employee_runtime_loads_manifest_from_registered_zip(tmp_path, monkeypatch):
    monkeypatch.setenv("MODSTORE_CATALOG_DIR", str(tmp_path / "catalog"))
    monkeypatch.setenv("MODSTORE_DB_PATH", str(tmp_path / "modstore.db"))

    from modstore_server import models
    from modstore_server.catalog_store import append_package
    from modstore_server.employee_ai_scaffold import build_employee_pack_zip
    from modstore_server.employee_runtime import load_employee_pack, parse_employee_config_v2
    from modstore_server.models import CatalogItem

    models._engine = None
    models._SessionFactory = None
    models.init_db()

    manifest = {
        "id": "rank-pack",
        "name": "排行员工",
        "version": "1.0.0",
        "artifact": "employee_pack",
        "scope": "global",
        "employee": {"id": "ranker", "label": "排行员工", "capabilities": []},
        "employee_config_v2": {"perception": {"type": "web_rankings"}, "actions": {"handlers": ["echo"]}},
    }
    raw = build_employee_pack_zip("rank-pack", manifest)
    with zipfile.ZipFile(io.BytesIO(raw), "r") as zf:
        names = {n.replace("\\", "/") for n in zf.namelist()}
        assert "rank-pack/backend/blueprints.py" in names
        assert "rank-pack/backend/employees/ranker.py" in names
        assert "rank-pack/manifest.json" in names
    with tempfile.NamedTemporaryFile(suffix=".xcemp", delete=False) as tmp:
        tmp.write(raw)
        tmp_path = Path(tmp.name)
    try:
        saved = append_package(
            {"id": "rank-pack", "name": "排行员工", "version": "1.0.0", "artifact": "employee_pack"},
            tmp_path,
        )
    finally:
        tmp_path.unlink(missing_ok=True)

    sf = models.get_session_factory()
    with sf() as db:
        db.add(
            CatalogItem(
                pkg_id="rank-pack",
                version="1.0.0",
                name="排行员工",
                artifact="employee_pack",
                stored_filename=saved["stored_filename"],
            )
        )
        db.commit()
        pack = load_employee_pack(db, "rank-pack")

    cfg = parse_employee_config_v2(pack["manifest"])
    assert cfg["perception"]["type"] == "web_rankings"


def test_run_employee_ai_scaffold_registers_runtime_catalog(tmp_path, monkeypatch):
    monkeypatch.setenv("MODSTORE_CATALOG_DIR", str(tmp_path / "catalog"))
    monkeypatch.setenv("MODSTORE_DB_PATH", str(tmp_path / "modstore.db"))

    from modman.repo_config import RepoConfig
    from modstore_server import models
    from modstore_server.models import CatalogItem, User
    from modstore_server.mod_scaffold_runner import run_employee_ai_scaffold_async

    models._engine = None
    models._SessionFactory = None
    models.init_db()

    sf = models.get_session_factory()
    with sf() as db:
        user = User(username="chain", email="chain@example.local", password_hash="x")
        db.add(user)
        db.commit()
        db.refresh(user)
        user_id = user.id

    async def fake_chat_dispatch(*args, **kwargs):
        return {
            "ok": True,
            "content": json.dumps(
                {
                    "id": "ai-rankings-stats",
                    "name": "AI 模型排行统计员工",
                    "version": "1.0.0",
                    "description": "上网获取 AI 模型排行榜并统计来源和结论",
                    "employee": {"id": "ranker", "label": "排行员工", "capabilities": ["web.rankings"]},
                },
                ensure_ascii=False,
            ),
        }

    monkeypatch.setattr("modstore_server.mod_scaffold_runner.chat_dispatch", fake_chat_dispatch)
    monkeypatch.setattr("modstore_server.mod_scaffold_runner.resolve_api_key", lambda *args, **kwargs: ("k", "test"))
    monkeypatch.setattr(
        "modstore_server.mod_scaffold_runner.load_config",
        lambda: RepoConfig(library_root=str(tmp_path / "library"), xcagi_root="", xcagi_backend_url="http://test.invalid"),
    )

    with sf() as db:
        user = db.query(User).filter(User.id == user_id).first()
        res = asyncio.run(
            run_employee_ai_scaffold_async(
                db,
                user,
                brief="生成 AI 模型排行统计员工",
                provider="deepseek",
                model="deepseek-chat",
            )
        )
        assert res["ok"] is True
        row = db.query(CatalogItem).filter(CatalogItem.pkg_id == "ai-rankings-stats").first()
        assert row is not None
        assert row.artifact == "employee_pack"
        assert row.author_id == user_id
        assert row.stored_filename
