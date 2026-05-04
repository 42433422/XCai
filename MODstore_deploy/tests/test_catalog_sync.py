"""catalog_sync：XC JSON 与 catalog_items / 员工列表对齐。"""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

pytest.importorskip("sqlalchemy")

from modstore_server.models import Base, CatalogItem
from modstore_server.catalog_sync import (
    sync_packages_json_to_catalog_items,
    upsert_catalog_item_from_xc_package_dict,
)


@pytest.fixture
def mem_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    try:
        yield db
    finally:
        db.close()


def test_upsert_catalog_item_from_xc_package_dict_employee_pack(mem_db):
    upsert_catalog_item_from_xc_package_dict(
        mem_db,
        {
            "id": "emp.pkg.sync-test",
            "version": "1.0.0",
            "name": "Sync Test",
            "artifact": "employee_pack",
            "description": "d",
            "industry": "通用",
            "stored_filename": "emp.pkg.sync-test-1.0.0.xcemp",
            "sha256": "deadbeef",
            "commerce": {"mode": "free"},
        },
        author_id=None,
    )
    mem_db.commit()
    row = mem_db.query(CatalogItem).filter(CatalogItem.pkg_id == "emp.pkg.sync-test").one()
    assert row.artifact == "employee_pack"
    assert row.stored_filename == "emp.pkg.sync-test-1.0.0.xcemp"
    assert row.version == "1.0.0"


def test_upsert_updates_same_pkg_id_new_version(mem_db):
    rec = {
        "id": "same.pkg",
        "version": "1.0.0",
        "name": "A",
        "artifact": "employee_pack",
        "stored_filename": "a.zip",
    }
    upsert_catalog_item_from_xc_package_dict(mem_db, rec, author_id=None)
    mem_db.commit()
    rec2 = dict(rec)
    rec2["version"] = "1.0.1"
    rec2["stored_filename"] = "b.zip"
    upsert_catalog_item_from_xc_package_dict(mem_db, rec2, author_id=None)
    mem_db.commit()
    rows = mem_db.query(CatalogItem).filter(CatalogItem.pkg_id == "same.pkg").all()
    assert len(rows) == 1
    assert rows[0].version == "1.0.1"
    assert rows[0].stored_filename == "b.zip"


def test_sync_packages_json_uses_xc_stored_filename_for_db(monkeypatch, tmp_path: Path, mem_db):
    """DB 行应保存 XC files 下的文件名，便于 employee_runtime 解析 zip。"""
    pkg_dir = tmp_path / "catalog"
    pkg_dir.mkdir()
    monkeypatch.setenv("MODSTORE_CATALOG_DIR", str(pkg_dir))
    from modstore_server.catalog_store import files_dir, save_store

    fname = "pkg-a-1.xcemp"
    fd = files_dir()
    fd.mkdir(parents=True, exist_ok=True)
    (fd / fname).write_bytes(b"PK\x03\x04fake")

    save_store(
        {
            "packages": [
                {
                    "id": "pkg.a",
                    "version": "1.0.0",
                    "name": "Pkg A",
                    "artifact": "employee_pack",
                    "stored_filename": fname,
                    "sha256": "abc",
                    "commerce": {"mode": "free"},
                }
            ]
        }
    )

    out = sync_packages_json_to_catalog_items(mem_db, admin_user_id=1)
    mem_db.commit()
    assert out["inserted"] == 1
    row = mem_db.query(CatalogItem).filter(CatalogItem.pkg_id == "pkg.a").one()
    assert row.stored_filename == fname
    assert (files_dir() / row.stored_filename).is_file()


def test_list_employees_sees_upserted_row(monkeypatch, mem_db):
    from modstore_server import employee_executor

    factory = sessionmaker(bind=mem_db.bind)
    monkeypatch.setattr(employee_executor, "get_session_factory", lambda: factory)

    upsert_catalog_item_from_xc_package_dict(
        mem_db,
        {
            "id": "emp.list.test",
            "version": "1.0.0",
            "name": "List Test",
            "artifact": "employee_pack",
            "stored_filename": "x.zip",
        },
        author_id=None,
    )
    mem_db.commit()

    rows = employee_executor.list_employees()
    ids = [r["id"] for r in rows]
    assert "emp.list.test" in ids
