import { expect, test } from '@playwright/test'

test('首页可加载，标题包含 XC AGI', async ({ page }) => {
  await page.goto('/')
  await expect(page).toHaveTitle(/XC AGI/i)
})

test('未登录访问 /wallet 应跳转到 /login 且带 redirect 查询参数', async ({ page }) => {
  await page.context().clearCookies()
  await page.goto('/wallet')
  // 路由守卫应当把我们带去登录页
  await page.waitForURL(/\/login(\?|$)/, { timeout: 10_000 })
  expect(page.url()).toContain('/login')
  expect(page.url()).toContain('redirect=%2Fwallet')
})

test('登录页可见用户名/密码字段', async ({ page }) => {
  await page.goto('/login')
  // 不强行检查具体 selector，只确认登录页能渲染输入框
  const inputs = page.locator('input')
  await expect(inputs.first()).toBeVisible({ timeout: 10_000 })
})
