/**
 * 与 modstore_server/llm_api.py `llm_status` 返回对齐：
 *   { providers: LlmProviderStatus[], fernet_configured: boolean }
 *
 * 字段源自 llm_key_resolver.credential_status：
 *   - has_platform_key：平台环境变量已配置
 *   - has_user_override：用户 BYOK 已上报
 */
export interface LlmProviderStatus {
  provider: string
  label?: string
  has_platform_key?: boolean
  has_user_override?: boolean
  masked_key?: string
  /** 旧字段，部分接口仍返回；前端按 has_user_override / has_platform_key 优先 */
  configured?: boolean
  healthy?: boolean
}

export interface LlmStatusResponse {
  providers: LlmProviderStatus[]
  fernet_configured: boolean
}
