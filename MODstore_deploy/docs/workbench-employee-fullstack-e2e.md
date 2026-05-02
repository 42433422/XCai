# 「做员工」类 C 全链路联调清单（MODstore + FHD）

本文对应已实现能力：**employee_pack** 含 `manifest.workflow_employees`、`backend/blueprints.py` + `backend/employees/<stem>.py`、`employee_config_v2`、可选 `xcagi_host_profile`；工作台可选 **pack_plus_workflow** 与 **FHD 根 URL 探测**。

---

## 1. MODstore 侧

1. 二档「做员工」→ 完成需求规划 → 制作草稿。
2. 在草稿中选择 **员工包模式**：
   - **仅员工包**：不创建画布工作流，工作流沙箱步骤为跳过说明。
   - **员工包 + 画布工作流**：编排中调用 NL 生图并写回 `manifest.workflow_employees[0].workflow_id`。
3. 可选填写 **FHD 根 URL**（如 `http://127.0.0.1:8000`），编排末尾对 `GET {base}/api/mods/` 做连通性探测（失败不阻断成功，写入 `artifact.host_probe`）。
4. 成功后检查 `artifact.pack_id`、`artifact.workflow_attachment`（pack_plus 时）、`artifact.host_probe`。

---

## 2. FHD 侧

1. 将生成的 zip 安装到 `mods/_employees/<pack_id>/`（与既有安装器一致）。
2. **重启或触发**宿主加载路由：`load_mod_routes` 会调用 `load_employee_pack_routes`，为带 `backend.entry` 的包挂载 `/api/mod/<pack_id>/employees/...`。
3. 调用 **`GET /api/mods/employee-packs/{pack_id}/config-preview`** 确认 `employee_config_v2` 摘要可读。
4. 调用 **`POST /api/mod/<pack_id>/employees/<employee_id>/run`**（body 任意 JSON）验证 `run` 与宿主 `mod_employee_complete` 注入。
5. 打开宿主前端 **/api/mods/** 列表：应出现 `type: employee_pack`，且 `workflow_employees` 首条含副窗所需 `id` / `label`；若 manifest 含 `xcagi_host_profile.workflow_employee_row`，字段会合并进该行。

---

## 3. 已知边界

- **内置四类轨道**（`label_print` 等）的完整业务链仍依赖宿主已实现逻辑；`xcagi_host_profile.builtin_track_id` 仅做契约与白名单校验。
- 宿主 **get_mod_detail** 仍只解析已注册 Mod；员工包详情以 `config-preview` 与磁盘 manifest 为准。

---

*与 [fhd-employee-composition.md](fhd-employee-composition.md)、[workbench-employee-impl-flow.md](workbench-employee-impl-flow.md) 交叉阅读。*
