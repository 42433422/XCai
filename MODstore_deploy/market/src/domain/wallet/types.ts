export interface WalletBalance {
  balance: number
  updated_at?: string
  /** 会员随单赠送累计参考（元，整数），见后端 WalletService#getMembershipReferenceLineYuan */
  membership_reference_yuan?: number
}

export interface WalletTransaction {
  id?: number
  amount: number
  type?: string
  txn_type?: string
  status?: string
  description?: string
  created_at?: string
}
