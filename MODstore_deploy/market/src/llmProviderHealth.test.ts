import { describe, expect, it } from 'vitest'
import { classifyLlmCatalogIssue, hasAnyLlmKey } from './llmProviderHealth'

describe('llmProviderHealth', () => {
  it('detects BYOK; xiaomi also accepts platform key from server env', () => {
    expect(hasAnyLlmKey(null)).toBe(false)
    expect(hasAnyLlmKey({ has_platform_key: true })).toBe(false)
    expect(hasAnyLlmKey({ provider: 'openai', has_platform_key: true })).toBe(false)
    expect(hasAnyLlmKey({ provider: 'xiaomi', has_platform_key: true })).toBe(true)
    expect(hasAnyLlmKey({ has_user_override: true })).toBe(true)
  })

  it('classifies authentication and transient catalog issues', () => {
    expect(classifyLlmCatalogIssue('401 invalid api key', '')).toBe('danger')
    expect(classifyLlmCatalogIssue('access token expired', '')).toBe('expired')
    expect(classifyLlmCatalogIssue('平台密钥已过期，请重新配置', '')).toBe('expired')
    expect(classifyLlmCatalogIssue('timeout while fetching models', '')).toBe('warn')
    expect(classifyLlmCatalogIssue('', 'fallback_after_error')).toBe('warn')
    expect(classifyLlmCatalogIssue('model list empty', '')).toBeNull()
  })
})
