"""Health check routes."""

from __future__ import annotations

from fastapi import APIRouter

from modstore_server.api.dto import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/api/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(ok=True)
