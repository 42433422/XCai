import { beforeEach, describe, expect, it } from 'vitest'
import {
  createConversation,
  exportConversationAsMarkdown,
  loadActiveId,
  loadConversations,
  makeMessage,
  saveActiveId,
  saveConversations,
  searchConversations,
  summarizeForTitle,
} from './conversationStore'

describe('conversationStore', () => {
  beforeEach(() => {
    if (typeof localStorage !== 'undefined') localStorage.clear()
  })

  it('creates conversation with default title and messages array', () => {
    const c = createConversation()
    expect(c.id).toMatch(/^conv_/)
    expect(c.title).toBe('新对话')
    expect(Array.isArray(c.messages)).toBe(true)
    expect(c.pinned).toBe(false)
  })

  it('summarizeForTitle truncates and trims', () => {
    expect(summarizeForTitle('  hello  ')).toBe('hello')
    expect(summarizeForTitle('a'.repeat(100)).length).toBe(24)
    expect(summarizeForTitle('')).toBe('新对话')
  })

  it('persists and reloads conversations sorted by pinned + updatedAt', () => {
    const a = createConversation({ title: 'A' })
    a.updatedAt = 1000
    const b = createConversation({ title: 'B' })
    b.updatedAt = 2000
    const c = createConversation({ title: 'C' })
    c.updatedAt = 500
    c.pinned = true
    saveConversations([a, b, c])

    const restored = loadConversations()
    expect(restored.map((x) => x.title)).toEqual(['C', 'B', 'A'])
  })

  it('saves and loads active id', () => {
    saveActiveId('abc')
    expect(loadActiveId()).toBe('abc')
  })

  it('searchConversations matches title and message body', () => {
    const a = createConversation({ title: '门店日报方案' })
    a.messages.push(makeMessage('user', '帮我写一份周报'))
    const b = createConversation({ title: '其它' })
    b.messages.push(makeMessage('user', '联网搜索股价'))
    expect(searchConversations([a, b], '日报').length).toBe(1)
    expect(searchConversations([a, b], '周报').length).toBe(1)
    expect(searchConversations([a, b], '股价').length).toBe(1)
    expect(searchConversations([a, b], '不存在').length).toBe(0)
  })

  it('exports conversation to markdown with header', () => {
    const c = createConversation({ title: '测试' })
    c.messages.push(makeMessage('user', '问题'))
    c.messages.push(makeMessage('assistant', '回答'))
    const md = exportConversationAsMarkdown(c)
    expect(md).toContain('# 测试')
    expect(md).toContain('问题')
    expect(md).toContain('回答')
  })

  it('caps stored conversations to 100 entries', () => {
    const list = Array.from({ length: 130 }, (_, i) => {
      const c = createConversation({ title: `T${i}` })
      c.updatedAt = i
      return c
    })
    saveConversations(list)
    const restored = loadConversations()
    expect(restored.length).toBe(100)
  })
})
