import { describe, expect, it } from 'vitest'
import {
  formatRefundTime,
  refundStatusText,
  validateRefundForm,
} from './refundStatus'

describe('refund helpers', () => {
  it('validates refund form before submit', () => {
    expect(validateRefundForm('', '有效原因')).toBe('请填写订单号')
    expect(validateRefundForm('ORD1', '短')).toContain('至少')
    expect(validateRefundForm('ORD1', '这是一个有效退款原因')).toBe('')
  })

  it('maps refund statuses to readable labels', () => {
    expect(refundStatusText('pending')).toBe('待审核')
    expect(refundStatusText('refunded')).toBe('已退款')
    expect(refundStatusText('unknown_status')).toBe('unknown_status')
  })

  it('formats refund time defensively', () => {
    expect(formatRefundTime('')).toBe('—')
    expect(formatRefundTime('bad-date')).toBe('bad-date')
    expect(formatRefundTime('2026-01-02T03:04:05Z')).toContain('2026')
  })
})
