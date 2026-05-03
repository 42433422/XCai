# MODstore 与 FHD（XCAGI）性能基线（公开）

本文档为仓库内**公开性能基线**的单一事实来源；更新前请重跑 k6 并同步修改本页表格与日期。勿将真实账号密码、JWT 或内网未脱敏地址写入本文件。

## 元数据

| 项目 | 值 |
| --- | --- |
| 文档日期 | 2026-05-03 |
| MODstore_deploy Git（短） | `62b5a39` |
| FHD Git（短） | `aa9a961` |
| k6 版本 | 0.54.0 |
| 本次执行环境说明 | Agent 本机；`127.0.0.1:8000` 无监听，用于**验证脚本与采集失败形态**；业务 QPS/延迟基线为 **N/A**，需在目标栈启动后重跑并替换下表 |

## 1. MODstore 全链路（`perf/full_link_smoke.js`）

### 1.1 运行参数

| 项 | 值 |
| --- | --- |
| `K6_STAGE` | `smoke`（2 VU、约 1 分钟，与脚本默认一致） |
| `BASE_URL` | `http://127.0.0.1:8000` |
| `WS_URL` / `TEST_EMAIL` / `TEST_PASSWORD` | 未配置（无登录与 WebSocket 子场景压测） |
| `ENABLE_LLM` / `ENABLE_RAG` | 未开启（默认） |

### 1.2 k6 摘要（本次）

> 目标端口无服务，全部为连接失败；**不代表** MODstore 真实性能。

| 指标 | 值 |
| --- | --- |
| `http_reqs` | 480 |
| `http_req_failed` | 100%（480/480） |
| `checks` | 0%（0/480） |
| `iterations` | 60 |
| `vus_max` | 2 |
| `modstore_business_errors` | 480（与失败请求一致） |

### 1.3 复现命令

在 `MODstore_deploy` 仓库根目录：

```bash
K6_STAGE=smoke k6 run perf/full_link_smoke.js
```

Windows（已安装 k6 时）：

```powershell
$env:K6_STAGE='smoke'; k6 run perf/full_link_smoke.js
```

指定环境与账号（勿提交密钥）：

```bash
BASE_URL=https://your-host \
WS_URL=wss://your-host \
TEST_EMAIL=loadtest@example.com \
TEST_PASSWORD='***' \
K6_STAGE=smoke \
k6 run perf/full_link_smoke.js
```

### 1.4 Grafana（可选）

本次未连接可观测栈，无面板截图。生产/预发跑完后请在 `MODstore Overview` 记录 FastAPI p95、支付代理 p95、JVM heap、Hikari、5xx，并追加到本节或链接到内部 wiki。

---

## 2. FHD / XCAGI API 脚本（`FHD/scripts/loadtest`）

### 2.1 路由对齐说明（2026-05-03）

脚本已与当前 FastAPI 路由对齐（`config.js`）：

| 逻辑名 | 路径 |
| --- | --- |
| health | `GET /api/health` |
| catalog（原 products 键名保留） | `GET /api/mod-store/catalog` |
| liveness（原 shipments 键名保留） | `GET /health/liveness` |
| auth（仅 `stress.js`） | `POST /api/auth/login` |

### 2.2 k6 摘要：`smoke.js`（本次）

| 指标 | 值 |
| --- | --- |
| `http_reqs` | 150 |
| `http_req_failed` | 100%（150/150） |
| `checks` | 0%（0/150） |
| `iterations` | 75 |
| `vus` | 5 |
| 阈值 | `http_req_duration p(99)<500ms`、`http_req_failed rate<0.05` — **未通过**（因无上游） |

### 2.3 复现命令

在 `FHD` 仓库根目录：

```bash
k6 run -e BASE_URL=http://127.0.0.1:8000 scripts/loadtest/smoke.js
k6 run -e BASE_URL=http://127.0.0.1:8000 scripts/loadtest/load.js
k6 run -e BASE_URL=http://127.0.0.1:8000 scripts/loadtest/stress.js
```

---

## 3. 正式基线回填检查清单

- [ ] 目标 `BASE_URL` 可访问，`GET /api/health` 返回 200。
- [ ] MODstore：`K6_STAGE=smoke` 通过后再按需跑 `step` / `soak`。
- [ ] FHD：`smoke.js` 全绿后再跑 `load.js` / `stress.js`。
- [ ] 将本节以上各表的 N/A/失败率替换为**成功连接**下的 p95/p99、错误率与迭代次数。
- [ ] 同步更新 FHD 仓库内 `docs/reports/capacity-planning.md` 中对应表格（与本文件常见同盘布局：[`../../../FHD/docs/reports/capacity-planning.md`](../../../FHD/docs/reports/capacity-planning.md)；若 FHD 检出位置不同则改用组织内链接）。
