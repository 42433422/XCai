"""Catalog application boundary."""

from __future__ import annotations

from typing import Any

from modstore_server import catalog_store


class CatalogApplicationService:
    def append_package(self, package: dict[str, Any]) -> dict[str, Any]:
        return catalog_store.append_package(package)
