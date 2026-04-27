"""FastAPI app factory for the Neuro-DDD composition layer.

The current app is still assembled by the legacy ``modstore_server.app`` module.
This factory gives new deployment and tests a stable target while route groups
are migrated into ``modstore_server.api``.
"""

from __future__ import annotations

from fastapi import FastAPI


def create_app() -> FastAPI:
    from modstore_server.app import app

    return app


def get_app() -> FastAPI:
    return create_app()
