import { describe, expect, it } from 'vitest'

import {
  bitText,
  confidenceText,
  errorHint,
  statusText,
  transitionText,
} from '@/utils/recognition'

describe('recognition utils', () => {
  it('状态值转成 4 位二进制（Q3Q2Q1Q0）', () => {
    expect(bitText(0)).toBe('0000')
    expect(bitText(5)).toBe('0101')
    expect(bitText(8)).toBe('1000')
    expect(bitText(15)).toBe('1111')
    expect(bitText(null)).toBe('—')
  })

  it('置信度按百分数展示，缺失显示「—」', () => {
    expect(confidenceText(0.9375)).toBe('93.8%')
    expect(confidenceText(1)).toBe('100.0%')
    expect(confidenceText(null)).toBe('—')
  })

  it('次态对用二进制展示', () => {
    expect(transitionText({ from: 5, to: 0 })).toBe('0101 → 0000')
    expect(transitionText({ from: 8, to: 1 })).toBe('1000 → 0001')
  })

  it('状态与失败原因都有中文标签', () => {
    expect(statusText('done')).toBe('识别完成')
    expect(statusText('failed')).toBe('识别失败')
    expect(errorHint('GRID_NOT_DETECTED')).toBe('未检测到网格')
    expect(errorHint('CELL_NOT_BINARY')).toBe('格内非 0/1')
    expect(errorHint('SOMETHING_ELSE')).toBe('SOMETHING_ELSE')
  })
})
