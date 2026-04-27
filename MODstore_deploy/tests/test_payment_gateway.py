from starlette.requests import Request


def _request(path: str) -> Request:
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": path,
            "headers": [],
            "query_string": b"",
        }
    )


def test_payment_backend_java_intercepts_payment_and_wallet(monkeypatch):
    from modstore_server import app as app_module

    monkeypatch.setenv("PAYMENT_BACKEND", "java")

    assert app_module._payment_backend_is_java(_request("/api/payment/plans"))
    assert app_module._payment_backend_is_java(_request("/api/wallet/balance"))
    assert not app_module._payment_backend_is_java(_request("/api/market/catalog"))


def test_payment_backend_defaults_to_python(monkeypatch):
    from modstore_server import app as app_module

    monkeypatch.delenv("PAYMENT_BACKEND", raising=False)

    assert not app_module._payment_backend_is_java(_request("/api/payment/plans"))
