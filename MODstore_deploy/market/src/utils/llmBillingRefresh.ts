import { useAuthStore } from '../stores/auth'
import { useWalletStore } from '../stores/wallet'

/** 走钱包计费的 LLM 调用完成后刷新等级经验与顶栏余额（避免 Pinia 15s 缓存仍显示旧值）。 */
export function refreshLevelAndWalletAfterLlm(): void {
  queueMicrotask(() => {
    try {
      void useAuthStore().refreshSession(true)
      void useWalletStore().refreshBalance()
    } catch {
      /* 应用未挂载时忽略 */
    }
  })
}
