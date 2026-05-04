# MODstore 关键修复任务清单

## 阶段 1: 严重安全修复

### 1.1 移除硬编码弱密钥 + 启动校验

- [x] Task 1.1.1: 移除 `modstore_server/auth_service.py` 中的 `"modstore-dev-secret-change-in-prod"` 回退值
- [x] Task 1.1.2: 在 `modstore_server/app.py` 中添加生产环境密钥强度校验函数
- [x] Task 1.1.3: 清理 `.env.example` 中的真实 SMTP 邮箱信息

### 1.2 安全响应头中间件

- [x] Task 1.2.1: 创建 `modstore_server/api/security_headers.py`，实现 SecurityHeadersMiddleware
- [x] Task 1.2.2: 在 `modstore_server/api/middleware.py` 中注册安全响应头中间件

### 1.3 CSRF 防护

- [x] Task 1.3.1: 创建 `modstore_server/api/csrf.py`，实现 CSRF 防护中间件（Double Submit Cookie 模式）
- [x] Task 1.3.2: 在中间件链中注册 CSRF 中间件

### 1.4 XSS 输入净化

- [x] Task 1.4.1: 创建 `modstore_server/api/xss_sanitizer.py`，实现全局 XSS 净化中间件
- [x] Task 1.4.2: 在中间件链中注册 XSS 净化中间件

### 1.5 安全审计日志

- [x] Task 1.5.1: 创建 `modstore_server/audit_logger.py`，实现审计日志模块
- [x] Task 1.5.2: 在 `modstore_server/auth_service.py` 中集成审计日志

## 阶段 2: MODstore 基础设施修复

### 2.1 数据库迁移管理（Alembic）

- [x] Task 2.1.1: 在 `MODstore_deploy/` 根目录初始化 Alembic
- [x] Task 2.1.2: 配置 `alembic/env.py` 连接 MODstore 数据库
- [ ] Task 2.1.3: 从现有 schema 自动生成初始迁移
- [ ] Task 2.1.4: 验证 `alembic upgrade head` 和 `alembic downgrade -1` 正常工作

### 2.2 HTTP 限流

- [x] Task 2.2.1: 创建 `modstore_server/api/rate_limiter.py`，实现基于 Redis 的滑动窗口限流器
- [x] Task 2.2.2: 创建限流中间件，默认 60 次/分钟/IP
- [x] Task 2.2.3: 在中间件链中注册限流中间件

### 2.3 结构化 JSON 日志

- [x] Task 2.3.1: 创建 `modstore_server/structured_logging.py`，实现 JSON 格式化器
- [x] Task 2.3.2: 在 `modstore_server/app.py` 启动时配置结构化日志

### 2.4 Redis 缓存层

- [x] Task 2.4.1: 创建 `modstore_server/cache.py`，实现 Redis 缓存管理器
- [x] Task 2.4.2: 为 catalog 查询添加缓存装饰器
- [x] Task 2.4.3: 为用户信息查询添加缓存

### 2.5 数据库连接池完善

- [x] Task 2.5.1: 在数据库连接配置中添加 pool_recycle=3600 和 pool_timeout=30

## 任务依赖关系

```
阶段 1（可并行）:
  1.1, 1.2, 1.3, 1.4, 1.5 之间无依赖

阶段 2（可并行）:
  2.1, 2.2, 2.3, 2.4, 2.5 之间无依赖
  2.4 依赖 Redis 可用（docker-compose 中已有）
```
