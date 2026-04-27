# MODstore 商业闭环实现计划

## 背景

MODstore 当前基础设施完善（认证、支付、市场、工作流编排、LLM 集成均已具备），但存在 4 个核心缺口导致业务无法闭环：

1. **AI 员工执行器是模拟的** — 用户购买员工后无法真正运行
2. **支付后权益未发放** — 无套餐配额系统，购买后功能未解锁
3. **员工配置 V2 未运行时解析** — perception/memory/cognition/actions 定义了但未执行
4. **工作流真实执行未打通** — 员工节点调用模拟器，无真实业务产出

本计划按优先级分 4 个阶段实现商业闭环。

---

## 阶段一：支付权益与配额系统（P0，商业模式基础）

**目标**：用户购买套餐/员工后，权益真正到账，平台能控制功能使用权限。

### 1.1 数据库模型扩展

新增以下表（SQLAlchemy 模型）：

- `UserPlan` — 用户当前生效套餐
  - `user_id`, `plan_id`, `started_at`, `expires_at`, `is_active`
- `Quota` — 用户资源配额
  - `user_id`, `quota_type` (employee_count/llm_calls/storage_mb), `total`, `used`, `reset_at`
- `Entitlement` — 用户已购权益明细
  - `user_id`, `catalog_id`, `entitlement_type` (plan/employee/mod), `granted_at`, `expires_at`

### 1.2 支付后权益发放

修改 `payment_api.py` 的 `_fulfill_paid_order`：

- 购买套餐 (`plan_id`) → 写入 `UserPlan` + 初始化 `Quota`
- 购买员工包 (`item_id`) → 写入 `Entitlement` + 更新 `Quota`
- 钱包充值 → 保持现有逻辑（余额增加）

### 1.3 套餐定义数据库化

将 `DEFAULT_PLANS` 硬编码改为数据库表 `PlanTemplate`：

- `id`, `name`, `price`, `features_json`, `quotas_json`
- 启动时自动初始化默认套餐

### 1.4 配额检查中间件

新增 `quota_middleware.py`：

- 创建员工前检查 `employee_count` 配额
- 调用 LLM 前检查 `llm_calls` 配额
- 上传文件前检查 `storage_mb` 配额

### 1.5 前端权益展示

- `MyStoreView.vue` 显示当前套餐、剩余配额
- `WalletView.vue` 增加「我的套餐」卡片

---

## 阶段二：AI 员工真实执行引擎（P0，产品核心价值）

**目标**：员工包下载后，能根据 `employee_config_v2` 真正执行业务逻辑。

### 2.1 员工包运行时加载器

新增 `employee_runtime.py`：

- `load_employee_pack(pack_id)` — 从 catalog 或本地加载员工包 zip
- `parse_employee_config_v2(manifest)` — 解析 V2 配置为运行时对象
- `build_employee_context(employee_id, input_data)` — 构建员工执行上下文

### 2.2 配置 V2 模块执行器

按 `employee_config_v2` 结构实现各模块：

- **Perception（感知）** — 解析输入数据格式（Excel/文本/图片）
  - 集成 `openpyxl` / `pandas` 处理 Excel
  - 集成 OCR 接口处理图片
- **Memory（记忆）** — 上下文/session 管理
  - 短期记忆：当前会话上下文
  - 长期记忆：用户偏好/历史记录（SQLite/JSON 存储）
- **Cognition（认知）** — LLM 调用与推理
  - 复用现有 `llm_chat_proxy.py`
  - 根据配置中的 `system_prompt` / `reasoning_mode` 构造请求
- **Actions（行动）** — 工具调用与外部集成
  - 微信通知 → 调用微信 API
  - 标签打印 → 生成 PDF/图片
  - 数据同步 → 调用外部系统接口

### 2.3 员工任务执行管道

重构 `employee_executor.py`：

```python
def execute_employee_task(employee_id, task, input_data):
    # 1. 加载员工包
    pack = load_employee_pack(employee_id)
    # 2. 解析配置
    config = parse_employee_config_v2(pack.manifest)
    # 3. 感知 → 认知 → 行动
    perceived = perception_module.run(config.perception, input_data)
    context = memory_module.load(config.memory, employee_id)
    reasoning = cognition_module.run(config.cognition, perceived, context)
    result = actions_module.run(config.actions, reasoning)
    # 4. 更新记忆
    memory_module.save(config.memory, employee_id, result)
    return result
```

