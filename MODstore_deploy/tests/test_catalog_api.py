"""Catalog /v1 路由冒烟（内存临时目录）。"""

import json
import os
from pathlib import Path

import pytest

pytest.importorskip("fastapi")


def test_catalog_index_empty(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("MODSTORE_CATALOG_DIR", str(tmp_path))
    from modstore_server.catalog_store import load_store, save_store

    save_store({"packages": []})
    from fastapi.testclient import TestClient
    from modstore_server.app import app

    c = TestClient(app)
    r = c.get("/v1/index.json")
    assert r.status_code == 200
    assert r.json() == {"packages": []}


def test_catalog_upload_with_token(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("MODSTORE_CATALOG_DIR", str(tmp_path))
    monkeypatch.setenv("MODSTORE_CATALOG_UPLOAD_TOKEN", "secret-test")
    from modstore_server.catalog_store import save_store

    save_store({"packages": []})

    from fastapi.testclient import TestClient
    from modstore_server.app import app

    # 最小 zip：含 manifest.json（mod）
    import io
    import zipfile

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr(
            "manifest.json",
            json.dumps(
                {
                    "id": "catalog-test-mod",
                    "name": "Test",
                    "version": "0.0.1",
                    "artifact": "mod",
                    "backend": {"entry": "blueprints", "init": "mod_init"},
                    "frontend": {"routes": "routes"},
                },
                ensure_ascii=False,
            ),
        )
        zf.writestr("backend/blueprints.py", "# stub\n")
        zf.writestr("backend/mod_init.py", "def mod_init():\n    pass\n")
        zf.writestr("frontend/routes.js", "export default []\n")
    buf.seek(0)

    c = TestClient(app)
    meta = json.dumps(
        {
            "id": "catalog-test-mod",
            "version": "0.0.1",
            "name": "Test",
            "artifact": "mod",
        },
        ensure_ascii=False,
    )
    r = c.post(
        "/v1/packages",
        headers={"Authorization": "Bearer secret-test"},
        data={"metadata": meta},
        files={"file": ("catalog-test-mod-0.0.1.xcmod", buf.getvalue(), "application/zip")},
    )
    assert r.status_code == 200, r.text
    idx = c.get("/v1/index.json").json()
    assert len(idx["packages"]) == 1
    assert idx["packages"][0]["id"] == "catalog-test-mod"
