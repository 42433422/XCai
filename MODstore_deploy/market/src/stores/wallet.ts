import { ref } from 'vue'
import { defineStore } from 'pinia'
import { api } from '../api'

export const useWalletStore = defineStore('wallet', () => {
  const balance = ref<number | null>(null)
  /** 会员累计参考线（元），来自 /api/wallet/balance */
  const membershipReferenceYuan = ref<number | null>(null)
  const loading = ref(false)

  function setMembershipReferenceYuan(v: unknown): void {
    const n = Number(v)
    membershipReferenceYuan.value = Number.isFinite(n) && n >= 0 ? Math.floor(n) : null
  }

  async function refreshBalance(): Promise<number | null> {
    loading.value = true
    try {
      const res = await api.balance()
      balance.value = Number(res?.balance ?? 0)
      setMembershipReferenceYuan(res?.membership_reference_yuan)
      return balance.value
    } catch {
      balance.value = null
      membershipReferenceYuan.value = null
      return null
    } finally {
      loading.value = false
    }
  }

  function setBalance(value: unknown): void {
    const n = Number(value)
    balance.value = Number.isFinite(n) ? n : null
  }

  function clear(): void {
    balance.value = null
    membershipReferenceYuan.value = null
  }

  return { balance, membershipReferenceYuan, loading, refreshBalance, setBalance, setMembershipReferenceYuan, clear }
})
