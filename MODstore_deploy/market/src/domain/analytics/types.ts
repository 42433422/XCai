export interface ExecutionMetrics {
  total: number
  success: number
  failed: number
  success_rate: number
  total_tokens: number
  avg_duration_ms?: number
}

export interface CommerceMetrics {
  total_spent: number
  purchase_count: number
  refund_count: number
  wallet_transaction_count: number
}

export interface CatalogMetrics {
  total_packages: number
  public_packages: number
  employee_packs: number
}

export interface AnalyticsDashboard {
  execution: ExecutionMetrics
  commerce?: CommerceMetrics
  catalog?: CatalogMetrics
  spending?: { total: number }
  recent_executions: Array<Record<string, unknown>>
}
