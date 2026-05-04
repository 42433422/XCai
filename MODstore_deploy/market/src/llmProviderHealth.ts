/**
 * 启发式：根据模型目录拉取错误与 fetch_source 推断 warn / danger。
 * 不表示各厂商真实余额，仅辅助 UI（黄/红）。
 */

/**
 * 钱包磁贴等 UI：默认仅以 BYOK 视为「已配置」。
 * 例外：小米 MiMo（xiaomi）仍兼容服务端环境变量密钥，与 BYOK 一并视为已配置。
 * @param {{ provider?: string, has_platform_key?: boolean, has_user_override?: boolean }|null|undefined} row
 */
export function hasAnyLlmKey(row) {
  if (!row) return false
  if (row.has_user_override) return true
  if (row.provider === 'xiaomi' && row.has_platform_key) return true
  return false
}

const DANGER_SUBSTR = [
  '401',
  '403',
  '402',
  'invalid',
  'authentication',
  'incorrect api key',
  'invalid api key',
  'wrong api key',
  'unauthorized',
  'forbidden',
  'insufficient',
  'quota',
  'exhausted',
  'billing',
  'payment',
  'permission denied',
  'not authorized',
  'no_api_key',
  '解密失败',
]

const EXPIRED_SUBSTR = [
  'expired',
  'expire',
  'expires',
  'invalid token',
  'token expired',
  'key expired',
  'api key expired',
  'credential expired',
  'access token expired',
  '已过期',
  '过期',
  '失效',
  '已失效',
]

const WARN_SUBSTR = [
  '429',
  'rate limit',
  'throttl',
  'resource_exhausted',
  'overloaded',
  'timeout',
  'timed out',
  'connect',
  '502',
  '503',
  '504',
  '500',
  'network',
  'unreachable',
  'temporar',
]

/**
 * @param {string|null|undefined} error
 * @param {string|null|undefined} fetchSource
 * @returns {'warn'|'danger'|'expired'|null}
 */
export function classifyLlmCatalogIssue(error, fetchSource) {
  const e = (error && String(error).toLowerCase()) || ''
  const src = fetchSource ? String(fetchSource) : ''

  for (const p of EXPIRED_SUBSTR) {
    if (e.includes(p)) return 'expired'
  }

  for (const p of DANGER_SUBSTR) {
    if (e.includes(p)) return 'danger'
  }

  if (src === 'fallback_after_error') return 'warn'

  for (const p of WARN_SUBSTR) {
    if (e.includes(p)) return 'warn'
  }

  if (e.trim()) return null

  return null
}
