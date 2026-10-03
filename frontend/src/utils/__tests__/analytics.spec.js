import { describe, expect, it } from 'vitest'

import {
  PROGRESS_BASIS,
  PROGRESS_BASIS_NOTE,
  RESOURCE_WINDOW_NOTE,
  STATS_TIMEZONE_NOTE,
  analyticsQuery,
  dayStamp,
  defaultUtcWindow,
  rateText,
  utcDay,
} from '@/utils/analytics'

describe('SPEC-006 UTC 整日换算', () => {
  it('按 UTC 取日，不受本地时区影响', () => {
    expect(utcDay(new Date('2026-09-29T23:30:00Z'))).toBe('2026-09-29')
    expect(utcDay(new Date('2026-09-30T00:00:00Z'))).toBe('2026-09-30')
    expect(dayStamp('2026-09-29')).toBe('2026-09-29T00:00:00Z')
    expect(dayStamp('')).toBe('')
  })

  it('默认窗口是最近 30 个 UTC 自然日，截止到当前 UTC 日的下一日', () => {
    const window = defaultUtcWindow(new Date('2026-09-29T06:30:00Z'))
    expect(window.to).toBe('2026-09-30')
    expect(window.from).toBe('2026-08-31')
    // 跨月边界同样成立
    const acrossMonths = defaultUtcWindow(new Date('2026-03-05T12:00:00Z'))
    expect(acrossMonths.to).toBe('2026-03-06')
    expect(acrossMonths.from).toBe('2026-02-04')
  })
})

describe('SPEC-006 筛选条件与导出共用同一查询串', () => {
  it('带日期与章节时组装完整查询串', () => {
    const query = analyticsQuery({ classId: 1, from: '2026-08-31', to: '2026-09-30', chapterId: 3 })
    expect(query).toBe('class_id=1&from=2026-08-31T00%3A00%3A00Z&to=2026-09-30T00%3A00%3A00Z&chapter_id=3')
  })

  it('缺日期时不下发 from/to，缺章节时不带 chapter_id', () => {
    expect(analyticsQuery({ classId: 2 })).toBe('class_id=2')
    expect(analyticsQuery({ classId: 2, from: '2026-08-31', chapterId: '' })).toBe('class_id=2')
  })
})

describe('SPEC-006 进度口径文案', () => {
  it('说明这是当前快照近似，且「掌握率／学习时长」只以否定形式出现', () => {
    expect(PROGRESS_BASIS).toBe('current_completed_before_to')
    expect(PROGRESS_BASIS_NOTE).toContain('当前快照近似')
    expect(PROGRESS_BASIS_NOTE).toContain('不代表历史精确掌握率或学习时长')

    // 每一次提到「掌握率」「学习时长」都必须落在「不代表…」的否定里
    const mentions = (text, word) => text.split(word).length - 1
    const negated = (text, word) => (text.match(new RegExp(`不代表[^。]*${word}`, 'g')) ?? []).length
    expect(mentions(PROGRESS_BASIS_NOTE, '掌握率')).toBe(negated(PROGRESS_BASIS_NOTE, '掌握率'))
    expect(mentions(PROGRESS_BASIS_NOTE, '学习时长')).toBe(negated(PROGRESS_BASIS_NOTE, '学习时长'))
    expect(mentions(PROGRESS_BASIS_NOTE, '掌握率')).toBeGreaterThan(0)
  })

  it('资源口径说明区分去重事件与人数，并标注时间窗只过滤资源', () => {
    expect(RESOURCE_WINDOW_NOTE).toContain('UTC')
    expect(RESOURCE_WINDOW_NOTE).toContain('去重事件')
    expect(RESOURCE_WINDOW_NOTE).toContain('人数只计一次')
    expect(RESOURCE_WINDOW_NOTE).toContain('只过滤资源事件')
    expect(STATS_TIMEZONE_NOTE).toContain('UTC')
  })

  it('完成率为 null 时显示为无已发布知识点而不是 0%', () => {
    expect(rateText(null)).toBe('—（无已发布知识点）')
    expect(rateText(undefined)).toBe('—（无已发布知识点）')
    expect(rateText(0)).toBe('0%')
    expect(rateText(0.75)).toBe('75%')
  })
})
