# MODstore 关键安全与生产就绪修复 Spec

## Why

深度审计发现 MODstore 存在严重安全缺陷：硬编码弱密钥回退值、无安全响应头、无 CSRF 防护、无 XSS 净化、无 HTTP 限流、无数据库迁移管理、无缓存层、无结构化日志。这些问题不修复，系统在生产环境中处于裸奔状态。

## What Changes

- 移除所有硬编码弱密钥回退值，添加生产环境启动时密钥强度校验
- 添加安全响应头中间件
- 添加 CSRF 防护中间件（对 cookie 认证端点）
- 添加全局 XSS 输入净化中间件
- 添加安全审计日志模块
- 引入 Alembic 数据库迁移管理
- 添加 Redis 缓存层
- 添加 HTTP 请求限流中间件
- 添加结构化 JSON 日志
- 完善数据库连接池配置

## Impact

- Affected code: `modstore_server/auth_service.py`, `modstore_server/api/middleware.py`, `modstore_server/app.py`, `modstore_server/infrastructure/db.py`, `modstore_server/models.py`, 新增多个模块

## ADDED Requirements

### Requirement: 启动时密钥强度校验
系统 SHALL 在生产环境启动时校验所有关键密钥的强度，弱密钥或默认密钥 SHALL 导致启动失败。

#### Scenario: 生产环境使用弱密钥
- **WHEN** 系统以生产模式启动且 JWT_SECRET 为默认值或长度不足 32 字符
- **THEN** 系统拒绝启动并输出明确错误信息

#### Scenario: 开发环境使用弱密钥
- **WHEN** 系统以开发模式启动且使用弱密钥
- **THEN** 系统输出警告但允许启动

---

### Requirement: 安全响应头
系统 SHALL 在所有 HTTP 响应中自动添加安全响应头。

#### Scenario: 所有响应包含安全头
- **WHEN** 客户端发送任意 HTTP 请求
- **THEN** 响应包含 `X-Content-Type-Options: nosniff`、`X-Frame-Options: DENY`、`Referrer-Policy: strict-origin-when-cross-origin`

---

### Requirement: CSRF 防护
系统 SHALL 对使用 cookie 认证的端点实施 CSRF 防护。

#### Scenario: 无 CSRF token 的 POST 请求
- **WHEN** 客户端发送 POST/PUT/DELETE 请求且使用 cookie 认证但无 CSRF token
- **THEN** 系统返回 403 Forbidden

#### Scenario: Bearer token 认证豁免
- **WHEN** 客户端使用 Authorization: Bearer 头认证
- **THEN** 不要求 CSRF token

---

### Requirement: XSS 输入净化
系统 SHALL 对用户提交的字符串输入进行 XSS 净化。

#### Scenario: 包含 script 标签的输入
- **WHEN** 用户提交包含 `<script>alert('xss')</script>` 的输入
- **THEN** 系统净化为安全文本

---

### Requirement: 安全审计日志
系统 SHALL 记录所有安全关键操作的审计日志。

#### Scenario: 用户登录
- **WHEN** 用户成功或失败登录
- **THEN** 系统记录审计日志（用户ID、IP、时间、成功/失败）

---

### Requirement: 数据库迁移管理
系统 SHALL 使用 Alembic 管理数据库 schema 版本化迁移。

#### Scenario: 执行迁移
- **WHEN** 运行 `alembic upgrade head`
- **THEN** 数据库 schema 更新到最新版本

#### Scenario: 回滚迁移
- **WHEN** 运行 `alembic downgrade -1`
- **THEN** 数据库 schema 回滚到上一个版本

---

### Requirement: HTTP 限流
系统 SHALL 对 API 请求实施限流防护。

#### Scenario: 超出限流阈值
- **WHEN** 同一 IP 在 1 分钟内发送超过 60 次请求
- **THEN** 系统返回 429 Too Many Requests

---

### Requirement: 结构化 JSON 日志
系统 SHALL 输出 JSON 格式的结构化日志。

#### Scenario: 日志输出格式
- **WHEN** 任何模块记录日志
- **THEN** 输出 JSON 格式，包含 timestamp, level, message, request_id, module 字段

---

### Requirement: Redis 缓存层
系统 SHALL 实现 Redis 缓存层以减轻数据库压力。

#### Scenario: 缓存命中
- **WHEN** 请求的数据在 Redis 缓存中存在且未过期
- **THEN** 直接从缓存返回，不查询数据库

## MODIFIED Requirements

### Requirement: auth_service.py 密钥管理
**MODIFIED**: 移除硬编码弱密钥回退值

**变更**:
- 移除 `JWT_SECRET` 的 `"modstore-dev-secret-change-in-prod"` 默认值
- 改为从环境变量读取，缺失时生产环境拒绝启动

## REMOVED Requirements

### Requirement: 硬编码弱密钥回退值
**Reason**: 安全风险极高
**Migration**: 移除所有硬编码回退值，改为从环境变量读取
