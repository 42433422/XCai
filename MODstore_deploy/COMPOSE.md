# MODstore Docker Compose

## 启动基础设施

```bash
docker compose up -d
```

这会启动 PostgreSQL、Redis、RabbitMQ。默认密码仅用于本地开发，生产环境必须在 `.env` 中改掉。

## 启动完整本地栈

```bash
docker compose --profile app up --build
```

- 市场前端：http://localhost:4173/market/
- FastAPI：http://localhost:8765/api/health
- Java 支付服务：http://localhost:8080/actuator/health
- RabbitMQ 管理台：http://localhost:15672

## 关键变量

- `PAYMENT_BACKEND=python|java`：是否由 FastAPI 代理支付/钱包请求到 Java 支付服务。
- `REDIS_URL` / `REDIS_PASSWORD`：支付幂等、防重放和缓存使用 Redis，生产环境应启用认证并限制网络。
- `MODSTORE_WEBHOOK_URL` / `MODSTORE_WEBHOOK_SECRET`：支付和退款事件的业务 Webhook 地址与签名密钥。
- `ALIPAY_NOTIFY_URL`：公网支付宝异步通知地址，路径保持 `/api/payment/notify/alipay`。

## 生产服务器闭环

生产单机部署建议从模板开始：

```bash
cp .env.production.example .env
```

替换所有 `CHANGE_ME` 后再启动：

```bash
docker compose --profile app up -d --build
```

远程服务器日常运维入口见：

- `scripts/remote-sre.ps1`：本机通过 SSH 触发远程 preflight、deploy、backup、smoke、loadtest、rollback。
- `scripts/remote_sre_ops.sh`：远程实际执行脚本。
- `docs/runbooks/remote-server-operations.md`：完整操作手册。

最小上线验收：

```bash
python scripts/sre_smoke_check.py \
  --base-url http://127.0.0.1:${MODSTORE_API_PORT:-8765} \
  --market-url http://127.0.0.1:${MODSTORE_MARKET_PORT:-4173} \
  --payment-url http://127.0.0.1:${JAVA_PAYMENT_PORT:-8080} \
  --prometheus-url http://127.0.0.1:${PROMETHEUS_PORT:-9090}
```
