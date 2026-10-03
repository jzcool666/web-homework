/**
 * SPEC-013 实验预测的显示工具。
 *
 * 只做「服务器的计算结果 → 界面文字」的转换：标准状态一律来自 E050 的响应，
 * 这里不重算任何一个状态，也不推断哪些拍是对的——first_error_index 由服务器给出。
 */

import { bitLabels, formatBits, inputLabel } from '@/utils/demo'

/** 检查点的显示名：index 从 0 开始，界面显示第 index+1 拍。 */
export function checkpointLabel(index) {
  return `第 ${index + 1} 拍`
}

/** 该模型一次预测的取值范围，与后端 state_range 一致（D/JK 为 0—1）。 */
export function predictionRange(simulatorType) {
  return simulatorType === 'd' || simulatorType === 'jk' ? { min: 0, max: 1 } : { min: 0, max: 15 }
}

export function predictionsOf(checkpoints) {
  return (checkpoints ?? []).map(() => '')
}

/** 该拍输入的文字，例如 "EN=1 RESET=0"。 */
export function inputsText(inputs) {
  const entries = Object.entries(inputs ?? {})
  return entries.length ? entries.map(([name, value]) => `${inputLabel(name)}=${value}`).join(' ') : '—'
}

/** 出错位置集合：只有服务器给出的 first_error_index 之后仍可能有差异，逐位标出。 */
export function wrongIndexes(expected, actual) {
  const wrong = new Set()
  const length = Math.max((expected ?? []).length, (actual ?? []).length)
  for (let index = 0; index < length; index += 1) {
    if (expected?.[index] !== actual?.[index]) wrong.add(index)
  }
  return wrong
}

/** 结果摘要：通过，或指出第几拍开始出错。 */
export function resultSummary(result) {
  if (!result) return ''
  if (result.passed) return '全部预测正确'
  const index = result.first_error_index
  if (index === null || index === undefined) return '未通过'
  return `${checkpointLabel(index)}出错`
}

export function resultTone(result) {
  if (!result) return 'neutral'
  return result.passed ? 'success' : 'danger'
}

/** 历史条目的一句话摘要。 */
export function attemptSummary(attempt, simulatorType) {
  if (!attempt) return ''
  const head = attempt.passed ? '通过' : resultSummary(attempt)
  const shown = formatBits(attempt.actual?.[0] ?? 0, simulatorType)
  return `${head} · 共 ${attempt.actual?.length ?? 0} 拍 · 首拍 ${shown}`
}

export function bitLabelsFor(simulatorType) {
  return bitLabels(simulatorType)
}
