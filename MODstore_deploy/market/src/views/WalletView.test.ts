import { mount, flushPromises } from '@vue/test-utils'
import { describe, expect, it, vi, beforeEach } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'
import { createPinia, setActivePinia } from 'pinia'
import WalletView from './WalletView.vue'
import { ACCESS_TOKEN_KEY } from '../infrastructure/storage/tokenStore'

vi.mock('../api', () => ({
  api: {
    walletOverview: vi.fn(),
    paymentMyPlan: vi.fn(),
    llmCatalog: vi.fn(),
    llmStatus: vi.fn(),
  },
}))

import { api } from '../api'

describe('WalletView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.setItem(ACCESS_TOKEN_KEY, 'tok-w')
    vi.mocked(api.walletOverview).mockResolvedValue({
      wallet: { balance: '12.34', membership_reference_yuan: 0 },
      transactions: [],
      orders: [],
      order_total: 0,
      refunds: [],
    })
    vi.mocked(api.paymentMyPlan).mockResolvedValue({ plan: null, quotas: [] })
    vi.mocked(api.llmCatalog).mockResolvedValue({
      providers: [],
      preferences: {},
    })
    vi.mocked(api.llmStatus).mockResolvedValue({ providers: [] })
  })

  it('renders wallet overview heading and balance', async () => {
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [{ path: '/wallet', name: 'wallet', component: WalletView }],
    })
    const pinia = createPinia()
    const wrapper = mount(WalletView, {
      global: { plugins: [pinia, router] },
    })

    await flushPromises()

    expect(wrapper.text()).toContain('资金与记录')
    expect(wrapper.text()).toContain('¥12.34')
  })
})
