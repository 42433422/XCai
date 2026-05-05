"""
测试 AI 数字管家 Butler API。

运行：
    cd MODstore_deploy
    pytest tests/test_agent_butler_api.py -v
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient


# ─── Fixtures ────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def app():
    """创建 FastAPI app 实例（跳过数据库迁移，仅注册路由）。"""
    from fastapi import FastAPI
    from modstore_server.agent_butler_api import router

    test_app = FastAPI()
    test_app.include_router(router)
    return test_app


@pytest.fixture(scope="module")
def client(app):
    return TestClient(app)


@pytest.fixture()
def mock_user():
    user = MagicMock()
    user.id = 42
    user.is_admin = False
    user.default_llm_json = json.dumps({"provider": "openai", "model": "gpt-4o-mini"})
    return user


@pytest.fixture()
def mock_db():
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None
    db.add = MagicMock()
    db.commit = MagicMock()
    db.flush = MagicMock()
    return db


# ─── Helper ────────────────────────────────────────────────────────


def _auth_overrides(app, mock_user, mock_db):
    from modstore_server.api.deps import _get_current_user
    from modstore_server.infrastructure.db import get_db

    app.dependency_overrides[_get_current_user] = lambda: mock_user
    app.dependency_overrides[get_db] = lambda: mock_db
    return app


# ─── Tests: /actions ──────────────────────────────────────────────


class TestButlerActions:
    def test_record_action_ok(self, app, mock_user, mock_db):
        _auth_overrides(app, mock_user, mock_db)
        client = TestClient(app)
        resp = client.post(
            "/api/agent/butler/actions",
            json={"action": "navigate", "route": "/plans", "risk": "low", "status": "success"},
        )
        assert resp.status_code == 200
        assert resp.json().get("ok") is True

    def test_record_action_creates_db_entry(self, app, mock_user, mock_db):
        _auth_overrides(app, mock_user, mock_db)
        client = TestClient(app)
        client.post(
            "/api/agent/butler/actions",
            json={"action": "click", "route": "/wallet", "risk": "medium", "status": "success"},
        )
        # ButlerAction 应被添加
        mock_db.add.assert_called()
        mock_db.commit.assert_called()


# ─── Tests: /skills ───────────────────────────────────────────────


class TestButlerSkills:
    def test_list_skills_empty(self, app, mock_user, mock_db):
        _auth_overrides(app, mock_user, mock_db)
        client = TestClient(app)

        with patch("modstore_server.agent_butler_api.db") if False else patch.object(
            mock_db.query.return_value.filter.return_value, "all", return_value=[]
        ):
            resp = client.get("/api/agent/butler/skills")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data

    def test_update_skill_requires_admin(self, app, mock_user, mock_db):
        mock_user.is_admin = False
        _auth_overrides(app, mock_user, mock_db)
        client = TestClient(app)
        resp = client.patch("/api/agent/butler/skills/1", json={"is_active": True})
        assert resp.status_code == 403

    def test_update_skill_ok_for_admin(self, app, mock_user, mock_db):
        mock_user.is_admin = True
        skill_mock = MagicMock()
        skill_mock.id = 1
        mock_db.query.return_value.filter.return_value.first.return_value = skill_mock
        _auth_overrides(app, mock_user, mock_db)
        client = TestClient(app)
        resp = client.patch("/api/agent/butler/skills/1", json={"is_active": False})
        assert resp.status_code == 200
        assert resp.json().get("ok") is True


# ─── Tests: system prompt 注入 ─────────────────────────────────────


class TestButlerSystemPrompt:
    def test_butler_system_prompt_content(self):
        from modstore_server.agent_butler_api import BUTLER_SYSTEM_PROMPT

        assert "数字管家" in BUTLER_SYSTEM_PROMPT
        assert "低风险" in BUTLER_SYSTEM_PROMPT
        assert "高风险" in BUTLER_SYSTEM_PROMPT

    def test_butler_tools_has_navigate(self):
        from modstore_server.agent_butler_api import BUTLER_TOOLS

        tool_names = [t["function"]["name"] for t in BUTLER_TOOLS]
        assert "navigate" in tool_names
        assert "click" in tool_names
        assert "fill" in tool_names
        assert "read" in tool_names

    def test_build_messages_injects_system(self):
        from modstore_server.agent_butler_api import _build_messages, ButlerChatDTO, ButlerMessageDTO

        body = ButlerChatDTO(
            messages=[ButlerMessageDTO(role="user", content="你好")],
            page_context="当前页面: 首页",
        )
        msgs = _build_messages(body, body.page_context)
        assert msgs[0]["role"] == "system"
        assert "数字管家" in msgs[0]["content"]
        assert "当前页面: 首页" in msgs[0]["content"]
        assert any(m["role"] == "user" for m in msgs)


# ─── Tests: _safe_json ────────────────────────────────────────────


class TestSafeJson:
    def test_string_input(self):
        from modstore_server.agent_butler_api import _safe_json

        result = _safe_json('{"key": "val"}')
        assert result == {"key": "val"}

    def test_dict_input(self):
        from modstore_server.agent_butler_api import _safe_json

        result = _safe_json({"key": "val"})
        assert result == {"key": "val"}

    def test_invalid_json(self):
        from modstore_server.agent_butler_api import _safe_json

        result = _safe_json("invalid json {")
        assert result == {}
