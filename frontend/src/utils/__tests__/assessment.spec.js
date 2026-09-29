import { describe, expect, it } from 'vitest'

import {
  defaultOptions,
  formatScore,
  isCorrectSelection,
  nextOptionKey,
  normalizeAnswer,
  optionLabel,
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
