import { describe, expect, it } from 'vitest'
import { classifyLlmCatalogIssue, hasAnyLlmKey } from './llmProviderHealth'

describe('llmProviderHealth', () => {
  it('detects configured platform or user keys', () => {
    expect(hasAnyLlmKey(null)).toBe(false)
    expect(hasAnyLlmKey({ has_platform_key: true })).toBe(true)
    expect(hasAnyLlmKey({ has_user_override: true })).toBe(true)
  })

  it('classifies authentication and transient catalog issues', () => {
    expect(classifyLlmCatalogIssue('401 invalid api key', '')).toBe('danger')
    expect(classifyLlmCatalogIssue('timeout while fetching models', '')).toBe('warn')
    expect(classifyLlmCatalogIssue('', 'fallback_after_error')).toBe('warn')
    expect(classifyLlmCatalogIssue('model list empty', '')).toBeNull()
  })
})
