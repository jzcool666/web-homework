import { describe, expect, it } from 'vitest'

import {
  LEAVE_STATUS_LABEL,
  PHASE_LABEL,
  STATUS_LABEL,
  defaultWindow,
  formatLocal,
  localInputToUtc,
  taskPhase,
  toUtcStamp,
  utcToLocalInput,
} from '@/utils/attendance'

const OPEN = '2026-09-29T02:00:00Z'
const LATE = '2026-09-29T02:05:00Z'
const CLOSES = '2026-09-29T02:30:00Z'

function task() {
  return { opens_at: OPEN, late_at: LATE, closes_at: CLOSES }
}

describe('SPEC-002 考勤时间换算', () => {
  it('输出接口要求的秒级 UTC，不带毫秒', () => {
    expect(toUtcStamp(new Date('2026-09-29T02:00:00Z'))).toBe(OPEN)
    expect(toUtcStamp(new Date(Date.UTC(2026, 8, 29, 2, 0, 0, 987)))).toBe(OPEN)
  })

  it('空值与非法输入返回 null，不产生 Invalid Date', () => {
    expect(localInputToUtc('')).toBeNull()
    expect(localInputToUtc(null)).toBeNull()
    expect(localInputToUtc('不是时间')).toBeNull()
  })

  it('datetime-local 与 UTC 字符串互相转换后保持不变', () => {
    for (const stamp of [OPEN, LATE, CLOSES, '2026-01-01T00:00:00Z']) {
      expect(localInputToUtc(utcToLocalInput(stamp))).toBe(stamp)
    }
  })

  it('formatLocal 对空值给出占位符而不是 1970 年', () => {
    expect(formatLocal(null)).toBe('—')
    expect(formatLocal('bad')).toBe('—')
  })
})

describe('SPEC-002 任务阶段判定', () => {
  it('按 [opens_at, closes_at) 与 late_at 划分四个阶段', () => {
    expect(taskPhase(task(), new Date('2026-09-29T01:59:59Z'))).toBe('upcoming')
    expect(taskPhase(task(), new Date(OPEN))).toBe('open')
    expect(taskPhase(task(), new Date('2026-09-29T02:04:59Z'))).toBe('open')
    expect(taskPhase(task(), new Date(LATE))).toBe('late')
    expect(taskPhase(task(), new Date('2026-09-29T02:29:59Z'))).toBe('late')
    expect(taskPhase(task(), new Date(CLOSES))).toBe('closed')
    expect(taskPhase(task(), new Date('2026-09-29T03:00:00Z'))).toBe('closed')
  })

  it('每个阶段都有中文标签', () => {
    for (const phase of ['upcoming', 'open', 'late', 'closed']) {
      expect(PHASE_LABEL[phase]).toBeTruthy()
    }
  })
})

describe('SPEC-002 展示标签与默认窗口', () => {
  it('覆盖后端全部出勤与审批状态', () => {
    for (const status of ['pending', 'present', 'late', 'leave', 'absent']) {
      expect(STATUS_LABEL[status]).toBeTruthy()
    }
    for (const status of ['pending', 'approved', 'rejected']) {
      expect(LEAVE_STATUS_LABEL[status]).toBeTruthy()
    }
  })

  it('默认窗口满足 opens_at ≤ late_at < closes_at', () => {
    const window = defaultWindow(new Date(OPEN))
    expect(window.opens_at).toBe(OPEN)
    expect(window.late_at > window.opens_at).toBe(true)
    expect(window.closes_at > window.late_at).toBe(true)
    expect(window.opens_at <= window.late_at && window.late_at < window.closes_at).toBe(true)
  })
})
