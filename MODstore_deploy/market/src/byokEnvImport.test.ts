import { describe, expect, it } from 'vitest'
import { parseByokPaste } from './byokEnvImport'

describe('parseByokPaste', () => {
  it('maps .env keys into provider credential entries', () => {
    const result = parseByokPaste(`
      export OPENAI_API_KEY="sk-openai"
      OPENAI_BASE_URL=https://api.example.test/v1
      deepseek=sk-deepseek
    `)

    expect(result.entries).toEqual([
      { provider: 'openai', api_key: 'sk-openai', base_url: 'https://api.example.test/v1' },
      { provider: 'deepseek', api_key: 'sk-deepseek', base_url: null },
    ])
    expect(result.warnings).toEqual([])
  })

  it('warns about malformed or too-short secrets', () => {
    const result = parseByokPaste('OPENAI_API_KEY=sk\nnot-a-key')

    expect(result.entries).toEqual([])
    expect(result.warnings.join('\n')).toContain('密钥过短')
    expect(result.warnings.join('\n')).toContain('跳过')
  })

  it('maps newly supported domestic provider aliases', () => {
    const result = parseByokPaste(`
      WENXIN_API_KEY=wenxin-key
      HUNYUAN_API_KEY=hunyuan-key
      zhipu=zhipu-key
    `)

    expect(result.entries).toEqual([
      { provider: 'wenxin', api_key: 'wenxin-key', base_url: null },
      { provider: 'hunyuan', api_key: 'hunyuan-key', base_url: null },
      { provider: 'zhipu', api_key: 'zhipu-key', base_url: null },
    ])
  })
})
