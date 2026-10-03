/**
 * 考勤页面的时间与状态换算（SPEC-002）。
 *
 * 接口时间一律是带 Z 的 RFC3339 UTC 秒级字符串；页面输入框（datetime-local）是
 * 浏览器本地时间。这里集中做两种表示之间的转换，避免各组件各写一份。
 * 签到判定完全由服务器完成，这里的 phase 只用于展示。
 */

/** Date → "YYYY-MM-DDTHH:MM:SSZ"（接口要求的秒级 UTC）。 */
export function toUtcStamp(date) {
  return date.toISOString().replace(/\.\d{3}Z$/, 'Z')
}

/** datetime-local 的本地时间值 → 带 Z 的 UTC 字符串；空值或非法值返回 null。 */
export function localInputToUtc(value) {
  if (!value) return null
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return null
  return toUtcStamp(date)
}

/** 带 Z 的 UTC 字符串 → datetime-local 需要的本地时间值。 */
export function utcToLocalInput(stamp) {
  if (!stamp) return ''
  const date = new Date(stamp)
  if (Number.isNaN(date.getTime())) return ''
  const pad = (n) => String(n).padStart(2, '0')
  return (
    `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}` +
    `T${pad(date.getHours())}:${pad(date.getMinutes())}`
  )
}

/** 按 Asia/Shanghai 之外仍可读的本地时区显示时间。 */
export function formatLocal(stamp) {
  if (!stamp) return '—'
  const date = new Date(stamp)
  if (Number.isNaN(date.getTime())) return '—'
  const pad = (n) => String(n).padStart(2, '0')
  return (
    `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ` +
    `${pad(date.getHours())}:${pad(date.getMinutes())}`
  )
}

/** 任务相对当前时间的阶段：未开始 / 可签到 / 迟到中 / 已结束。 */
export function taskPhase(task, now = new Date()) {
  const opens = new Date(task.opens_at).getTime()
  const late = new Date(task.late_at).getTime()
  const closes = new Date(task.closes_at).getTime()
  const at = now.getTime()
  if (at < opens) return 'upcoming'
  if (at < late) return 'open'
  if (at < closes) return 'late'
  return 'closed'
}

export const PHASE_LABEL = {
  upcoming: '未开始',
  open: '可签到',
  late: '迟到中',
  closed: '已结束',
}

export const STATUS_LABEL = {
  pending: '待签到',
  present: '出勤',
  late: '迟到',
  leave: '请假',
  absent: '缺勤',
}

export const LEAVE_STATUS_LABEL = {
  pending: '待审批',
  approved: '已批准',
  rejected: '已驳回',
}

/** 创建任务表单的默认窗口：现在开始，5 分钟后算迟到，20 分钟后结束。 */
export function defaultWindow(now = new Date()) {
  const shift = (minutes) => toUtcStamp(new Date(now.getTime() + minutes * 60_000))
  return {
    opens_at: shift(0),
    late_at: shift(5),
    closes_at: shift(20),
  }
}
