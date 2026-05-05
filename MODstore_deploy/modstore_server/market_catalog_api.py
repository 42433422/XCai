"""XC AGI 在线市场 API：目录浏览、搜索、评价、收藏、投诉。"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from modstore_server.models import (
    CatalogItem,
    Favorite,
    Purchase,
    Review,
    User,
    get_session_factory,
)
from modstore_server.models_catalog import CatalogComplaint
from modstore_server.market_shared import (
    _catalog_item_payload,
    _get_current_user,
    _normalize_license_scope,
    _normalize_material_category,
    _optional_current_user,
    _require_admin,
    LICENSE_SCOPE_LABELS,
    MATERIAL_CATEGORY_LABELS,
)

router = APIRouter(tags=["market"])


class ReviewSubmitDTO(BaseModel):
    rating: int = Field(..., ge=1, le=5)
    content: str = Field(default="", max_length=4000)


class CatalogComplaintSubmitDTO(BaseModel):
    complaint_type: str = Field(default="other", max_length=32)
    reason: str = Field(..., min_length=4, max_length=4000)
    evidence: Dict[str, Any] = Field(default_factory=dict)


class CatalogComplaintReviewDTO(BaseModel):
    action: str = Field(..., description="resolve/reject/downrank/delist/restore")
    admin_note: str = Field(default="", max_length=4000)
    rank_delta: float = Field(default=0.0)
    delist_reason: str = Field(default="", max_length=1000)


@router.get("/market/facets")
def api_market_facets():
    sf = get_session_factory()
    with sf() as session:
        pub = (CatalogItem.is_public == True) & (CatalogItem.compliance_status != "delisted")
        industries = sorted(
            {
                t[0]
                for t in session.query(CatalogItem.industry).filter(pub).distinct().all()
                if t[0]
            },
        )
        artifacts = sorted(
            {
                t[0]
                for t in session.query(CatalogItem.artifact).filter(pub).distinct().all()
                if t[0]
            },
        )
        security_levels = sorted(
            {
                t[0]
                for t in session.query(CatalogItem.security_level).filter(pub).distinct().all()
                if t[0]
            },
        )
        material_categories = sorted(
            {
                _normalize_material_category(cat, art)
                for cat, art in session.query(CatalogItem.material_category, CatalogItem.artifact)
                .filter(pub)
                .all()
                if _normalize_material_category(cat, art)
            },
        )
        license_scopes = sorted(
            {
                _normalize_license_scope(t[0], 0)
                for t in session.query(CatalogItem.license_scope).filter(pub).distinct().all()
                if _normalize_license_scope(t[0], 0)
            },
        )
        compliance_statuses = sorted(
            {
                t[0]
                for t in session.query(CatalogItem.compliance_status).filter(pub).distinct().all()
                if t[0]
            },
        )
        return {
            "industries": industries,
            "artifacts": artifacts,
            "material_categories": material_categories,
            "material_category_labels": MATERIAL_CATEGORY_LABELS,
            "license_scopes": license_scopes,
            "license_scope_labels": LICENSE_SCOPE_LABELS,
            "security_levels": security_levels,
            "compliance_statuses": compliance_statuses,
        }


@router.get("/market/catalog")
def api_market_catalog(
    q: Optional[str] = Query(None),
    artifact: Optional[str] = Query(None),
    material_category: Optional[str] = Query(None),
    industry: Optional[str] = Query(None),
    license_scope: Optional[str] = Query(None),
    security_level: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user: Optional[User] = Depends(_optional_current_user),
):
    sf = get_session_factory()
    with sf() as session:
        query = session.query(CatalogItem).filter(
            CatalogItem.is_public == True,
            CatalogItem.compliance_status != "delisted",
        )
        if q:
            ql = q.lower()
            query = query.filter(
                (CatalogItem.name.ilike(f"%{ql}%"))
                | (CatalogItem.pkg_id.ilike(f"%{ql}%"))
                | (CatalogItem.description.ilike(f"%{ql}%"))
            )
        if artifact:
            query = query.filter(CatalogItem.artifact == artifact)
        if material_category:
            mapped_artifacts = {
                "ai_employee": ["employee_pack"],
                "workflow_template": ["workflow_template"],
                "page_style": ["surface"],
                "mod_asset": ["mod", "bundle"],
            }.get(material_category, [])
            cond = CatalogItem.material_category == material_category
            if mapped_artifacts:
                cond = cond | (
                    (CatalogItem.material_category == "")
                    & (CatalogItem.artifact.in_(mapped_artifacts))
                )
            query = query.filter(cond)
        if industry:
            query = query.filter(CatalogItem.industry == industry)
        if license_scope:
            query = query.filter(CatalogItem.license_scope == license_scope)
        if security_level:
            query = query.filter(CatalogItem.security_level == security_level)
        total = query.count()
        rows = (
            query.order_by(CatalogItem.rank_score.desc(), CatalogItem.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

        purchased_ids = set()
        if user:
            purchased_rows = (
                session.query(Purchase.catalog_id).filter(Purchase.user_id == user.id).all()
            )
            purchased_ids = {r[0] for r in purchased_rows}

        complaint_counts: Dict[int, int] = {}
        if rows:
            ids = [r.id for r in rows]
            counts = (
                session.query(CatalogComplaint.catalog_id, CatalogComplaint.id)
                .filter(CatalogComplaint.catalog_id.in_(ids))
                .all()
            )
            for catalog_id, _ in counts:
                complaint_counts[int(catalog_id)] = complaint_counts.get(int(catalog_id), 0) + 1

        return {
            "items": [
                _catalog_item_payload(
                    r,
                    purchased=r.id in purchased_ids,
                    complaint_count=complaint_counts.get(int(r.id), 0),
                )
                for r in rows
            ],
            "total": total,
        }


@router.get("/market/catalog/{item_id}")
def api_market_catalog_detail(
    item_id: int,
    user: Optional[User] = Depends(_optional_current_user),
):
    sf = get_session_factory()
    with sf() as session:
        item = session.query(CatalogItem).filter(CatalogItem.id == item_id).first()
        if not item:
            raise HTTPException(404, "商品不存在")
        purchased = False
        favorited = False
        user_has_review = False
        if user:
            purchased = (
                session.query(Purchase)
                .filter(Purchase.user_id == user.id, Purchase.catalog_id == item.id)
                .first()
                is not None
            )
            favorited = (
                session.query(Favorite)
                .filter(Favorite.user_id == user.id, Favorite.catalog_id == item.id)
                .first()
                is not None
            )
            user_has_review = (
                session.query(Review)
                .filter(Review.user_id == user.id, Review.catalog_id == item.id)
                .first()
                is not None
            )
        complaint_count = (
            session.query(CatalogComplaint).filter(CatalogComplaint.catalog_id == item.id).count()
        )
        return _catalog_item_payload(
            item,
            purchased=purchased,
            favorited=favorited,
            user_has_review=user_has_review,
            complaint_count=complaint_count,
        )


@router.post("/market/catalog/{item_id}/review")
def api_submit_review(
    item_id: int,
    body: ReviewSubmitDTO,
    user: User = Depends(_get_current_user),
):
    from modstore_server.models import Entitlement

    sf = get_session_factory()
    with sf() as session:
        item = session.query(CatalogItem).filter(CatalogItem.id == item_id).first()
        if not item:
            raise HTTPException(404, "商品不存在")
        ent = (
            session.query(Entitlement)
            .filter(
                Entitlement.user_id == user.id,
                Entitlement.catalog_id == item_id,
                Entitlement.is_active == True,
            )
            .first()
        )
        purchase = (
            session.query(Purchase)
            .filter(Purchase.user_id == user.id, Purchase.catalog_id == item_id)
            .first()
        )
        if not ent and not purchase:
            raise HTTPException(403, "购买后方可评价")
        exists = (
            session.query(Review)
            .filter(Review.user_id == user.id, Review.catalog_id == item_id)
            .first()
        )
        if exists:
            raise HTTPException(400, "已评价过")
        session.add(
            Review(
                user_id=user.id,
                catalog_id=item_id,
                rating=int(body.rating),
                content=(body.content or "").strip(),
            )
        )
        session.commit()
    return {"ok": True}


@router.get("/market/catalog/{item_id}/reviews")
def api_catalog_reviews(item_id: int):
    sf = get_session_factory()
    with sf() as session:
        rows = (
            session.query(Review, User)
            .join(User, Review.user_id == User.id)
            .filter(Review.catalog_id == item_id)
            .order_by(Review.created_at.desc())
            .limit(50)
            .all()
        )
        revs = [
            {
                "id": r.id,
                "user_name": u.username,
                "rating": r.rating,
                "content": r.content or "",
                "created_at": r.created_at.isoformat() if r.created_at else "",
            }
            for r, u in rows
        ]
        avg = sum(x[0].rating for x in rows) / len(rows) if rows else 0.0
        return {"reviews": revs, "average_rating": round(avg, 2), "total": len(revs)}


@router.post("/market/catalog/{item_id}/favorite")
def api_toggle_favorite(item_id: int, user: User = Depends(_get_current_user)):
    sf = get_session_factory()
    with sf() as session:
        item = session.query(CatalogItem).filter(CatalogItem.id == item_id).first()
        if not item:
            raise HTTPException(404, "商品不存在")
        existing = (
            session.query(Favorite)
            .filter(Favorite.user_id == user.id, Favorite.catalog_id == item_id)
            .first()
        )
        if existing:
            session.delete(existing)
            session.commit()
            return {"ok": True, "favorited": False}
        session.add(Favorite(user_id=user.id, catalog_id=item_id))
        session.commit()
        return {"ok": True, "favorited": True}


@router.post("/market/catalog/{item_id}/complaints")
def api_submit_catalog_complaint(
    item_id: int,
    body: CatalogComplaintSubmitDTO,
    user: User = Depends(_get_current_user),
):
    sf = get_session_factory()
    with sf() as session:
        item = session.query(CatalogItem).filter(CatalogItem.id == item_id).first()
        if not item:
            raise HTTPException(404, "商品不存在")
        complaint_type = (body.complaint_type or "other").strip() or "other"
        row = CatalogComplaint(
            catalog_id=item.id,
            user_id=user.id,
            complaint_type=complaint_type,
            reason=(body.reason or "").strip(),
            evidence_json=json.dumps(body.evidence or {}, ensure_ascii=False),
            status="pending",
        )
        session.add(row)
        item.rank_score = max(0.0, float(getattr(item, "rank_score", 100.0) or 100.0) - 5.0)
        if (getattr(item, "compliance_status", "") or "approved") == "approved":
            item.compliance_status = "under_review"
        session.commit()
        session.refresh(row)
        return {
            "ok": True,
            "id": row.id,
            "status": row.status,
            "message": "投诉/申诉已提交，客服助手会继续引导补充材料",
        }


@router.get("/admin/catalog/complaints")
def api_admin_list_catalog_complaints(
    status: str = Query("", max_length=24),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user: User = Depends(_require_admin),
):
    sf = get_session_factory()
    with sf() as session:
        query = (
            session.query(CatalogComplaint, CatalogItem, User)
            .join(CatalogItem, CatalogComplaint.catalog_id == CatalogItem.id)
            .join(User, CatalogComplaint.user_id == User.id)
        )
        if status:
            query = query.filter(CatalogComplaint.status == status)
        total = query.count()
        rows = query.order_by(CatalogComplaint.created_at.desc()).offset(offset).limit(limit).all()
        return {
            "items": [
                {
                    "id": c.id,
                    "catalog_id": c.catalog_id,
                    "catalog_name": item.name,
                    "pkg_id": item.pkg_id,
                    "user_id": c.user_id,
                    "user_name": reporter.username,
                    "complaint_type": c.complaint_type,
                    "reason": c.reason,
                    "evidence": json.loads(c.evidence_json or "{}"),
                    "status": c.status,
                    "resolution": c.resolution,
                    "admin_note": c.admin_note,
                    "created_at": c.created_at.isoformat() if c.created_at else "",
                    "updated_at": c.updated_at.isoformat() if c.updated_at else "",
                }
                for c, item, reporter in rows
            ],
            "total": total,
        }


@router.post("/admin/catalog/complaints/{complaint_id}/review")
def api_admin_review_catalog_complaint(
    complaint_id: int,
    body: CatalogComplaintReviewDTO,
    user: User = Depends(_require_admin),
):
    action = (body.action or "").strip().lower()
    if action not in {"resolve", "reject", "downrank", "delist", "restore"}:
        raise HTTPException(400, "action 必须是 resolve/reject/downrank/delist/restore")
    sf = get_session_factory()
    with sf() as session:
        complaint = (
            session.query(CatalogComplaint).filter(CatalogComplaint.id == complaint_id).first()
        )
        if not complaint:
            raise HTTPException(404, "投诉/申诉不存在")
        item = session.query(CatalogItem).filter(CatalogItem.id == complaint.catalog_id).first()
        if not item:
            raise HTTPException(404, "商品不存在")

        now = datetime.utcnow()
        complaint.admin_id = user.id
        complaint.admin_note = (body.admin_note or "").strip()
        complaint.resolution = action
        complaint.updated_at = now

        if action == "reject":
            complaint.status = "rejected"
            item.compliance_status = "approved"
        elif action == "restore":
            complaint.status = "resolved"
            item.is_public = True
            item.compliance_status = "approved"
            item.delist_reason = ""
            item.rank_score = max(float(getattr(item, "rank_score", 100.0) or 0), 80.0)
        elif action == "delist":
            complaint.status = "resolved"
            item.is_public = False
            item.compliance_status = "delisted"
            item.delist_reason = (body.delist_reason or body.admin_note or "投诉处理下架").strip()
            item.rank_score = 0.0
        elif action == "downrank":
            complaint.status = "resolved"
            item.compliance_status = "restricted"
            delta = body.rank_delta if body.rank_delta > 0 else 30.0
            item.rank_score = max(
                0.0, float(getattr(item, "rank_score", 100.0) or 100.0) - float(delta)
            )
        else:
            complaint.status = "resolved"
            if item.compliance_status == "under_review":
                item.compliance_status = "approved"
        session.commit()
        return {
            "ok": True,
            "id": complaint.id,
            "status": complaint.status,
            "resolution": complaint.resolution,
        }
