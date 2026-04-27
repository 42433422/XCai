"""Regression test for the frontend / API gateway treatment in
``docs/FRONTEND_AND_GATEWAY_ROADMAP.md``.

These checks make sure nobody silently reintroduces a duplicate Vite config or
moves the static market dist somewhere FastAPI no longer serves.
"""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
MARKET = REPO_ROOT / "market"
APP_PY = REPO_ROOT / "modstore_server" / "app.py"


def test_only_one_vite_config_exists():
    ts_config = MARKET / "vite.config.ts"
    js_config = MARKET / "vite.config.js"
    assert ts_config.is_file(), "vite.config.ts must remain the canonical config"
    assert not js_config.is_file(), (
        "vite.config.js was removed in the frontend/gateway cleanup; do not "
        "re-add it. See docs/FRONTEND_AND_GATEWAY_ROADMAP.md §1."
    )


def test_package_json_build_script_pins_vite():
    import json

    pkg = json.loads((MARKET / "package.json").read_text(encoding="utf-8"))
    assert pkg["scripts"]["build"] == "vite build"
    assert pkg["scripts"]["test:coverage"].startswith("vitest run --coverage")


def test_app_py_keeps_market_dist_as_single_source():
    if not APP_PY.is_file():
        pytest.skip("app.py not present in this checkout")
    text = APP_PY.read_text(encoding="utf-8")
    assert (
        "_MARKET_DIST = Path(__file__).resolve().parent.parent / \"market\" / \"dist\""
        in text
    ), (
        "FastAPI must keep MODstore_deploy/market/dist as the single static "
        "source per docs/FRONTEND_AND_GATEWAY_ROADMAP.md §1"
    )


def test_payment_gateway_proxy_remains_in_python_until_gateway_decision():
    """The independent API Gateway is intentionally deferred. Until that ADR
    lands, the FastAPI middleware MUST keep handling proxying to Java itself.
    """

    text = APP_PY.read_text(encoding="utf-8")
    assert "_proxy_to_java_payment" in text
    assert "PaymentGatewayService" in text


def test_roadmap_doc_exists_and_records_decisions():
    doc = (REPO_ROOT / "docs" / "FRONTEND_AND_GATEWAY_ROADMAP.md").read_text(encoding="utf-8")
    for must_contain in (
        "vite.config.ts",
        "MARKET",
        "API Gateway",
        "PAYMENT_BACKEND=java",
    ):
        assert must_contain in doc, (
            f"frontend/gateway roadmap doc must keep '{must_contain}' as a "
            "discoverable reference; do not delete the section that mentions it"
        )
