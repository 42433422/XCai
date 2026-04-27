export interface PaymentPlan {
  id: string
  name: string
  description?: string
  price: number
  features?: string[]
}

export interface OrderSummary {
  out_trade_no?: string
  order_id?: string
  status: string
  total_amount?: number
  subject?: string
}

export interface EntitlementList {
  items?: unknown[]
  entitlements?: unknown[]
  total?: number
}
