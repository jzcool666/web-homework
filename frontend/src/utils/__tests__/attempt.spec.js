/**
 * SPEC-013 实验预测的显示工具。
 *
 * 重点：拍号从 0 起算显示为「第 N+1 拍」，结果摘要完全依据服务器给出的
 * first_error_index / passed，不在前端推断对错。
 */

import { describe, expect, it } from 'vitest'

import {
  attemptSummary,
  checkpointLabel,
  inputsText,
  predictionRange,
  predictionsOf,
  resultSummary,
  resultTone,
  wrongIndexes,
} from '@/utils/attempt'

describe('拍号与取值范围', () => {
  it('下标 0 显示为第 1 拍', () => {
    expect(checkpointLabel(0)).toBe('第 1 拍')
    expect(checkpointLabel(1)).toBe('第 2 拍')
    expect(checkpointLabel(9)).toBe('第 10 拍')
  })

  it('D/JK 只允许 0 和 1，计数器与移位寄存器允许 0—15', () => {
    expect(predictionRange('d')).toEqual({ min: 0, max: 1 })
    expect(predictionRange('jk')).toEqual({ min: 0, max: 1 })
    expect(predictionRange('counter')).toEqual({ min: 0, max: 15 })
    expect(predictionRange('shift')).toEqual({ min: 0, max: 15 })
  })

  it('按检查点数生成空答案', () => {
    expect(predictionsOf([{ index: 0 }, { index: 1 }])).toEqual(['', ''])
    expect(predictionsOf(undefined)).toEqual([])
  })
})

describe('输入与结果文案', () => {
  it('输入按引脚列出', () => {
    expect(inputsText({ enable: 1, reset: 0 })).toBe('EN=1 RESET=0')
    expect(inputsText({ serial_in: 1 })).toBe('SI=1')
    expect(inputsText({})).toBe('—')
    expect(inputsText(undefined)).toBe('—')
  })

  it('逐位标出与标准答案不同的位置', () => {
    expect([...wrongIndexes([5, 0, 1, 2], [5, 6, 1, 3])].sort()).toEqual([1, 3])
    expect([...wrongIndexes([5, 0, 1, 2], [5, 0, 1, 2])]).toEqual([])
    expect([...wrongIndexes([5, 0], [5])].sort()).toEqual([1])
  })

  it('摘要依据服务器的 passed 与 first_error_index', () => {
    expect(resultSummary({ passed: true, first_error_index: null })).toBe('全部预测正确')
    expect(resultSummary({ passed: false, first_error_index: 1 })).toBe('第 2 拍出错')
    expect(resultSummary({ passed: false, first_error_index: 0 })).toBe('第 1 拍出错')
    expect(resultSummary(null)).toBe('')
    expect(resultTone({ passed: true })).toBe('success')
    expect(resultTone({ passed: false })).toBe('danger')
    expect(resultTone(null)).toBe('neutral')
  })

  it('历史摘要包含结果与拍数', () => {
    const summary = attemptSummary({ passed: false, first_error_index: 1, actual: [5, 6, 1, 2] }, 'counter')
    expect(summary).toContain('第 2 拍出错')
    expect(summary).toContain('共 4 拍')
    expect(summary).toContain('0101')
  })
})
