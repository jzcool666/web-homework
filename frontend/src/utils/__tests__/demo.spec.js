/**
 * SPEC-012 演示显示工具。
 *
 * 重点：位序必须是 Q3Q2Q1Q0（Q3 最高位），波形槽位来自服务器历史，
 * 且本模块**不提供**任何下一状态的本地推算——预测只能来自服务器的 next_q。
 */

import { describe, expect, it } from 'vitest'

import * as demo from '@/utils/demo'
import {
  actionLabel,
  bitLabels,
  bitsOf,
  formatInputs,
  formatStateValue,
  inputsFor,
  inputLabel,
  modelLabel,
  risingCount,
  rowSummary,
  stepPath,
  waveSignals,
  waveWidth,
} from '@/utils/demo'

const HISTORY = [
  { seq: 1, op: 'set', clock: 0, inputs: { d: 1, reset: 0 }, q_before: 0, q: 0, rising: false, step_no: 0 },
  { seq: 2, op: 'toggle_clock', clock: 1, inputs: { d: 1, reset: 0 }, q_before: 0, q: 1, rising: true, step_no: 1 },
  { seq: 3, op: 'set', clock: 1, inputs: { d: 0, reset: 0 }, q_before: 1, q: 1, rising: false, step_no: 1 },
  { seq: 4, op: 'toggle_clock', clock: 0, inputs: { d: 0, reset: 0 }, q_before: 1, q: 1, rising: false, step_no: 1 },
]

describe('位序与取值', () => {
  it('D/JK 只有 Q，计数器与移位寄存器是 Q3Q2Q1Q0', () => {
    expect(bitLabels('d')).toEqual(['Q'])
    expect(bitLabels('jk')).toEqual(['Q'])
    expect(bitLabels('counter')).toEqual(['Q3', 'Q2', 'Q1', 'Q0'])
    expect(bitLabels('shift')).toEqual(['Q3', 'Q2', 'Q1', 'Q0'])
  })

  it('Q3 是最高位：1010 拆成 1 0 1 0', () => {
    expect(bitsOf(0b1010, 'shift')).toEqual([1, 0, 1, 0])
    expect(bitsOf(0b1101, 'shift')).toEqual([1, 1, 0, 1])
    expect(formatStateValue(0b1010, 'shift')).toBe('1010（10）')
    expect(bitsOf(1, 'd')).toEqual([1])
    expect(bitsOf(0, 'jk')).toEqual([0])
  })

  it('输入按模型列出并带上标签', () => {
    expect(inputsFor('d')).toEqual(['d', 'reset'])
    expect(inputsFor('jk')).toEqual(['j', 'k', 'reset'])
    expect(inputsFor('counter')).toEqual(['enable', 'reset'])
    expect(inputsFor('shift')).toEqual(['enable', 'serial_in', 'reset'])
    expect(inputsFor('unknown')).toEqual([])
    expect(inputLabel('serial_in')).toBe('SI')
    expect(formatInputs({ enable: 1, serial_in: 0, reset: 0 }, 'shift')).toBe('EN=1 SI=0 RESET=0')
    expect(formatInputs(undefined, 'counter')).toBe('EN=0 RESET=0')
  })

  it('模型名称未知时给出可读占位', () => {
    expect(modelLabel('counter')).toBe('4 位计数器')
    expect(modelLabel('cpu')).toBe('未知模型')
  })
})

describe('波形槽位', () => {
  it('每个历史行占一个槽位，电平取事件之后的值', () => {
    const signals = waveSignals(HISTORY, 'd')
    expect(signals.map((s) => s.clock)).toEqual([0, 1, 1, 0])
    expect(signals.map((s) => s.bits[0])).toEqual([0, 1, 1, 1])
    expect(signals.map((s) => s.rising)).toEqual([false, true, false, false])
  })

  it('有效沿数量与 step_no 一致', () => {
    expect(risingCount(HISTORY)).toBe(1)
    expect(risingCount([])).toBe(0)
    expect(waveWidth(HISTORY, 26)).toBe(4 * 26)
    expect(waveWidth([], 26)).toBe(26)
  })

  it('阶梯路径在槽边界转折，电平不变时不画竖线', () => {
    expect(stepPath([0, 1, 1, 0], { slot: 10, yLow: 20, yHigh: 5 })).toBe(
      'M0 20 H10 V5 H20 V5 H30 V20 H40',
    )
    // 恒定电平只有水平段
    expect(stepPath([1, 1], { slot: 10, yLow: 20, yHigh: 5 })).toBe('M0 5 H10 V5 H20')
    expect(stepPath([], {})).toBe('')
  })
})

describe('历史行文案', () => {
  it('区分有效沿与保持', () => {
    expect(actionLabel('toggle_clock')).toBe('切换时钟')
    expect(actionLabel('set')).toBe('设置输入')
    expect(actionLabel('reset_view')).toBe('复位到初态')
    expect(rowSummary(HISTORY[1], 'd')).toContain('0 → 1')
    expect(rowSummary(HISTORY[0], 'd')).toContain('保持')
  })
})

describe('不提供本地预测', () => {
  it('工具模块不导出任何计算下一状态的函数', () => {
    // 预测是否可见只能由服务器的 reveal_next / next_q 决定
    const suspicious = Object.keys(demo).filter((name) => /^(compute|predict|calc).*next|nextQ|next_q/i.test(name))
    expect(suspicious).toEqual([])
  })
})
