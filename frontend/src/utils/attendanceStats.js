/**
 * 出勤统计页面的换算与口径文案（SPEC-003）。
 *
 * 措辞是口径的一部分：请假不计入分母；没有可计算的出勤率时分母为零，
 * 显示「无分母」而不是 0%；相关系数只描述同窗口共同样本的线性相关，
 * 不代表因果。这些说明由单测守住。
 */

import { defaultUtcWindow, dayStamp } from '@/utils/analytics'

export const ATTENDANCE_WINDOW_NOTE =
  '出勤按任务的 opens_at 落入窗口选择，且只统计已结算任务；进行中的任务不进入分母。' +
  '出勤率 =（出勤 + 迟到）/（出勤 + 迟到 + 缺勤），请假从分母中排除。'

export const CORRELATION_NOTE =
  '相关系数只用同窗口内同时具备出勤率与百分制测评均分的学生；' +
  '共同样本少于 5 名、或任一路取值恒定时不计算。相关不代表因果。'

/** null 表示没有可计任务（分母为零），不是 0%。 */
export function attendanceRateText(rate) {
  if (rate === null || rate === undefined) return '—（无分母）'
  return `${Math.round(rate * 1000) / 10}%`
}

/** 相关系数展示：未计算时带上原因，不显示成 0。 */
export function correlationText(correlation) {
  if (!correlation) return '—'
  if (correlation.coefficient === null || correlation.coefficient === undefined) {
    return `—（${correlation.reason ?? '未计算'}）`
  }
  return String(correlation.coefficient)
}

/** 页面与导出必须使用同一查询串。 */
export function attendanceQuery({ classId, from, to }) {
  const params = new URLSearchParams({ class_id: String(classId) })
  if (from && to) {
    params.set('from', dayStamp(from))
    params.set('to', dayStamp(to))
  }
  return params.toString()
}

export function defaultAttendanceWindow(now = new Date()) {
  return defaultUtcWindow(now)
}

export const COUNT_LABELS = {
  present: '出勤',
  late: '迟到',
  leave: '请假',
  absent: '缺勤',
}
