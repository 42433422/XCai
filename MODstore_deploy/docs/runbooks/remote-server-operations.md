# 远程服务器 SRE 运维手册

本手册面向单机/少量服务器 Docker Compose 部署。目标是在远程服务器上把部署、健康检查、备份、压测、演练和回滚串成可重复流程。

## 首次准备

服务器需要具备：

- Git
- Docker Engine 与 Docker Compose plugin
- Python 3
- curl
- 可访问代码仓库的权限

推荐目录：

```bash
/root/modstore-git
```

服务器上准备环境变量：

```bash
cd /root/modstore-git/MODstore_deploy
cp .env.production.example .env
vim .env
```

必须替换所有 `CHANGE_ME`，尤其是数据库、Redis、RabbitMQ、JWT、支付签名、Grafana 密码和支付回调地址。

## 本地触发远程操作

在本机 `MODstore_deploy` 目录运行：

```powershell
.\scripts\remote-sre.ps1 `
  -Action preflight `
  -SshTarget root@your-server `
  -RemoteRepo /root/modstore-git
```

也可以通过环境变量减少参数：

```powershell
$env:DEPLOY_SSH = "root@your-server"
$env:DEPLOY_REMOTE_REPO = "/root/modstore-git"
$env:DEPLOY_GIT_BRANCH = "main"
```

## 支持动作

| Action | 作用 |
| --- | --- |
| `preflight` | 检查远程命令、目录、`.env`、Compose 配置、磁盘和容器状态 |
| `smoke` | 远程执行 `scripts/sre_smoke_check.py` |
| `backup` | 远程执行 `scripts/backup_modstore.py` |
| `deploy` | `git fetch/reset`、备份、`docker compose --profile app up -d --build`、冒烟 |
| `loadtest` | 运行 Compose `loadtest` profile 的 k6 冒烟/阶梯压测 |
| `chaos-dry-run` | 打印混沌演练命令，不实际停止服务 |
| `rollback` | 回滚到指定 Git ref，重建应用栈并冒烟 |

## 日常发布

```powershell
.\scripts\remote-sre.ps1 -Action deploy -SshTarget root@your-server -RemoteRepo /root/modstore-git -Branch main
```

发布动作会在远端执行：

1. `preflight`
2. `git fetch origin <branch>`
3. `git reset --hard origin/<branch>`
4. `python scripts/backup_modstore.py`
5. `docker compose --profile app up -d --build`
6. `python scripts/sre_smoke_check.py ...`

## 冒烟检查

默认检查本机端口：

```powershell
.\scripts\remote-sre.ps1 -Action smoke -SshTarget root@your-server -RemoteRepo /root/modstore-git
```

如服务器端口不同：

```powershell
.\scripts\remote-sre.ps1 `
  -Action smoke `
  -SshTarget root@your-server `
  -RemoteRepo /root/modstore-git `
  -ApiUrl http://127.0.0.1:9999 `
  -MarketUrl http://127.0.0.1:4173 `
  -PaymentUrl http://127.0.0.1:8080 `
  -PrometheusUrl http://127.0.0.1:9090
```

## 备份

```powershell
.\scripts\remote-sre.ps1 -Action backup -SshTarget root@your-server -RemoteRepo /root/modstore-git
```

备份落在远端：

```bash
/root/modstore-git/MODstore_deploy/backups/<timestamp>/
```

建议再通过对象存储、rsync 或云盘快照把备份复制到服务器外部。

## 压测

轻量冒烟：

```powershell
.\scripts\remote-sre.ps1 -Action loadtest -SshTarget root@your-server -RemoteRepo /root/modstore-git
```

阶梯压测：

```powershell
.\scripts\remote-sre.ps1 -Action loadtest -SshTarget root@your-server -RemoteRepo /root/modstore-git -K6Stage step
```

压测前后打开 Grafana `MODstore Overview`，记录 FastAPI p95、支付代理 p95、Java heap、Hikari 连接池和告警。

## 混沌演练 dry-run

```powershell
.\scripts\remote-sre.ps1 `
  -Action chaos-dry-run `
  -SshTarget root@your-server `
  -RemoteRepo /root/modstore-git `
  -ChaosScenario payment-restart
```

该动作只打印命令，不会真正重启或停止服务。真实演练仍需登录预发服务器后按 `chaos/README.md` 手动带 `--confirm` 执行。

## 回滚

回滚必须明确 Git ref，例如上一个提交、tag 或稳定分支：

```powershell
.\scripts\remote-sre.ps1 `
  -Action rollback `
  -SshTarget root@your-server `
  -RemoteRepo /root/modstore-git `
  -RollbackRef HEAD~1
```

回滚动作会先备份当前状态，再重建 Compose 应用栈并冒烟。支付相关回滚还必须参考 `docs/PAYMENT_GRAY_RELEASE.md`，避免订单数据源不一致。

## 端口与 Nginx

Compose 默认端口：

- Market: `4173`
- FastAPI: `8765`
- Java payment: `8080`
- Prometheus: `9090`
- Grafana: `3000`
- RabbitMQ 管理台: `15672`

公网建议只暴露 Nginx/HTTPS 入口，数据库、Redis、RabbitMQ、Prometheus、Grafana 只允许内网或 SSH 隧道访问。

## 最小上线验收

- `preflight` 通过。
- `deploy` 成功完成。
- `smoke` 通过。
- Grafana 无 P0/P1 告警。
- `backup` 产物已同步到服务器外部。
- 支付计划、钱包余额、订单查询至少手工验证一次。
