import { expect, test } from '@playwright/test'

// 并行 worker 同时打同一 Vite dev 实例时易出现首屏/路由竞态（如未清 token 的误判）；本文件串行更稳。
test.describe.configure({ mode: 'serial' })

async function stubCommonApis(page: import('@playwright/test').Page) {
  await page.route('**/*', async (route) => {
    const { pathname } = new URL(route.request().url())
    if (pathname === '/api/auth/me') {
      await route.fulfill({ json: { id: 1, username: 'tester', is_admin: false } })
      return
    }
    if (pathname === '/api/wallet/balance') {
      await route.fulfill({ json: { balance: 0 } })
      return
    }
    if (pathname === '/api/notifications') {
      await route.fulfill({ json: { items: [], unread_count: 0 } })
      return
    }
    if (pathname === '/api/payment/plans') {
      await route.fulfill({
        json: {
          plans: [
            {
              id: 'basic',
              name: '基础版',
              price: 9.9,
              description: '适合试用',
              features: ['1 个员工', '基础工作台'],
            },
          ],
        },
      })
      return
    }
    if (pathname === '/api/payment/sign-checkout') {
      await route.fulfill({
        json: {
          plan_id: 'basic',
          item_id: 0,
          total_amount: 9.9,
          subject: '基础版',
          wallet_recharge: false,
          request_id: 'req-e2e',
          timestamp: 1710000000,
          signature: 'sig-e2e',
        },
      })
      return
    }
    if (pathname === '/api/payment/checkout') {
      await route.fulfill({ json: { ok: true, type: 'precreate', order_id: 'order-e2e' } })
      return
    }
    if (pathname.startsWith('/api/payment/query/')) {
      await route.fulfill({
        json: {
          out_trade_no: 'order-e2e',
          subject: '基础版',
          total_amount: 9.9,
          status: 'paid',
          trade_no: 'trade-e2e',
          created_at: '2026-01-02T03:04:05Z',
          paid_at: '2026-01-02T03:05:05Z',
          refund_status: 'none',
          refunded_amount: 0,
        },
      })
      return
    }
    if (pathname.startsWith('/api/')) {
      await route.fulfill({ json: { items: [], ok: true, workflows: [], executions: [] } })
      return
    }
    if (pathname.startsWith('/v1/')) {
      await route.fulfill({ json: { items: [] } })
      return
    }
    await route.fallback()
  })
}

test('protected pages redirect anonymous users to login', async ({ page }) => {
  await page.goto('/wallet')

  await expect(page).toHaveURL(/\/login\?redirect=.*wallet/)
  await expect(page.getByRole('heading', { name: '登录' })).toBeVisible()
})

test('plan purchase creates a checkout order for authenticated users', async ({ page }) => {
  await stubCommonApis(page)
  await page.addInitScript(() => localStorage.setItem('modstore_token', 'token-e2e'))

  await page.goto('/plans')
  await expect(page.getByRole('heading', { name: '基础版' })).toBeVisible()
  await page.locator('.plan-card .btn-primary').click()

  await expect(page).toHaveURL(/\/checkout\/order-e2e/)
})

test('order detail renders payment and refund state', async ({ page }) => {
  await stubCommonApis(page)
  await page.addInitScript(() => localStorage.setItem('modstore_token', 'token-e2e'))

  await page.goto('/order/order-e2e')

  await expect(page.getByText('order-e2e')).toBeVisible()
  await expect(page.getByText('已支付')).toBeVisible()
  await expect(page.getByText('无退款')).toBeVisible()
})

test('workbench focus tabs switch between employee workflow and repository surfaces', async ({ page }) => {
  await stubCommonApis(page)
  await page.addInitScript(() => {
    localStorage.setItem('modstore_token', 'token-e2e')
    localStorage.setItem('employee_workbench_onboarding_seen_v1', '1')
  })

  await page.goto('/workbench/unified?focus=employee')
  await expect(page.getByRole('button', { name: '专注员工制作' })).toHaveClass(/mode-tab--active/)

  await page.locator('.mode-tab', { hasText: '专注工作流' }).click()
  await expect(page).toHaveURL(/focus=workflow/)
  await expect(page.getByRole('button', { name: '专注工作流' })).toHaveClass(/mode-tab--active/)

  await page.locator('.mode-tab', { hasText: '专注Mod库' }).click()
  await expect(page).toHaveURL(/focus=repository/)
})

test('unknown routes render the not found page', async ({ page }) => {
  await page.goto('/does-not-exist')

  await expect(page.getByRole('heading', { name: '404' })).toBeVisible()
  await expect(page.getByText('抱歉，您访问的页面不存在')).toBeVisible()
})
