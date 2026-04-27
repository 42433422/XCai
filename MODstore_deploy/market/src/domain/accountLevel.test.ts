import { describe, expect, it } from 'vitest'
import { buildLevelProfileDict, isMeAdminPayload, normalizeMeResponse } from './accountLevel'

describe('accountLevel', () => {
  it('buildLevelProfileDict matches low tiers', () => {
    expect(buildLevelProfileDict(0).level).toBe(1)
    expect(buildLevelProfileDict(0).title).toBe('新手')
    expect(buildLevelProfileDict(1500).level).toBe(2)
    expect(buildLevelProfileDict(4999).level).toBe(2)
    expect(buildLevelProfileDict(5000).level).toBe(3)
  })

  it('normalizes Java-style nested user', () => {
    const flat = normalizeMeResponse({
      user: { id: 9, username: 'a', email: 'a@b.c', is_admin: false, experience: 1200 },
    })
    expect(flat.id).toBe(9)
    expect(flat.username).toBe('a')
    expect(flat.experience).toBe(1200)
    expect(flat.is_admin).toBe(false)
  })

  it('isMeAdminPayload reads nested admin', () => {
    expect(isMeAdminPayload({ user: { id: 1, username: 'x', is_admin: true } })).toBe(true)
    expect(isMeAdminPayload({ user: { id: 1, username: 'x', admin: true } })).toBe(true)
    expect(isMeAdminPayload({ id: 1, username: 'x', is_admin: true })).toBe(true)
    expect(isMeAdminPayload({ user: { id: 1, username: 'x', is_admin: false } })).toBe(false)
  })
})
