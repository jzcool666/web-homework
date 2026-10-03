import { describe, expect, it } from 'vitest'

import { buildQuery, formatCount, formatRate, statsPath, toUtcStamp } from '@/utils/experimentStats'

describe('experimentStats utils', () => {
  it('无参与时显示「—」而不是 0%', () => {
    expect(formatRate(null)).toBe('—')
    expect(formatRate(undefined)).toBe('—')
  })

  it('比例按百分数展示', () => {
    expect(formatRate(0)).toBe('0.0%')
    expect(formatRate(0.5)).toBe('50.0%')
    expect(formatRate(1)).toBe('100.0%')
  })

  it('计数缺失时显示「—」', () => {
    expect(formatCount(0)).toBe('0')
    expect(formatCount(null)).toBe('—')
  })

  it('空值不出现在查询串里', () => {
    expect(buildQuery({ class_id: 3, from: '', to: undefined, experiment_id: null })).toBe(
      'class_id=3',
    )
  })

  it('statsPath 组合 class_id 与可选筛选', () => {
    expect(statsPath({ classId: 3 })).toBe('/analytics/experiment?class_id=3')
    expect(statsPath({ classId: 3, experimentId: 7, format: 'csv' })).toBe(
      '/analytics/experiment?class_id=3&experiment_id=7&format=csv',
    )
  })

  it('datetime-local 转成秒级 RFC3339 UTC', () => {
    expect(toUtcStamp('')).toBe('')
    expect(toUtcStamp('not-a-date')).toBe('')
    const stamp = toUtcStamp('2026-09-01T12:00')
    expect(stamp).toMatch(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$/)
  })
})
