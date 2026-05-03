import pytest


def test_validate_secrets_rejects_empty_without_insecure_flag(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("MODSTORE_JWT_SECRET", raising=False)
    monkeypatch.delenv("MODSTORE_INSECURE_EMPTY_JWT", raising=False)
    from modstore_server.middleware_registry import _validate_production_secrets

    with pytest.raises(RuntimeError, match="MODSTORE_JWT_SECRET"):
        _validate_production_secrets()


def test_validate_secrets_allows_empty_with_insecure_flag(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("MODSTORE_JWT_SECRET", raising=False)
    monkeypatch.setenv("MODSTORE_INSECURE_EMPTY_JWT", "1")
    from modstore_server.middleware_registry import _validate_production_secrets

    _validate_production_secrets()
