# MODstore Event Contracts

事件统一使用 NeuroBus envelope。当前实现是进程内 `InMemoryNeuroBus`，后续可以替换为 outbox、Redis Streams 或 RabbitMQ。

## Envelope

```json
{
  "event_id": "uuid",
  "event_name": "payment.order_paid",
  "event_version": 1,
  "occurred_at": "2026-04-26T00:00:00Z",
  "producer": "payment",
  "idempotency_key": "payment.order_paid:MOD1234567890",
  "subject_id": "MOD1234567890",
  "payload": {}
}
```

## 首批事件

| Event | Producer | Subject |
| --- | --- | --- |
| `catalog.package_published` | CatalogDomain | package id |
| `employee.pack_registered` | EmployeeDomain | employee pack id |
| `workflow.sandbox_completed` | WorkflowDomain | workflow id |
| `payment.order_paid` | PaymentDomain | order no |
| `wallet.balance_changed` | WalletDomain | user id |
| `llm.quota_consumed` | LLMDomain | user id |
