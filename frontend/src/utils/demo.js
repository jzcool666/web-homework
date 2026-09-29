/**
 * SPEC-012 演示显示工具。
 *
 * 只做「服务器状态 → 界面文字与波形几何」的转换：本文件**不**计算下一个状态。
 * 预测是否可见完全由服务器决定（reveal_next=false 时 next_q 为 null），
 * 前端另算一份会绕过该规则，也会与后端规则漂移。
 */

export const MODEL_LABELS = {
  d: 'D 触发器',
  jk: 'JK 触发器',
  counter: '4 位计数器',
  shift: '4 位移位寄存器',
}

// 各模型的输入引脚；顺序即界面上的排列顺序
export const MODEL_INPUTS = {
  d: ['d', 'reset'],
  jk: ['j', 'k', 'reset'],
  counter: ['enable', 'reset'],
  shift: ['enable', 'serial_in', 'reset'],
}

export const INPUT_LABELS = {
  d: 'D',
  j: 'J',
  k: 'K',
  enable: 'EN',
  serial_in: 'SI',
  reset: 'RESET',
}

export const INPUT_HINTS = {
  enable: '0 保持',
  serial_in: '进入 Q3',
  reset: '同步高有效',
}

export function modelLabel(simulatorType) {
  return MODEL_LABELS[simulatorType] ?? '未知模型'
}

export function inputsFor(simulatorType) {
  return MODEL_INPUTS[simulatorType] ?? []
}

export function inputLabel(name) {
  return INPUT_LABELS[name] ?? name
}

/** 显示位序：D/JK 只有 Q；计数器与移位寄存器为 Q3Q2Q1Q0（Q3 最高位）。 */
export function bitLabels(simulatorType) {
  return simulatorType === 'counter' || simulatorType === 'shift'
    ? ['Q3', 'Q2', 'Q1', 'Q0']
    : ['Q']
}

/** 把整数状态拆成显示位序的 0/1 数组。 */
export function bitsOf(value, simulatorType) {
  const labels = bitLabels(simulatorType)
  return labels.map((_, index) => (value >> (labels.length - 1 - index)) & 1)
}

export function formatBits(value, simulatorType) {
  return bitsOf(value, simulatorType).join('')
}

export function formatStateValue(value, simulatorType) {
  return `${formatBits(value, simulatorType)}（${value}）`
}

/** 输入字符串：D=1 RESET=0。 */
export function formatInputs(inputs, simulatorType) {
  const names = inputsFor(simulatorType)
  if (names.length === 0) return '—'
  return names.map((name) => `${inputLabel(name)}=${inputs?.[name] ?? 0}`).join(' ')
}

/** 已执行的有效上升沿数量，用于「第 N 拍」文案。 */
export function risingCount(history) {
  return (history ?? []).filter((row) => row.rising).length
}

/**
 * 波形槽位：history 每行是一次事件，正好占半个时钟周期。
 * clock 为事件后的电平；Q 只在有效沿变化，其余槽位保持。
 */
export function waveSignals(history, simulatorType) {
  return (history ?? []).map((row, index) => ({
    index,
    seq: row.seq ?? index + 1,
    clock: row.clock ? 1 : 0,
    bits: bitsOf(row.q ?? 0, simulatorType),
    rising: Boolean(row.rising),
    stepNo: row.step_no ?? 0,
  }))
}

/**
 * 阶梯波形路径：每槽一个电平，槽边界竖线连接。
 * 返回 SVG path 的 d 属性；levels 为 0/1 数组。
 */
export function stepPath(levels, { slot = 26, yLow = 0, yHigh = 1 } = {}) {
  if (!levels.length) return ''
  const y = (level) => (level ? yHigh : yLow)
  let path = `M0 ${y(levels[0])}`
  for (let index = 1; index < levels.length; index += 1) {
    path += ` H${index * slot} V${y(levels[index])}`
  }
  return `${path} H${levels.length * slot}`
}

/** 波形图总宽度（含左侧信号名留白由组件负责）。 */
export function waveWidth(history, slot = 26) {
  return Math.max(1, (history ?? []).length) * slot
}

/** 事件历史的一行摘要，用于表格与无障碍文本。 */
export function rowSummary(row, simulatorType) {
  const action =
    row.op === 'set' ? '设置输入' : row.op === 'toggle_clock' ? '切换时钟' : '复位到初态'
  const change = row.rising
    ? `${formatBits(row.q_before ?? 0, simulatorType)} → ${formatBits(row.q ?? 0, simulatorType)}`
    : '保持'
  return `第 ${row.seq ?? '—'} 次事件：${action}，CLK=${row.clock ? 1 : 0}，${change}`
}

export function actionLabel(op) {
  return op === 'set' ? '设置输入' : op === 'toggle_clock' ? '切换时钟' : op === 'reset_view' ? '复位到初态' : op
}
