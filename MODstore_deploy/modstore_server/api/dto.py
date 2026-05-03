"""Request/Response DTOs extracted from app.py for DDD layer separation."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ConfigDTO(BaseModel):
    library_root: str = ""
    xcagi_root: str = ""
    xcagi_backend_url: str = ""


class HealthResponse(BaseModel):
    ok: bool = True


class CreateModDTO(BaseModel):
    mod_id: str = Field(..., min_length=1, max_length=128)
    display_name: str = Field(..., min_length=1, max_length=256)


class ModAiScaffoldDTO(BaseModel):
    brief: str = Field(..., min_length=3, max_length=30000)
    suggested_id: str = Field("", max_length=64)
    replace: bool = True
    provider: Optional[str] = Field(None, max_length=64)
    model: Optional[str] = Field(None, max_length=128)


class FrontendRegenerateDTO(BaseModel):
    brief: str = Field("", max_length=8000)


class SyncDTO(BaseModel):
    mod_ids: Optional[List[str]] = None


class ManifestPutDTO(BaseModel):
    manifest: Dict[str, Any]


class ModFilePutDTO(BaseModel):
    path: str = Field(..., min_length=1)
    content: str = ""


class WorkflowEmployeeCatalogDTO(BaseModel):
    workflow_index: int = Field(0, ge=0)
    industry: str = Field("通用", max_length=64)
    price: float = Field(0, ge=0)
    release_channel: str = Field("stable", pattern="^(stable|draft)$")


class SandboxDTO(BaseModel):
    mod_id: str = Field(..., min_length=1)
    mode: str = Field(default="copy", pattern="^(copy|symlink)$")


class FocusPrimaryDTO(BaseModel):
    mod_id: str = Field(..., min_length=1)


class ExportFhdShellDTO(BaseModel):
    output_path: str = ""
