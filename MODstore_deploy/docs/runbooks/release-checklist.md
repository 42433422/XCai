# 发布门禁 Checklist

## 发布前

- [ ] CI 全部通过。
- [ ] 变更范围已明确，包含回滚方式。
- [ ] 数据库迁移已在预发执行并验证。
- [ ] 支付相关变更已通过 `docs/PAYMENT_GRAY_RELEASE.md` 预检。
- [ ] 备份已完成：`python scripts/backup_modstore.py --components postgres,modstore_data`。
- [ ] 预发冒烟通过：`python scripts/sre_smoke_check.py ...`。
- [ ] 轻量压测通过：`K6_STAGE=smoke k6 run perf/full_link_smoke.js`。
- [ ] Grafana 无未处理 P0/P1 告警。

## 发布中

- [ ] 记录发布时间、commit、操作者。
- [ ] 按服务顺序发布：基础设施、Java 支付、FastAPI、market。
- [ ] 每一步执行健康检查。
- [ ] 观察 5xx、p95、支付代理、Java heap/Hikari。

## 发布后

- [ ] 生产冒烟通过。
- [ ] 核心业务手工验证：登录、市场、支付计划、钱包、订单查询。
- [ ] 观察至少 15 分钟无新增 P0/P1 告警。
- [ ] 记录发布结果和发现的问题。

## 回滚触发条件

- P0 链路持续 5 分钟不可用。
- 支付/钱包出现未知 5xx 或数据一致性风险。
- 数据库迁移导致核心查询失败。
- p95 延迟超过 SLO 2 倍且无法在 15 分钟内定位。
