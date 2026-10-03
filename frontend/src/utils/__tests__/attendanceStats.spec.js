import { describe, expect, it } from 'vitest'

import {
  attendanceQuery,
  attendanceRateText,
  correlationText,
  defaultAttendanceWindow,
} from '@/utils/attendanceStats'

describe('attendanceStats utils', () => {
  it('没有可计任务时显示「无分母」而不是 0%', () => {
    expect(attendanceRateText(null)).toBe('—（无分母）')
    expect(attendanceRateText(undefined)).toBe('—（无分母）')
  })

  it('出勤率按百分数展示', () => {
    expect(attendanceRateText(0)).toBe('0%')
    expect(attendanceRateText(0.75)).toBe('75%')
    expect(attendanceRateText(1)).toBe('100%')
  })

  it('相关系数未计算时带上原因，不显示成 0', () => {
    expect(
      correlationText({ coefficient: null, n: 4, reason: '同时具备出勤与成绩的学生只有 4 名' }),
    ).toContain('只有 4 名')
    expect(correlationText({ coefficient: null, n: 0, reason: null })).toBe('—（未计算）')
    expect(correlationText({ coefficient: 0.87, n: 5, reason: null })).toBe('0.87')
    expect(correlationText(null)).toBe('—')
  })

  it('查询串省略空窗口，且始终带 class_id', () => {
    expect(attendanceQuery({ classId: 3 })).toBe('class_id=3')
    expect(attendanceQuery({ classId: 3, from: '2026-09-01', to: '2026-10-01' })).toBe(
      'class_id=3&from=2026-09-01T00%3A00%3A00Z&to=2026-10-01T00%3A00%3A00Z',
    )
  })

  it('默认窗口为最近 30 个 UTC 自然日', () => {
    const window = defaultAttendanceWindow(new Date('2026-10-02T05:00:00Z'))
    expect(window).toEqual({ from: '2026-09-03', to: '2026-10-03' })
  })
})
