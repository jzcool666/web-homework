import { describe, expect, it } from 'vitest'

import {
  AUTOSAVE_DELAY_MS,
  answerPayload,
  bucketWidth,
  defaultOptions,
  formatRate,
  formatScore,
  isCorrectSelection,
  nextOptionKey,
  normalizeAnswer,
  optionLabel,
  saveStatus,
  selectedFor,
  selectionText,
  toggleSelection,
  unansweredCount,
} from '@/utils/assessment'

describe('SPEC-009 答案集合比较', () => {
  it('集合完全相同才算答对，空答案一律错误', () => {
    expect(isCorrectSelection(['A'], ['A'])).toBe(true)
    expect(isCorrectSelection(['B', 'A'], ['A', 'B'])).toBe(true)
    expect(isCorrectSelection(['A'], ['A', 'B'])).toBe(false)
    expect(isCorrectSelection(['A', 'B', 'C'], ['A', 'B'])).toBe(false)
    expect(isCorrectSelection([], ['A'])).toBe(false)
    expect(isCorrectSelection(['A'], [])).toBe(false)
  })
})

describe('SPEC-009 题型与选项换算', () => {
  it('判断题固定 true/false，其余默认两个字母选项', () => {
    expect(defaultOptions('boolean').map((option) => option.key)).toEqual(['true', 'false'])
    expect(defaultOptions('single').map((option) => option.key)).toEqual(['A', 'B'])
  })

  it('沿用第一个未占用的字母作为新选项 key', () => {
    expect(nextOptionKey([])).toBe('A')
    expect(nextOptionKey(['A', 'B'])).toBe('C')
    expect(nextOptionKey(['B'])).toBe('A')
  })

  it('单选/判断只保留一个答案，切换题型会裁掉多余答案', () => {
    expect(normalizeAnswer('multiple', ['A', 'B'], ['A', 'B', 'C'])).toEqual(['A', 'B'])
    expect(normalizeAnswer('single', ['A', 'B'], ['A', 'B'])).toEqual(['A'])
    expect(normalizeAnswer('boolean', ['true'], ['true', 'false'])).toEqual(['true'])
    expect(normalizeAnswer('single', ['X'], ['A', 'B'])).toEqual([])
  })

  it('单选再点同一项取消，多选可累加', () => {
    expect(toggleSelection([], 'A', false)).toEqual(['A'])
    expect(toggleSelection(['A'], 'A', false)).toEqual([])
    expect(toggleSelection(['A'], 'B', true)).toEqual(['A', 'B'])
    expect(toggleSelection(['A', 'B'], 'A', true)).toEqual(['B'])
  })
})

describe('SPEC-009 作答与成绩展示', () => {
  const answers = [
    { item_id: 1, selected: ['A'] },
    { item_id: 2, selected: [] },
  ]

  it('按条目取回已保存的选项，缺省为空数组', () => {
    expect(selectedFor(answers, 1)).toEqual(['A'])
    expect(selectedFor(answers, 2)).toEqual([])
    expect(selectedFor(answers, 99)).toEqual([])
  })

  it('统计未作答题数用于提交前提示', () => {
    const items = [{ id: 1 }, { id: 2 }, { id: 3 }]
    expect(unansweredCount(items, answers)).toBe(2)
  })

  it('反馈未公开时分数显示为待公开而不是 0', () => {
    expect(formatScore(null, 20)).toBe('待公开')
    expect(formatScore(undefined, 20)).toBe('待公开')
    expect(formatScore(0, 20)).toBe('0 / 20')
    expect(formatScore(15, 20)).toBe('15 / 20')
  })

  it('把选项 key 还原成可读文案', () => {
    const options = [{ key: 'A', label: '保持' }, { key: 'B', label: '翻转' }]
    expect(optionLabel(options, 'A')).toBe('保持')
    expect(optionLabel(options, 'Z')).toBe('Z')
    expect(selectionText(options, ['A', 'B'])).toBe('保持、翻转')
    expect(selectionText(options, [])).toBe('未作答')
  })
})

describe('SPEC-010 草稿自动保存与状态提示', () => {
  it('短延迟保存窗口为 1 秒', () => {
    expect(AUTOSAVE_DELAY_MS).toBe(1000)
  })

  it('作答映射按接口要求整理成 answers 数组', () => {
    expect(answerPayload({ 1: ['A'], 2: [] })).toEqual([
      { item_id: 1, selected: ['A'] },
      { item_id: 2, selected: [] },
    ])
    expect(answerPayload({})).toEqual([])
    expect(answerPayload(undefined)).toEqual([])
  })

  it('离线或保存失败时显示未保存，不伪报成功', () => {
    expect(saveStatus({ online: false, lastSavedAt: '10:00:00' })).toEqual({
      tone: 'danger',
      text: '离线，最后保存 10:00:00',
    })
    expect(saveStatus({ online: false })).toEqual({ tone: 'danger', text: '离线，尚未保存' })
    expect(saveStatus({ failed: true, lastSavedAt: '10:00:00' }).tone).toBe('danger')
    expect(saveStatus({ failed: true }).text).toBe('保存失败，尚未保存')
  })

  it('区分保存中、已保存与尚未保存', () => {
    expect(saveStatus({ saving: true })).toEqual({ tone: 'warning', text: '保存中…' })
    expect(saveStatus({ lastSavedAt: '10:00:00' })).toEqual({
      tone: 'success',
      text: '已保存 10:00:00',
    })
    expect(saveStatus({})).toEqual({ tone: 'neutral', text: '尚未保存' })
  })

  it('保存中优先于旧的已保存时间', () => {
    expect(saveStatus({ saving: true, lastSavedAt: '10:00:00' }).tone).toBe('warning')
  })

  it('修改已保存的答案后立即显示未保存更改', () => {
    expect(saveStatus({ dirty: true, lastSavedAt: '10:00:00' })).toEqual({
      tone: 'warning',
      text: '有未保存更改，最后保存 10:00:00',
    })
  })
})

describe('SPEC-010 统计展示换算', () => {
  it('分数段条形按最大计数归一', () => {
    const counts = [{ count: 2 }, { count: 0 }, { count: 1 }]
    expect(bucketWidth(2, counts)).toBe(100)
    expect(bucketWidth(1, counts)).toBe(50)
    expect(bucketWidth(0, counts)).toBe(0)
    expect(bucketWidth(0, [])).toBe(0)
    expect(bucketWidth(5, [{ count: 0 }])).toBe(500)
  })

  it('正确率为 null 时显示占位符而不是 0%', () => {
    expect(formatRate(null)).toBe('—')
    expect(formatRate(undefined)).toBe('—')
    expect(formatRate(0)).toBe('0%')
    expect(formatRate(0.3333)).toBe('33.3%')
    expect(formatRate(1)).toBe('100%')
  })
})