### 2.4 员工包沙盒执行环境

- 使用 Docker 容器隔离员工执行（已有 `docker/mod-sandbox/` 基础）
- 限制网络访问、文件系统、CPU/内存
- 超时控制（默认 30 秒）

---

## 阶段三：工作流与员工深度集成（P1，自动化能力）

**目标**：工作流中的员工节点能调用真实执行引擎，实现端到端自动化。

### 3.1 工作流节点配置增强

扩展 `WorkflowNode.config` 结构：

```json
{
  "employee_id": "sz-qsm-pro-wechat_phone",
  "task": "notify_customer",
  "input_mapping": {
    "customer_phone": "{{nodes.prev.output.phone}}",
    "message_template": "订单{{order_id}}已发货"
  },
  "output_mapping": {
    "send_status": "{{result.status}}"
  },
  "timeout_seconds": 30,
  "retry_count": 2
}
```

### 3.2 工作流变量引擎

新增 `workflow_variables.py`：

- 节点间数据传递（`{{nodes.{id}.output.{key}}}`）
- 全局变量（`{{global.user_id}}`）
- 条件表达式求值（替换现有 `eval` 为安全表达式引擎）

### 3.3 员工节点真实执行

修改 `workflow_engine.py` 的 `_execute_employee_node`：

- 解析 `input_mapping` 构建输入数据
- 调用真实 `execute_employee_task`
- 解析 `output_mapping` 将结果写入工作流上下文
- 处理超时/重试/错误

### 3.4 工作流触发器

新增触发机制：

- **定时触发** — Cron 表达式（如每天 9:00 执行报表）
- **Webhook 触发** — 外部系统推送事件
- **事件触发** — 数据库变更/文件上传

---

## 阶段四：运营与体验完善（P2，商业成熟度）

### 4.1 部署状态监控

- `push`/`pull` 后查询 XCAGI 加载状态
- 员工包部署到 `_employees/` 后的健康检查
- 版本兼容性校验（manifest 版本 vs XCAGI 版本）

### 4.2 使用统计与计费

- 每个员工的调用次数、耗时、成功率
- LLM Token 使用量统计
- 按量计费基础数据

### 4.3 消息通知系统

- 支付成功/失败通知
- 员工执行完成通知
- 配额不足预警

### 4.4 退款与售后

- 退款申请接口（管理员审核）
- 权益回收机制
- 交易流水对账

---

## 实施顺序建议


| 周次    | 阶段     | 交付物                           |
| ----- | ------ | ----------------------------- |
| 第 1 周 | 阶段一    | 配额模型 + 权益发放 + 套餐数据库化          |
| 第 2 周 | 阶段二（上） | 员工包加载器 + Perception/Memory 模块 |
| 第 3 周 | 阶段二（下） | Cognition/Actions 模块 + 沙盒执行   |
| 第 4 周 | 阶段三    | 工作流变量引擎 + 员工节点真实执行            |
| 第 5 周 | 阶段四    | 监控/统计/通知/退款                   |


---

## 风险与依赖

1. **XCAGI 宿主接口** — 员工包部署后需要 XCAGI 正确加载，需确认宿主侧加载协议
2. **LLM 成本** — 真实执行会产生 Token 费用，需做好配额控制和成本监控
3. **沙盒安全** — 用户上传的员工包可能包含恶意代码，沙盒隔离必须严格
4. **数据隐私** — 员工处理的用户数据（Excel/图片）需符合隐私法规

---

## 验收标准

- 用户购买套餐后，前端显示套餐权益和剩余配额
- 用户购买员工包后，能在「我的商店」下载并运行
- 员工执行真实业务（如解析 Excel 并返回结构化数据）
- 工作流编排后执行，员工节点产生真实输出
- 配额耗尽后，前端提示升级套餐，后端拒绝超限操作
- 支付全流程（下单 → 支付 → 权益到账 → 使用）端到端可验证

