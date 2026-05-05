import { describe, it, expect, vi, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { skillRegistry } from '../../utils/agent/agentSkillRegistry'
import { readPageSkill } from './skills/readPageSkill'
import type { AgentSkill, AgentContext } from '../../types/agent'

// 模拟 vue-router
vi.mock('vue-router', () => ({
  useRouter: () => ({ push: vi.fn() }),
  useRoute: () => ({ fullPath: '/test', name: 'test' }),
}))

// 模拟 api
vi.mock('../../api', () => ({
  api: {
    agentButlerChat: vi.fn().mockResolvedValue({ text: '好的', tool_calls: [], conversation_id: 1 }),
  },
}))

// 模拟 pageSerializer
vi.mock('../../utils/agent/pageSerializer', () => ({
  serializeVisibleDom: () => '当前页面: 测试',
}))

describe('skillRegistry — 关键词匹配', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    skillRegistry.register(readPageSkill)
  })

  it('用户说"这里有什么" 应匹配 read_page 技能', () => {
    const ctx: AgentContext = {
      route: '/test',
      pageTitle: '测试',
      pageSummary: '',
      userMessage: '这里有什么？',
      history: [],
    }
    const match = skillRegistry.matchByIntent(ctx)
    expect(match).not.toBeNull()
    expect(match?.id).toBe('builtin:read_page')
  })

  it('用户说随机内容 不应匹配', () => {
    const ctx: AgentContext = {
      route: '/test',
      pageTitle: '测试',
      pageSummary: '',
      userMessage: 'xxxyyy随机内容',
      history: [],
    }
    const match = skillRegistry.matchByIntent(ctx)
    expect(match).toBeNull()
  })
})

describe('skillRegistry — tool_call 解析', () => {
  it('getById 能找到注册的技能', () => {
    skillRegistry.register(readPageSkill)
    expect(skillRegistry.getById('builtin:read_page')).toBeDefined()
  })

  it('getById 找不到未注册的技能', () => {
    expect(skillRegistry.getById('not:exist')).toBeUndefined()
  })
})

describe('readPageSkill — 执行', () => {
  it('execute 应返回 success=true', async () => {
    const ctx: AgentContext = {
      route: '/test',
      pageTitle: '测试',
      pageSummary: '',
      userMessage: '读取页面',
      history: [],
    }
    const result = await readPageSkill.execute(ctx)
    expect(result.success).toBe(true)
    expect(typeof result.message).toBe('string')
  })
})
