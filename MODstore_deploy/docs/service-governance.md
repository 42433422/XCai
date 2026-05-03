# MODstore 单机服务治理约定

本文档记录当前单机/少量服务器部署下已经落地的服务治理能力，以及迁移到 Kubernetes/Service Mesh 前的边界。

## 网关层

`market/nginx.conf` 是容器化部署的入口反代，负责：

- `/api/auth/` 每 IP 5 r/s，突发 10。
- `/api/payment/`、`/api/wallet/` 每 IP 10 r/s，突发 20。
- 其他 `/api/`、`/v1/` 每 IP 20 r/s，突发 40。
- `/api/realtime/` 保持 WebSocket 长连接，`proxy_read_timeout 1d`。
- 其他 `/api/`、`/v1/`：`proxy_read_timeout` / `proxy_send_timeout` 设为 **3600s**（含 LLM 流式、工作台编排）；过短会在上游仍在处理时由 nginx 返回 **504**。
- 所有反代请求透传 `X-Request-Id`，便于从 Nginx、FastAPI、Java 日志串联。
- `/nginx-health` 作为容器健康检查，不依赖前端构建产物路由。

## FastAPI 网关层

FastAPI 已安装以下治理能力：

- `X-Request-Id` 中间件：若入口未传入，则生成新的 request id，并写回响应头。
- HTTP 指标：`modstore_http_requests_total`、`modstore_http_request_duration_seconds`。
- 支付代理指标：`modstore_payment_proxy_requests_total`、`modstore_payment_proxy_duration_seconds`。
- Java 支付代理超时由环境变量控制：
  - `PAYMENT_PROXY_CONNECT_TIMEOUT_SECONDS`，默认 `5`。
  - `PAYMENT_PROXY_READ_TIMEOUT_SECONDS`，默认 `30`。

当 `PAYMENT_BACKEND=java` 时，只有 `payment_contract.PROXY_PREFIXES` 中定义的路径会被代理到 Java，其余业务仍由 Python 服务处理。

## Java 支付层

Java 支付服务继续使用 Spring Boot Actuator/Micrometer 暴露 JVM、HTTP、Hikari 连接池指标，并补充业务指标：

- `modstore_payment_checkout_total{channel,result,reason}`：下单尝试结果。
- `modstore_payment_notify_total{provider,result}`：支付回调处理结果。
- `modstore_webhook_delivery_total{event_type,result,status,attempt}`：业务 Webhook 投递结果。

这些指标已经纳入 `monitoring/prometheus/rules/modstore-alerts.yml` 的支付告警与 Grafana dashboard。

## 灰度与回滚约束

- 支付后端切换必须按 `docs/PAYMENT_GRAY_RELEASE.md` 执行预检、预发灰度、生产切换和回滚。
- 任意发布前必须至少通过 `scripts/sre_smoke_check.py` 的核心健康检查。
- 开启 `PAYMENT_BACKEND=java` 前必须确认 Java `/actuator/health` 为 UP，且 `MODSTORE_JWT_SECRET` 与 Python 一致。
- 回滚到 Python 支付时，要明确 Java 期间产生的订单仍在 PostgreSQL，不能假设 Python JSON 订单存储完整。
- LLM/RAG/工作流等长链路不应复用支付短请求超时，需要按业务链路单独配置和压测。

## 服务网格目标态

当前部署不依赖 Kubernetes，不强行引入 Istio/Linkerd。短期用 Nginx + FastAPI + Actuator 获得限流、超时、指标和灰度回滚能力。迁移到 Kubernetes 后，再评估：

- mTLS 与服务身份。
- 自动重试、熔断、连接池策略。
- 金丝雀发布和流量镜像。
- 多副本跨节点流量治理。
