"""公网 Catalog 本地 JSON 存储（首期无数据库）。"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import threading
from pathlib import Path
from typing import Any, Dict, List, Tuple

_lock = threading.Lock()


def default_catalog_dir() -> Path:
    raw = (os.environ.get("MODSTORE_CATALOG_DIR") or "").strip()
    if raw:
        return Path(raw).expanduser().resolve()
    return Path(__file__).resolve().parent / "catalog_data"


def packages_path() -> Path:
    d = default_catalog_dir()
    d.mkdir(parents=True, exist_ok=True)
    return d / "packages.json"


def files_dir() -> Path:
    d = default_catalog_dir() / "files"
    d.mkdir(parents=True, exist_ok=True)
    return d


def load_store() -> Dict[str, Any]:
    p = packages_path()
    if not p.is_file():
        return {"packages": []}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        if isinstance(data, dict) and isinstance(data.get("packages"), list):
            return data
    except (json.JSONDecodeError, OSError):
        pass
    return {"packages": []}


def save_store(data: Dict[str, Any]) -> None:
    p = packages_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(p)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def list_packages(
    *,
    artifact: str | None = None,
    q: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> Tuple[List[Dict[str, Any]], int]:
    with _lock:
        rows = list(load_store().get("packages") or [])
    total = len(rows)
    if artifact:
        rows = [r for r in rows if str(r.get("artifact") or "mod") == artifact]
    if q:
        ql = q.lower()
        rows = [
            r
            for r in rows
            if ql in str(r.get("name", "")).lower()
            or ql in str(r.get("id", "")).lower()
            or ql in str(r.get("description", "")).lower()
        ]
    rows = rows[offset : offset + max(1, min(limit, 500))]
    return rows, total


def get_package(id_: str, version: str) -> Dict[str, Any] | None:
    id_ = (id_ or "").strip()
    version = (version or "").strip()
    with _lock:
        for r in load_store().get("packages") or []:
            if str(r.get("id")) == id_ and str(r.get("version")) == version:
                return dict(r)
    return None


def list_versions(id_: str) -> List[Dict[str, Any]]:
    """返回某个包 id 下的全部版本（按 created_at / version 倒序，缺失字段时按列表顺序）。"""
    pid = (id_ or "").strip()
    if not pid:
        return []
    with _lock:
        rows = [dict(r) for r in load_store().get("packages") or [] if str(r.get("id")) == pid]
    rows.sort(
        key=lambda r: (str(r.get("created_at") or ""), str(r.get("version") or "")),
        reverse=True,
    )
    return rows


def promote_draft_to_stable(id_: str, from_version: str) -> Dict[str, Any]:
    """把 draft-* 草稿晋升为正式版本：以 from_version 为模板，生成新的稳定版记录。

    规则：
    - from_version 必须以 ``draft-`` 开头且在该 id 下存在；
    - 新版本号 = from_version 去掉 ``draft-`` 前缀后保留剩余段，若已存在则追加 ``+N``；
    - 写入新记录后保留旧 draft，便于回滚。
    """
    pid = (id_ or "").strip()
    src_ver = (from_version or "").strip()
    if not pid or not src_ver:
        raise ValueError("id 与 from_version 必填")
    if not src_ver.startswith("draft-"):
        raise ValueError("from_version 必须以 draft- 开头")
    src = get_package(pid, src_ver)
    if not src:
        raise ValueError("源版本不存在")
    base_target = src_ver[len("draft-") :].strip() or "1.0.0"
    target = base_target
    bump = 1
    while get_package(pid, target) is not None:
        bump += 1
        target = f"{base_target}+{bump}"
    rec = dict(src)
    rec["version"] = target
    rec["release_channel"] = "stable"
    rec.pop("created_at", None)
    with _lock:
        data = load_store()
        pkgs = list(data.get("packages") or [])
        pkgs.append(rec)
        data["packages"] = pkgs
        save_store(data)
    return rec


def append_package(record: Dict[str, Any], src_file: Path | None) -> Dict[str, Any]:
    """写入记录；若提供 src_file 则复制到 files/ 并填写 download_path / sha256。"""
    pid = str(record.get("id") or "").strip()
    ver = str(record.get("version") or "").strip()
    if not pid or not ver:
        raise ValueError("id 与 version 必填")

    rec = dict(record)
    rec.setdefault("artifact", "mod")
    rec.setdefault(
        "commerce",
        {"mode": "free", "product_id": None, "sku": None},
    )
    rec.setdefault("license", {"type": "none", "verify_url": None})

    if src_file is not None and src_file.is_file():
        fd = files_dir()
        ext = src_file.suffix.lower() or ".xcmod"
        dest = fd / f"{pid}-{ver}{ext}"
        shutil.copy2(src_file, dest)
        rec["sha256"] = sha256_file(dest)
        rec["file_size"] = dest.stat().st_size
        rec["stored_filename"] = dest.name

    with _lock:
        data = load_store()
        pkgs = [x for x in data.get("packages") or [] if not (str(x.get("id")) == pid and str(x.get("version")) == ver)]
        pkgs.append(rec)
        data["packages"] = pkgs
        save_store(data)
    return rec
