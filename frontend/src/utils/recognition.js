/**
 * 状态表识别页面的展示换算与口径文案（SPEC-017）。
 *
 * 措辞是口径的一部分：识别结果只是辅助信息，必须标注「需人工核对」；
 * 实验判分仍由后端按实验配置与输入序列重算，不采用识别结论或客户端字段。
 */

export const STATUS_LABELS = {
  done: '识别完成',
  failed: '识别失败',
}

export const ERROR_HINTS = {
  IMAGE_DECODE_FAILED: '图片无法解码',
  GRID_NOT_DETECTED: '未检测到网格',
  SHAPE_MISMATCH: '行列数不符',
  CELL_NOT_BINARY: '格内非 0/1',
  CELL_UNCERTAIN: '字符不确定',
}

export const REVIEW_NOTE =
  '识别结果为辅助信息，需人工核对。实验判分仍由后端按实验配置与输入序列重算，' +
  '不采用识别结论或客户端字段。'

export const FORMAT_NOTE =
  '格式 v1：白底黑线的规则网格，恰好 4 列、2—17 行，每格一个印刷体 0 或 1，' +
  '无表头、合并格或手写内容；列从左到右为 Q3、Q2、Q1、Q0，行从上到下为连续时钟拍。'

/** 十进制状态值 → 4 位二进制（Q3Q2Q1Q0）。 */
export function bitText(value) {
  if (value === null || value === undefined) return '—'
  return Number(value).toString(2).padStart(4, '0')
}

export function confidenceText(confidence) {
  if (confidence === null || confidence === undefined) return '—'
  return `${(Number(confidence) * 100).toFixed(1)}%`
}

export function transitionText(transition) {
  return `${bitText(transition.from)} → ${bitText(transition.to)}`
}

export function statusText(status) {
  return STATUS_LABELS[status] ?? status ?? '—'
}

export function errorHint(code) {
  return ERROR_HINTS[code] ?? code ?? '识别未完成'
}
