"""Mod AI 脚手架：LLM 生成 manifest + zip 导入（供 /api/mods/ai-scaffold 与工作台编排复用）。"""

from __future__ import annotations

import json
import py_compile
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from modman.repo_config import load_config, resolved_library
from modman.store import import_zip
from modstore_server.llm_chat_proxy import chat_dispatch
from modstore_server.llm_key_resolver import (
    KNOWN_PROVIDERS,
    OAI_COMPAT_OPENAI_STYLE_PROVIDERS,
    resolve_api_key,
    resolve_base_url,
)
from modstore_server.employee_ai_scaffold import (
    SYSTEM_PROMPT_EMPLOYEE,
    build_employee_pack_zip,
    parse_employee_pack_llm_json,
)
from modstore_server.mod_ai_scaffold import (
    SYSTEM_PROMPT,
    build_scaffold_zip,
    normalize_mod_id,
    parse_llm_manifest_json,
)
from modstore_server.models import User, add_user_mod


def modstore_library_path() -> Path:
    p = resolved_library(load_config())
    p.mkdir(parents=True, exist_ok=True)
    return p


def mod_compileall_warnings(mod_dir: Path) -> List[str]:
    """对 Mod 下 backend 内 .py 做语法编译检查；失败仅作警告列表，不删 Mod。"""
    backend = mod_dir / "backend"
    if not backend.is_dir():
        return []
    out: List[str] = []
    for p in sorted(backend.rglob("*.py")):
        try:
            py_compile.compile(str(p), doraise=True)
        except py_compile.PyCompileError as e:
            rel = p.relative_to(mod_dir).as_posix()
            out.append(f"{rel}: {e.msg}")
        except OSError as e:
            rel = p.relative_to(mod_dir).as_posix()
            out.append(f"{rel}: {e}")
    return out


def resolve_llm_provider_model(
    db: Session,
    user: User,
    provider: Optional[str],
    model: Optional[str],
) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """
    返回 (provider, model, error_message)。
    若 body 未传 provider/model，则读用户 default_llm_json。
    """
    prov = (provider or "").strip()
    mdl = (model or "").strip()
    if prov and mdl:
        if prov not in KNOWN_PROVIDERS:
            return None, None, f"不支持的供应商: {prov}"
        return prov, mdl, None
    urow = db.query(User).filter(User.id == user.id).first()
    raw_pref = ((urow.default_llm_json if urow else None) or "").strip()
    prefs: Dict[str, Any] = {}
    if raw_pref:
        try:
            loaded = json.loads(raw_pref)
            if isinstance(loaded, dict):
                prefs = loaded
        except json.JSONDecodeError:
            prefs = {}
    prov = str(prefs.get("provider") or "").strip()
    mdl = str(prefs.get("model") or "").strip()
    if not prov or prov not in KNOWN_PROVIDERS or not mdl:
        return None, None, "请先在 LLM 设置中选择默认供应商与模型，或在请求中传入 provider 与 model"
    return prov, mdl, None


