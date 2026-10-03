/**
 * SPEC-007 检索问答的显示工具。
 *
 * 重点是相似度只作百分比展示，并且 null 与真实的 0 要区分开（UI 基线第 14 节）。
 */

import { describe, expect, it } from 'vitest'

import { formatSimilarity, matchSummary, sourceLabel } from '@/utils/qa'

describe('相似度展示', () => {
  it('比例转百分比', () => {
    expect(formatSimilarity(0.42)).toBe('42%')
    expect(formatSimilarity(1)).toBe('100%')
    expect(formatSimilarity(0.005)).toBe('1%')
  })

  it('缺失值与真实 0 区分开', () => {
    expect(formatSimilarity(null)).toBe('—')
    expect(formatSimilarity(undefined)).toBe('—')
    expect(formatSimilarity('x')).toBe('—')
    expect(formatSimilarity(0)).toBe('0%')
  })
})

describe('来源与匹配说明', () => {
  it('来源只显示主机名', () => {
    expect(sourceLabel('https://computationstructures.org/notes/sequential_logic/notes.html')).toBe(
      'computationstructures.org',
    )
    expect(sourceLabel('')).toBe('')
    expect(sourceLabel(null)).toBe('')
  })

  it('无法解析的链接原样返回，不抛错', () => {
    expect(sourceLabel('not a url')).toBe('not a url')
  })

  it('没有匹配时明确说明，而不是留空', () => {
    expect(matchSummary(false, 0)).toBe('没有可靠匹配')
    expect(matchSummary(true, 0)).toBe('没有可靠匹配')
    expect(matchSummary(true, 2)).toBe('找到 2 个可能相关的知识点')
  })
})
