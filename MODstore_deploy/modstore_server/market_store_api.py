"""XC AGI 在线市场 API：购买、下载、我的商店。"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from modstore_server.models import (
    CatalogItem,
    Entitlement,
    Purchase,
    Transaction,
    User,
    Wallet,
    get_session_factory,
)
from modstore_server.market_shared import (
    _catalog_item_payload,
    _get_current_user,
    _grant_catalog_entitlement,
)

router = APIRouter(tags=["market"])


class BuyDTO(BaseModel):
    pass


@router.post("/market/catalog/{item_id}/buy")
def api_buy_item(item_id: int, user: User = Depends(_get_current_user)):
    sf = get_session_factory()
    with sf() as session:
        item = session.query(CatalogItem).filter(CatalogItem.id == item_id).first()
        if not item:
            raise HTTPException(404, "商品不存在")
        if not item.is_public or (getattr(item, "compliance_status", "") or "") == "delisted":
            raise HTTPException(403, "该商品已下架，无法购买")
        if item.price <= 0:
            existing = (
                session.query(Purchase)
                .filter(Purchase.user_id == user.id, Purchase.catalog_id == item.id)
                .first()
            )
            if existing:
                return {"ok": True, "message": "已拥有"}
            purchase = Purchase(user_id=user.id, catalog_id=item.id, amount=0)
            session.add(purchase)
            _grant_catalog_entitlement(session, user_id=user.id, item=item, source="free_claim")
            session.commit()
            return {"ok": True, "message": "免费领取成功"}

        existing = (
            session.query(Purchase)
            .filter(Purchase.user_id == user.id, Purchase.catalog_id == item.id)
            .first()
        )
        if existing:
            return {"ok": True, "message": "已拥有"}

        wallet = session.query(Wallet).filter(Wallet.user_id == user.id).with_for_update().first()
        if not wallet:
            session.add(Wallet(user_id=user.id, balance=0.0))
            session.flush()
            wallet = (
                session.query(Wallet).filter(Wallet.user_id == user.id).with_for_update().first()
            )
        if not wallet or wallet.balance < item.price:
            raise HTTPException(
                402, f"余额不足，需要 ¥{item.price}，当前 ¥{wallet.balance if wallet else 0}"
            )

        wallet.balance -= item.price
        wallet.updated_at = datetime.now(timezone.utc)
        purchase = Purchase(user_id=user.id, catalog_id=item.id, amount=item.price)
        txn = Transaction(
            user_id=user.id,
            amount=-item.price,
            txn_type="purchase",
            status="completed",
            description=f"购买 {item.name} ({item.pkg_id})",
        )
        session.add(purchase)
        session.add(txn)
        _grant_catalog_entitlement(session, user_id=user.id, item=item, source="wallet")
        session.commit()
        return {"ok": True, "message": "购买成功", "new_balance": wallet.balance}


@router.get("/market/catalog/{item_id}/download")
def api_download_item(item_id: int, user: User = Depends(_get_current_user)):
    sf = get_session_factory()
    with sf() as session:
        item = session.query(CatalogItem).filter(CatalogItem.id == item_id).first()
        if not item:
            raise HTTPException(404, "商品不存在")
        if not item.is_public or (getattr(item, "compliance_status", "") or "") == "delisted":
            raise HTTPException(403, "该商品已下架，无法下载")
        ent = (
            session.query(Entitlement)
            .filter(
                Entitlement.user_id == user.id,
                Entitlement.catalog_id == item.id,
                Entitlement.is_active == True,
            )
            .first()
        )
        purchased = (
            session.query(Purchase)
            .filter(Purchase.user_id == user.id, Purchase.catalog_id == item.id)
            .first()
        )
        if item.price > 0 and not ent and not purchased:
            raise HTTPException(403, "未购买此商品，请先购买后下载")
        if item.price <= 0 and not ent and not purchased:
            _grant_catalog_entitlement(session, user_id=user.id, item=item, source="free_download")
            session.commit()
        if not item.stored_filename:
            raise HTTPException(404, "该商品无文件可下载")
        from modstore_server.catalog_store import files_dir
        from fastapi.responses import StreamingResponse

        path = files_dir() / item.stored_filename
        if not path.is_file():
            raise HTTPException(404, "文件缺失")

        def generate():
            with open(path, "rb") as f:
                while chunk := f.read(8192):
                    yield chunk

        return StreamingResponse(
            generate(),
            media_type="application/zip",
            headers={
                "Content-Disposition": f"attachment; filename={item.pkg_id}.zip",
                "Content-Length": str(path.stat().st_size),
            },
        )


@router.get("/my-store")
def api_my_store(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user: User = Depends(_get_current_user),
):
    sf = get_session_factory()
    with sf() as session:
        total = session.query(Purchase).filter(Purchase.user_id == user.id).count()
        rows = (
            session.query(Purchase)
            .filter(Purchase.user_id == user.id)
            .order_by(Purchase.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )
        items = []
        for p in rows:
            item = session.query(CatalogItem).filter(CatalogItem.id == p.catalog_id).first()
            if item:
                items.append(
                    {
                        "purchase_id": p.id,
                        "catalog_id": item.id,
                        "pkg_id": item.pkg_id,
                        "version": item.version,
                        "name": item.name,
                        "artifact": item.artifact or "mod",
                        "price_paid": p.amount,
                        "purchased_at": p.created_at.isoformat() if p.created_at else "",
                    }
                )
        return {"items": items, "total": total}
