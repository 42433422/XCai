from __future__ import annotations

import json

from modstore_server.mod_ai_scaffold import parse_llm_mod_suite_json
from modstore_server.mod_scaffold_runner import (
    run_mod_suite_mod_sandbox,
    write_mod_suite_industry_card,
    write_mod_suite_ui_shell,
)
from modstore_server.workbench_api import _default_steps


def _suite_payload() -> dict:
    return {
        "manifest": {
            "id": "manufacture-flow",
            "name": "制造协同",
            "version": "1.0.0",
            "description": "生产协同与库存管理",
        },
        "industry": {
            "name": "制造业",
            "scenario": "生产任务、库存和报表协同",
            "product_fields": {"name": "物料名称", "category": "物料分类"},
            "order_types": {"shipment": "发货单"},
        },
        "ui_shell": {
            "sidebar_menu": [
                {"key": "products", "label": "物料管理", "path": "/materials", "order": 20},
                {"key": "shipments", "label": "发货单记录", "path": "/shipments", "order": 40},
            ],
            "settings": {"industry_options": ["制造业"]},
            "make_scene": {"title": "制作制造协同", "description": "按制造流程生成可运行工作流。"},
        },
        "employees": [
            {
                "id": "inventory_planner",
                "label": "库存计划员",
                "panel_title": "库存协同",
                "panel_summary": "跟踪库存并输出补货建议",
                "workflow": {"name": "库存协同工作流", "description": "读取库存，判断缺口，输出建议。"},
            }
        ],
        "configs": {"reports": ["库存日报"]},
    }


def test_parse_mod_suite_json_extracts_wrapped_json():
    payload = _suite_payload()
    raw = "模型说明如下：\n```json\n" + json.dumps(payload, ensure_ascii=False) + "\n```\n请查收"
    parsed, err = parse_llm_mod_suite_json(raw)
    assert err == ""
    assert parsed
    assert parsed["manifest"]["id"] == "manufacture-flow"
    assert parsed["blueprint"]["industry"]["name"] == "制造业"
    assert parsed["manifest"]["industry"]["product_fields"]["name"] == "物料名称"
    assert parsed["manifest"]["frontend"]["menu_overrides"][0]["key"] in {"products", "shipments"}
    assert len(parsed["manifest"]["frontend"]["shell"]["sidebar_menu"]) >= 18
    assert parsed["blueprint"]["ui_shell"]["settings"]["industry_options"] == ["制造业"]
    assert parsed["employees"][0]["id"] == "inventory_planner"


def test_default_mod_steps_are_full_flow():
    ids = [s["id"] for s in _default_steps("mod")]
    assert ids == [
        "spec",
        "manifest",
        "repo",
        "industry",
        "employees",
        "employee_impls",
        "workflows",
        "register_packs",
        "api",
        "workflow_sandbox",
        "mod_sandbox",
        "complete",
    ]


def test_default_employee_steps_include_named_sandboxes():
    ids_pack = [s["id"] for s in _default_steps("employee", employee_target="pack_only")]
    assert ids_pack == [
        "spec",
        "generate",
        "validate",
        "workflow",
        "workflow_sandbox",
        "mod_sandbox",
        "host_check",
        "complete",
    ]
    ids_plus = [s["id"] for s in _default_steps("employee", employee_target="pack_plus_workflow")]
    assert ids_plus == ids_pack


def test_mod_suite_mod_sandbox_checks_manifest_blueprint_and_links(tmp_path):
    mod_dir = tmp_path / "manufacture-flow"
    (mod_dir / "backend").mkdir(parents=True)
    (mod_dir / "frontend").mkdir()
    (mod_dir / "config").mkdir()
    manifest = {
        "id": "manufacture-flow",
        "name": "制造协同",
        "version": "1.0.0",
        "backend": {"entry": "blueprints", "init": "mod_init"},
        "frontend": {"routes": "frontend/routes.js"},
        "workflow_employees": [{"id": "inventory_planner", "label": "库存计划员", "workflow_id": 123}],
    }
    (mod_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
    (mod_dir / "backend" / "__init__.py").write_text("", encoding="utf-8")
    (mod_dir / "backend" / "blueprints.py").write_text("def mod_init():\n    return None\n", encoding="utf-8")
    (mod_dir / "frontend" / "routes.js").write_text("export default []\n", encoding="utf-8")
    (mod_dir / "config" / "ai_blueprint.json").write_text("{}", encoding="utf-8")

    report = run_mod_suite_mod_sandbox(
        mod_dir,
        [{"workflow_id": 123, "employee_id": "inventory_planner"}],
    )
    assert report["ok"] is True
    assert {c["id"] for c in report["checks"]} >= {"manifest", "blueprint", "workflow_links", "python_compile"}


def test_mod_suite_writes_industry_card_and_ui_shell(tmp_path):
    parsed, err = parse_llm_mod_suite_json(json.dumps(_suite_payload(), ensure_ascii=False))
    assert err == ""
    mod_dir = tmp_path / "manufacture-flow"
    mod_dir.mkdir()

    industry_card = write_mod_suite_industry_card(mod_dir, parsed["blueprint"])
    ui_shell = write_mod_suite_ui_shell(mod_dir, parsed["blueprint"])

    assert industry_card["name"] == "制造业"
    assert industry_card["product_fields"]["name"] == "物料名称"
    assert ui_shell["target"] == "traditional-mode"
    assert any(item["label"] == "物料管理" for item in ui_shell["sidebar_menu"])
    assert (mod_dir / "config" / "industry_card.json").is_file()
    assert (mod_dir / "config" / "ui_shell.json").is_file()


def test_shell_ui_api_exposes_mod_sidebar_and_industries(client, library):
    mod_dir = library / "paint-mod"
    (mod_dir / "config").mkdir(parents=True)
    manifest = {
        "id": "paint-mod",
        "name": "涂料工坊",
        "version": "1.0.0",
        "primary": True,
        "backend": {"entry": "blueprints", "init": "mod_init"},
        "frontend": {
            "routes": "frontend/routes",
            "menu": [{"id": "paint-home", "label": "涂料工坊", "icon": "fa-cube", "path": "/paint-mod"}],
            "menu_overrides": [{"key": "products", "label": "配方管理"}],
        },
        "industry": {"name": "涂料/油漆行业", "scenario": "配方、批次与出货"},
        "config": {"industry_card": "config/industry_card.json", "ui_shell": "config/ui_shell.json"},
    }
    ui_shell = {
        "schema_version": 1,
        "target": "traditional-mode",
        "sidebar_menu": [{"key": "products", "label": "配方管理", "path": "/recipes", "visible": True, "order": 20}],
        "menu_overrides": [{"key": "products", "label": "配方管理"}],
        "settings": {"default_industry": "涂料/油漆行业", "industry_options": ["涂料/油漆行业"]},
        "make_scene": {"title": "制作涂料工坊", "description": "生成配方和出货工作流。"},
    }
    (mod_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
    (mod_dir / "config" / "industry_card.json").write_text(
        json.dumps({"schema_version": 1, "name": "涂料/油漆行业"}, ensure_ascii=False),
        encoding="utf-8",
    )
    (mod_dir / "config" / "ui_shell.json").write_text(json.dumps(ui_shell, ensure_ascii=False), encoding="utf-8")

    res = client.get("/api/mods/shell-ui?mod_id=paint-mod")

    assert res.status_code == 200
    data = res.json()
    assert data["selected_mod_id"] == "paint-mod"
    assert data["sidebar_menu"][0]["label"] == "配方管理"
    assert "涂料/油漆行业" in data["industry_options"]
