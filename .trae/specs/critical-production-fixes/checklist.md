# MODstore 关键修复检查清单

## 阶段 1: 严重安全修复

### 1.1 硬编码弱密钥移除

- [x] `auth_service.py` 中无 `"modstore-dev-secret-change-in-prod"` 回退值
- [x] 生产模式下弱密钥导致启动失败
- [x] 开发模式下弱密钥仅输出警告
- [x] `.env.example` 中无真实邮箱/密钥信息

### 1.2 安全响应头

- [x] 所有 HTTP 响应包含 `X-Content-Type-Options: nosniff`
- [x] 所有 HTTP 响应包含 `X-Frame-Options: DENY`
- [x] 所有 HTTP 响应包含 `Referrer-Policy: strict-origin-when-cross-origin`
- [x] HTTPS 响应包含 `Strict-Transport-Security`

### 1.3 CSRF 防护

- [x] POST/PUT/DELETE 请求使用 cookie 认证时要求 CSRF token
- [x] Bearer token 认证豁免 CSRF 检查
- [x] 无 CSRF token 返回 403

### 1.4 XSS 净化

- [x] 包含 `<script>` 标签的输入被净化
- [x] 正常文本输入不受影响

### 1.5 审计日志

- [x] 用户登录成功/失败记录审计日志
- [x] 审计日志包含用户ID、IP、时间、操作结果

## 阶段 2: 基础设施修复

### 2.1 数据库迁移

- [x] `alembic/` 目录存在且配置正确
- [ ] `alembic upgrade head` 执行成功（需运行时验证）
- [ ] `alembic downgrade -1` 执行成功（需运行时验证）
- [ ] 初始迁移文件包含现有 schema（需运行 `alembic revision --autogenerate`）

### 2.2 HTTP 限流

- [x] 限流中间件已注册
- [x] 超出限流阈值返回 429 Too Many Requests
- [x] 响应包含 `Retry-After` 头
- [x] 正常请求量不受影响

### 2.3 结构化日志

- [x] 日志输出为 JSON 格式
- [x] JSON 日志包含 timestamp, level, message, request_id, module 字段
- [x] 现有日志调用无需修改即可输出 JSON

### 2.4 Redis 缓存

- [x] 缓存管理器 `cache.py` 存在
- [x] catalog 查询使用缓存
- [x] 缓存命中时数据库查询次数为 0
- [x] 缓存未命中时查询数据库并写入缓存

### 2.5 数据库连接池

- [x] 连接池配置包含 `pool_recycle=3600`
- [x] 连接池配置包含 `pool_timeout=30`