async def run_mod_ai_scaffold_async(
    db: Session,
    user: User,
    *,
    brief: str,
    suggested_id: Optional[str] = None,
    replace: bool = True,
    provider: Optional[str] = None,
    model: Optional[str] = None,
) -> Dict[str, Any]:
    """
    生成并导入 Mod。成功: {"ok": True, "id", "path", "manifest"}；
    失败: {"ok": False, "error": "..."}。
    """
    brief = (brief or "").strip()
    if len(brief) < 3:
        return {"ok": False, "error": "描述过短"}

    prov, mdl, err = resolve_llm_provider_model(db, user, provider, model)
    if err:
        return {"ok": False, "error": err}

    api_key, _ = resolve_api_key(db, user.id, prov)  # type: ignore[arg-type]
    if not api_key:
        return {"ok": False, "error": "该供应商未配置可用 API Key（平台或 BYOK）"}
    base = (
        resolve_base_url(db, user.id, prov)
        if prov in OAI_COMPAT_OPENAI_STYLE_PROVIDERS
        else None
    )

    user_lines = [brief]
    hint = normalize_mod_id(suggested_id or "")
    if hint:
        user_lines.append(f"作者希望的 manifest.id（若与描述不冲突可采用）: {hint}")
    msgs = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": "\n\n".join(user_lines)},
    ]
    result = await chat_dispatch(
        prov,
        api_key=api_key,
        base_url=base,
        model=mdl,
        messages=msgs,
        max_tokens=2048,
    )
    if not result.get("ok"):
        return {"ok": False, "error": result.get("error") or "upstream error"}

    manifest, perr = parse_llm_manifest_json(str(result.get("content") or ""))
    if perr or not manifest:
        return {"ok": False, "error": perr or "无法解析模型输出为 manifest"}

    mid = str(manifest.get("id") or "").strip()
    mname = str(manifest.get("name") or mid)
    lib = modstore_library_path()
    dest_path = lib / mid
    if dest_path.is_dir() and not replace:
        return {"ok": False, "error": f"Mod {mid} 已存在，请传 replace=true 覆盖或更换描述"}

    try:
        raw_zip = build_scaffold_zip(mid, mname, manifest)
    except FileNotFoundError as e:
        return {"ok": False, "error": str(e)}

    with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
        tmp.write(raw_zip)
        tmp_path = Path(tmp.name)
    try:
        dest = import_zip(tmp_path, lib, replace=replace)
    except (ValueError, FileExistsError) as e:
        return {"ok": False, "error": str(e)}
    finally:
        tmp_path.unlink(missing_ok=True)

    add_user_mod(user.id, dest.name)
    return {
        "ok": True,
        "id": dest.name,
        "path": str(dest),
        "manifest": manifest,
    }


async def run_employee_ai_scaffold_async(
    db: Session,
    user: User,
    *,
    brief: str,
    replace: bool = True,
    provider: Optional[str] = None,
    model: Optional[str] = None,
) -> Dict[str, Any]:
    """
    生成 employee_pack 并导入用户库。商店执行器仍读 CatalogItem；此处产物用于本地库与「员工制作」页继续上架。
    """
    brief = (brief or "").strip()
    if len(brief) < 3:
        return {"ok": False, "error": "描述过短"}

    prov, mdl, err = resolve_llm_provider_model(db, user, provider, model)
    if err:
        return {"ok": False, "error": err}

    api_key, _ = resolve_api_key(db, user.id, prov)  # type: ignore[arg-type]
    if not api_key:
        return {"ok": False, "error": "该供应商未配置可用 API Key（平台或 BYOK）"}
    base = (
        resolve_base_url(db, user.id, prov)
        if prov in OAI_COMPAT_OPENAI_STYLE_PROVIDERS
        else None
    )

    msgs = [
        {"role": "system", "content": SYSTEM_PROMPT_EMPLOYEE},
        {"role": "user", "content": brief},
    ]
    result = await chat_dispatch(
        prov,
        api_key=api_key,
        base_url=base,
        model=mdl,
        messages=msgs,
        max_tokens=2048,
    )
    if not result.get("ok"):
        return {"ok": False, "error": result.get("error") or "upstream error"}

    manifest, perr = parse_employee_pack_llm_json(str(result.get("content") or ""))
    if perr or not manifest:
        return {"ok": False, "error": perr or "无法解析模型输出"}

    pid = str(manifest.get("id") or "").strip()
    lib = modstore_library_path()
    if (lib / pid).is_dir() and not replace:
        return {"ok": False, "error": f"包 {pid} 已存在，请传 replace=true 覆盖"}

    raw_zip = build_employee_pack_zip(pid, manifest)
    with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
        tmp.write(raw_zip)
        tmp_path = Path(tmp.name)
    try:
        dest = import_zip(tmp_path, lib, replace=replace)
    except (ValueError, FileExistsError) as e:
        return {"ok": False, "error": str(e)}
    finally:
        tmp_path.unlink(missing_ok=True)

    add_user_mod(user.id, dest.name)
    return {
        "ok": True,
        "id": dest.name,
        "path": str(dest),
        "manifest": manifest,
    }
