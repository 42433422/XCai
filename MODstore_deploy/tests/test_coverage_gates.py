"""Regression tests for the cross-stack coverage gates.

These tests fail loudly if someone removes the 80% gate on the critical
payment modules, lowers the existing floors, or drops the JaCoCo / Vitest
``check`` configurations. The intent is to keep ratcheting up; we never want
the gates to silently disappear.
"""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
WORKFLOW = REPO_ROOT.parent / ".github" / "workflows" / "deploy.yml"


def _read(path: Path) -> str:
    if not path.is_file():
        pytest.skip(f"{path} not present in this checkout")
    return path.read_text(encoding="utf-8")


def test_pyproject_declares_coverage_target():
    pyproject = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert "[tool.coverage.report]" in pyproject
    assert "fail_under = 80" in pyproject, "Pyproject must declare the 80% coverage target"


def test_deploy_workflow_runs_python_coverage_with_floor():
    text = _read(WORKFLOW)
    assert "pytest --cov=modstore_server --cov=modman" in text
    assert "MODSTORE_PY_COVERAGE_FLOOR" in text
    assert "--cov-fail-under" in text


def test_deploy_workflow_enforces_critical_modules_at_80():
    text = _read(WORKFLOW)
    assert "coverage report --fail-under=80" in text
    for module in (
        "modstore_server/payment_orders.py",
        "modstore_server/payment_contract.py",
        "modstore_server/application/payment_gateway.py",
        "modstore_server/eventing/contracts.py",
        "modstore_server/webhook_dispatcher.py",
        "modstore_server/webhook_api.py",
    ):
        assert module in text, f"deploy.yml dropped critical-module gate for {module!r}"


def test_deploy_workflow_runs_java_verify():
    text = _read(WORKFLOW)
    assert "mvn -B verify" in text, (
        "Java step must run ``mvn verify`` so JaCoCo check rules are enforced"
    )


def test_deploy_workflow_runs_frontend_coverage():
    text = _read(WORKFLOW)
    assert "npm run test:coverage" in text
    assert "npm test\n" not in text, (
        "Frontend step must run npm run test:coverage, not bare npm test"
    )


def test_pom_declares_jacoco_check_rule():
    pom = _read(REPO_ROOT / "java_payment_service" / "pom.xml")
    assert "<id>jacoco-check</id>" in pom
    assert "<goal>check</goal>" in pom
    assert "<counter>LINE</counter>" in pom
    assert "<counter>BRANCH</counter>" in pom
    assert "${jacoco.line.coverage}" in pom


def test_vite_config_enforces_payment_api_at_80():
    text = _read(REPO_ROOT / "market" / "vite.config.ts")
    assert "thresholds" in text
    assert "src/application/paymentApi.ts" in text, (
        "vite.config.ts must keep a per-file 80% gate on the payment API client"
    )
    assert "lines: 80" in text, (
        "vite.config.ts must enforce 80% lines on the payment API client"
    )
