import { describe, expect, it } from 'vitest'

import {
  availableFactorsText,
  clusterText,
  factorText,
  levelText,
  levelTone,
  scoreText,
} from '@/utils/warnings'

describe('warnings utils', () => {
  it('样本不足时分数显示「—」而不是 0', () => {
    expect(scoreText(null)).toBe('—')
    expect(scoreText(undefined)).toBe('—')
    expect(scoreText(70)).toBe('70.0')
    expect(scoreText(0)).toBe('0.0')
  })

  it('等级文案与配色：样本不足中性，高风险用危险色', () => {
    expect(levelText('insufficient')).toBe('样本不足')
    expect(levelText('high')).toBe('高')
    expect(levelTone('insufficient')).toBe('neutral')
    expect(levelTone('low')).toBe('success')
    expect(levelTone('high')).toBe('danger')
  })

  it('不可用的因素显示「未计入」，可用显示两位小数', () => {
    expect(factorText(null)).toBe('未计入')
    expect(factorText(0.5)).toBe('0.50')
    expect(factorText(0)).toBe('0.00')
  })

  it('分组标签：未分组显示「—」', () => {
    expect(clusterText(null)).toBe('—')
    expect(clusterText(0)).toBe('组 0')
    expect(clusterText(2)).toBe('组 2')
  })

  it('可用因素列表转成中文标签', () => {
    expect(availableFactorsText(['attendance', 'accuracy'])).toBe('出勤、知识点首答')
    expect(availableFactorsText([])).toBe('无')
  })
})
