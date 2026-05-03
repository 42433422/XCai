from __future__ import annotations

import logging
from typing import Any

import httpx
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from modstore_server.api.auth_deps import require_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/sandbox", tags=["sandbox"])

_CONNECT_TIMEOUT = 6.0
_READ_TIMEOUT = 10.0


class ConnectRequest(BaseModel):
    host_url: str


class PushAndTestRequest(BaseModel):
    host_url: str
    mod_id: str


def _normalize_url(raw: str) -> str:
    return raw.strip().rstrip("/")


@router.post("/connect")
def api_sandbox_connect(body: ConnectRequest, _user=Depends(require_user)):
    url = _normalize_url(body.host_url)
    try:
        with httpx.Client(timeout=(_CONNECT_TIMEOUT, _READ_TIMEOUT)) as client:
            health = client.get(f"{url}/api/health")
            health.raise_for_status()
            health_data = health.json()
    except Exception as exc:
        logger.warning("sandbox connect failed: %s", exc)
        return {"ok": False, "error": str(exc)}

    mods_info: dict[str, Any] = {}
    try:
        with httpx.Client(timeout=(_CONNECT_TIMEOUT, _READ_TIMEOUT)) as client:
            resp = client.get(f"{url}/api/mods/loading-status")
            if resp.status_code == 200:
                mods_info = resp.json()
    except Exception:
        pass

    return {
        "ok": True,
        "host_url": url,
        "health": health_data,
        "mods": mods_info,
    }


@router.post("/push-and-test")
def api_sandbox_push_and_test(body: PushAndTestRequest, _user=Depends(require_user)):
    url = _normalize_url(body.host_url)
    mod_id = body.mod_id.strip()

    from modstore_server.infrastructure import library_paths

    lib = library_paths.lib()
    mod_dir = lib / mod_id
    if not mod_dir.is_dir():
        return {"ok": False, "error": f"Mod '{mod_id}' not found in library"}

    import zipfile
    import tempfile
    import os

    with tempfile.TemporaryDirectory() as tmp:
        zip_path = os.path.join(tmp, f"{mod_id}.xcmod")
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for root, _dirs, files in os.walk(str(mod_dir)):
                for fname in files:
                    full = os.path.join(root, fname)
                    arcname = os.path.relpath(full, str(mod_dir))
                    zf.write(full, arcname)

        try:
            with httpx.Client(timeout=(_CONNECT_TIMEOUT, 30.0)) as client:
                with open(zip_path, "rb") as f:
                    resp = client.post(
                        f"{url}/api/mod-store/install",
                        files={"file": (f"{mod_id}.xcmod", f, "application/zip")},
                    )
                resp.raise_for_status()
                install_data = resp.json()
        except Exception as exc:
            logger.warning("sandbox push failed: %s", exc)
            return {"ok": False, "error": str(exc)}

    return {
        "ok": True,
        "mod_id": mod_id,
        "install": install_data,
        "sandbox_url": f"{url}/?sandbox=1",
    }


@router.get("/host-status")
def api_sandbox_host_status(_user=Depends(require_user)):
    from modstore_server.infrastructure import library_paths

    cfg = library_paths.cfg()
    backend_url = cfg.get("xcagi_backend_url", "")
    if not backend_url:
        return {"ok": False, "error": "xcagi_backend_url not configured"}

    url = _normalize_url(backend_url)
    try:
        with httpx.Client(timeout=(_CONNECT_TIMEOUT, _READ_TIMEOUT)) as client:
            resp = client.get(f"{url}/api/mods/loading-status")
            resp.raise_for_status()
            return {"ok": True, "data": resp.json()}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
