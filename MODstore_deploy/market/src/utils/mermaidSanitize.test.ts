import { describe, expect, it } from 'vitest'
import { sanitizeMermaidSource } from './mermaidSanitize'

describe('sanitizeMermaidSource', () => {
  it('leaves clean labels unchanged', () => {
    const src = 'flowchart LR\nA[Foo] --> B[Bar]'
    expect(sanitizeMermaidSource(src)).toBe(src)
  })

  it('quotes bracket labels with parentheses', () => {
    const src = 'flowchart LR\nA[Foo (Bar)] --> B[Done]'
    expect(sanitizeMermaidSource(src)).toBe(
      'flowchart LR\nA["Foo (Bar)"] --> B[Done]',
    )
  })

  it('quotes round-shape labels with colons', () => {
    const src = 'flowchart TB\nA(开始: register) --> B(结束)'
    expect(sanitizeMermaidSource(src)).toBe(
      'flowchart TB\nA("开始: register") --> B(结束)',
    )
  })

  it('escapes inner quotes via #quot;', () => {
    const src = 'flowchart LR\nA[Hello "world"]'
    expect(sanitizeMermaidSource(src)).toBe(
      'flowchart LR\nA["Hello #quot;world#quot;"]',
    )
  })

  it('keeps already-quoted labels untouched', () => {
    const src = 'flowchart LR\nA["Foo (Bar)"] --> B["x: y"]'
    expect(sanitizeMermaidSource(src)).toBe(src)
  })

  it('does not touch edge pipe labels or styles', () => {
    const src = [
      'flowchart LR',
      'A -->|click: go| B',
      'style A fill:#fff,stroke:#333',
    ].join('\n')
    expect(sanitizeMermaidSource(src)).toBe(src)
  })

  it('strips stray triple-backtick fences', () => {
    const src = '```mermaid\nflowchart LR\nA --> B\n```'
    expect(sanitizeMermaidSource(src)).toBe('flowchart LR\nA --> B')
  })

  it('handles CJK + colon labels (the regression case)', () => {
    const src = 'flowchart LR\n注册[用户注册: /signup] --> 登录[用户登录]'
    expect(sanitizeMermaidSource(src)).toBe(
      'flowchart LR\n注册[用户注册: /signup] --> 登录[用户登录]',
    )
    // 纯 ASCII id 才会被改写；CJK id 留给 mermaid 自身处理（保守策略）
  })

  it('quotes ASCII-id labels with semicolons', () => {
    const src = 'flowchart LR\nA[step; next] --> B[end]'
    expect(sanitizeMermaidSource(src)).toBe(
      'flowchart LR\nA["step; next"] --> B[end]',
    )
  })
})
