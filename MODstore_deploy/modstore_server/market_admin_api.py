"""XC AGI 在线市场 API：管理员路由（目录管理、上传、用户、钱包、交易）。"""

from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field

from modstore_server import catalog_sync
from modstore_server.models import (
    CatalogItem,
    Transaction,
    User,
    Wallet,
    get_session_factory,
)
from modstore_server.market_shared import (
    _catalog_item_payload,
    _ensure_catalog_listing_allowed,
    _get_current_user,
    _normalize_ip_risk_level,
    _normalize_license_scope,
    _normalize_material_category,
    _normalize_origin_type,
    _require_admin,
)

router = APIRouter(tags=["market"])


def _catalog_files_dir() -> Path:
    d = Path(__file__).resolve().parent / "market_files"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _upload_chunks_dir() -> Path:
    d = Path(__file__).resolve().parent / "upload_chunks"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _compute_sha256(file_path: Path) -> str:
    h = hashlib.sha256()
    with file_path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


class UploadCatalogDTO(BaseModel):
    pkg_id: str = Field(..., min_length=1, max_length=128)
    version: str = Field(..., min_length=1, max_length=32)
    name: str = Field(..., min_length=1, max_length=256)
    description: str = ""
    price: float = Field(..., ge=0)
    artifact: str = "mod"


class UploadSession(BaseModel):
    session_id: str
    file_name: str
    total_size: int
    chunk_size: int
    total_chunks: int


class UploadChunk(BaseModel):
    session_id: str
    chunk_index: int
    chunk_data: bytes


class CompleteUpload(BaseModel):
    session_id: str
    pkg_id: str
    version: str
    name: str
    description: str = ""
    price: float = 0.0
    artifact: str = "mod"
    industry: str = "通用"
    material_category: str = ""
    license_scope: str = "personal"
    origin_type: str = "original"
    ip_risk_level: str = "low"


@router.post("/admin/catalog", summary="管理员上传 MOD 到市场（支持文件上传）")
async def api_admin_upload_catalog(
    pkg_id: str = Form(..., min_length=1, max_length=128),
    version: str = Form(..., min_length=1, max_length=32),
    name: str = Form(..., min_length=1, max_length=256),
    description: str = Form(""),
    price: float = Form(0, ge=0),
    artifact: str = Form("mod"),
    industry: str = Form("通用"),
    material_category: str = Form(""),
    license_scope: str = Form(""),
    origin_type: str = Form("original"),
    ip_risk_level: str = Form("low"),
    file: UploadFile = File(None),
    user: User = Depends(_require_admin),
):
    sf = get_session_factory()
    with sf() as session:
        existing = (
            session.query(CatalogItem)
            .filter(CatalogItem.pkg_id == pkg_id, CatalogItem.version == version)
            .first()
        )
        if existing:
            raise HTTPException(409, f"pkg_id '{pkg_id}' + version '{version}' 已存在")

        stored_filename = ""
        sha256 = ""

        if file and file.filename:
            suffix = Path(file.filename).suffix.lower()
            if suffix not in {".zip", ".xcmod", ".xcemp"}:
                raise HTTPException(400, "仅支持 .zip / .xcmod / .xcemp 格式")

            dest_dir = _catalog_files_dir()
            dest_name = f"{pkg_id}-{version}{suffix}"
            dest_path = dest_dir / dest_name

            content = await file.read()
            if len(content) > 100 * 1024 * 1024:
                raise HTTPException(400, "文件过大（>100MB）")

            dest_path.write_bytes(content)
            stored_filename = dest_name
            sha256 = _compute_sha256(dest_path)

        ind = (industry or "").strip() or "通用"
        mat = _normalize_material_category(material_category, artifact)
        lic = _normalize_license_scope(license_scope, price)
        origin = _normalize_origin_type(origin_type)
        risk = _normalize_ip_risk_level(ip_risk_level)
        _ensure_catalog_listing_allowed(
            price=price,
            license_scope=lic,
            origin_type=origin,
            ip_risk_level=risk,
        )
        item = CatalogItem(
            pkg_id=pkg_id,
            version=version,
            name=name,
            description=description,
            price=price,
            author_id=user.id,
            artifact=artifact,
            industry=ind,
            material_category=mat,
            license_scope=lic,
            origin_type=origin,
            ip_risk_level=risk,
            compliance_status="approved",
            rank_score=100.0,
            stored_filename=stored_filename,
            sha256=sha256,
        )
        session.add(item)
        session.commit()
        session.refresh(item)
        return {
            "ok": True,
            "id": item.id,
            "pkg_id": item.pkg_id,
            "stored_filename": item.stored_filename,
        }


@router.post(
    "/admin/catalog/sync-from-xc-packages", summary="从 XC catalog_store 同步缺失条目到市场库"
)
def api_admin_sync_xc_catalog_packages(user: User = Depends(_require_admin)):
    sf = get_session_factory()
    with sf() as session:
        out = catalog_sync.sync_packages_json_to_catalog_items(session, admin_user_id=user.id)
        session.commit()
    return {"ok": True, **out}


@router.get("/admin/catalog")
def api_admin_list_catalog(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user: User = Depends(_require_admin),
):
    sf = get_session_factory()
    with sf() as session:
        total = session.query(CatalogItem).count()
        rows = (
            session.query(CatalogItem)
            .order_by(CatalogItem.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )
        return {
            "items": [
                {
                    **_catalog_item_payload(r),
                    "stored_filename": r.stored_filename,
                    "sha256": r.sha256,
                    "is_public": r.is_public,
                }
                for r in rows
            ],
            "total": total,
        }


@router.post("/admin/upload/initiate", summary="初始化分块上传")
def api_initiate_upload(
    file_name: str = Form(...),
    total_size: int = Form(...),
    chunk_size: int = Form(...),
    user: User = Depends(_require_admin),
):
    import uuid

    session_id = str(uuid.uuid4())
    total_chunks = (total_size + chunk_size - 1) // chunk_size

    session_dir = _upload_chunks_dir() / session_id
    session_dir.mkdir(parents=True, exist_ok=True)

    session_info = {
        "session_id": session_id,
        "file_name": file_name,
        "total_size": total_size,
        "chunk_size": chunk_size,
        "total_chunks": total_chunks,
        "created_at": datetime.utcnow().isoformat(),
    }

    with open(session_dir / "session.json", "w", encoding="utf-8") as f:
        json.dump(session_info, f)

    return {"ok": True, "session_id": session_id, "total_chunks": total_chunks}


@router.post("/admin/upload/chunk", summary="上传文件块")
async def api_upload_chunk(
    session_id: str = Form(...),
    chunk_index: int = Form(...),
    file: UploadFile = File(...),
    user: User = Depends(_require_admin),
):
    session_dir = _upload_chunks_dir() / session_id
    if not session_dir.exists():
        raise HTTPException(404, "上传会话不存在")

    with open(session_dir / "session.json", "r", encoding="utf-8") as f:
        session_info = json.load(f)

    if chunk_index >= session_info["total_chunks"]:
        raise HTTPException(400, "无效的块索引")

    chunk_path = session_dir / f"chunk_{chunk_index}"
    content = await file.read()

    with open(chunk_path, "wb") as f:
        f.write(content)

    return {"ok": True, "chunk_index": chunk_index}


@router.post("/admin/upload/complete", summary="完成分块上传")
def api_complete_upload(
    session_id: str = Form(...),
    pkg_id: str = Form(...),
    version: str = Form(...),
    name: str = Form(...),
    description: str = Form(""),
    price: float = Form(0.0),
    artifact: str = Form("mod"),
    industry: str = Form("通用"),
    material_category: str = Form(""),
    license_scope: str = Form(""),
    origin_type: str = Form("original"),
    ip_risk_level: str = Form("low"),
    user: User = Depends(_require_admin),
):
    session_dir = _upload_chunks_dir() / session_id
    if not session_dir.exists():
        raise HTTPException(404, "上传会话不存在")

    with open(session_dir / "session.json", "r", encoding="utf-8") as f:
        session_info = json.load(f)

    missing_chunks = []
    for i in range(session_info["total_chunks"]):
        chunk_path = session_dir / f"chunk_{i}"
        if not chunk_path.exists():
            missing_chunks.append(i)

    if missing_chunks:
        raise HTTPException(400, f"缺少文件块: {missing_chunks}")

    suffix = Path(session_info["file_name"]).suffix.lower()
    if suffix not in {".zip", ".xcmod", ".xcemp"}:
        raise HTTPException(400, "仅支持 .zip / .xcmod / .xcemp 格式")

    dest_dir = _catalog_files_dir()
    dest_name = f"{pkg_id}-{version}{suffix}"
    dest_path = dest_dir / dest_name

    with open(dest_path, "wb") as out_file:
        for i in range(session_info["total_chunks"]):
            chunk_path = session_dir / f"chunk_{i}"
            with open(chunk_path, "rb") as in_file:
                out_file.write(in_file.read())

    sha256 = _compute_sha256(dest_path)

    shutil.rmtree(session_dir)

    sf = get_session_factory()
    with sf() as session:
        existing = (
            session.query(CatalogItem)
            .filter(CatalogItem.pkg_id == pkg_id, CatalogItem.version == version)
            .first()
        )
        if existing:
            raise HTTPException(409, f"pkg_id '{pkg_id}' + version '{version}' 已存在")

        ind = (industry or "").strip() or "通用"
        mat = _normalize_material_category(material_category, artifact)
        lic = _normalize_license_scope(license_scope, price)
        origin = _normalize_origin_type(origin_type)
        risk = _normalize_ip_risk_level(ip_risk_level)
        _ensure_catalog_listing_allowed(
            price=price,
            license_scope=lic,
            origin_type=origin,
            ip_risk_level=risk,
        )
        item = CatalogItem(
            pkg_id=pkg_id,
            version=version,
            name=name,
            description=description,
            price=price,
            author_id=user.id,
            artifact=artifact,
            industry=ind,
            material_category=mat,
            license_scope=lic,
            origin_type=origin,
            ip_risk_level=risk,
            compliance_status="approved",
            rank_score=100.0,
            stored_filename=dest_name,
            sha256=sha256,
        )
        session.add(item)
        session.commit()
        session.refresh(item)

        return {
            "ok": True,
            "id": item.id,
            "pkg_id": item.pkg_id,
            "stored_filename": item.stored_filename,
            "file_size": session_info["total_size"],
        }


@router.delete("/admin/catalog/{item_id}")
def api_admin_delete_catalog(item_id: int, user: User = Depends(_require_admin)):
    sf = get_session_factory()
    with sf() as session:
        item = session.query(CatalogItem).filter(CatalogItem.id == item_id).first()
        if not item:
            raise HTTPException(404, "商品不存在")

        item.is_public = False
        item.compliance_status = "delisted"
        item.delist_reason = "管理员手动下架"
        item.rank_score = 0.0
        session.commit()
        return {"ok": True, "deleted_id": item_id}


@router.get("/admin/users")
def api_admin_list_users(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user: User = Depends(_require_admin),
):
    sf = get_session_factory()
    with sf() as session:
        total = session.query(User).count()
        rows = (
            session.query(User).order_by(User.created_at.desc()).offset(offset).limit(limit).all()
        )
        return {
            "users": [
                {
                    "id": r.id,
                    "username": r.username,
                    "email": r.email,
                    "is_admin": r.is_admin,
                    "created_at": r.created_at.isoformat() if r.created_at else "",
                }
                for r in rows
            ],
            "total": total,
        }


@router.put("/admin/users/{user_id}/admin")
def api_admin_set_admin_status(
    user_id: int,
    is_admin: bool = Query(...),
    user: User = Depends(_require_admin),
):
    sf = get_session_factory()
    with sf() as session:
        target = session.query(User).filter(User.id == user_id).first()
        if not target:
            raise HTTPException(404, "用户不存在")
        target.is_admin = is_admin
        session.commit()
        return {"ok": True, "user_id": user_id, "is_admin": is_admin}


@router.get("/admin/wallets")
def api_admin_list_wallets(
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    user: User = Depends(_require_admin),
):
    sf = get_session_factory()
    with sf() as session:
        total = session.query(Wallet).count()
        rows = session.query(Wallet).order_by(Wallet.id).offset(offset).limit(limit).all()
        return {
            "items": [
                {
                    "id": w.id,
                    "user_id": w.user_id,
                    "balance": w.balance,
                    "updated_at": w.updated_at.isoformat() if w.updated_at else "",
                }
                for w in rows
            ],
            "total": total,
        }


@router.get("/admin/transactions")
def api_admin_list_transactions(
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    user: User = Depends(_require_admin),
):
    sf = get_session_factory()
    with sf() as session:
        total = session.query(Transaction).count()
        rows = (
            session.query(Transaction)
            .order_by(Transaction.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )
        return {
            "items": [
                {
                    "id": t.id,
                    "user_id": t.user_id,
                    "amount": t.amount,
                    "txn_type": t.txn_type,
                    "status": t.status,
                    "description": t.description,
                    "created_at": t.created_at.isoformat() if t.created_at else "",
                }
                for t in rows
            ],
            "total": total,
        }
