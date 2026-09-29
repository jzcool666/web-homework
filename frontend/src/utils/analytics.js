/**
 * 学习进度与资源统计页面的纯换算（SPEC-006）。
 *
 * 这个模块的措辞是口径的一部分：进度是「当前快照近似」，页面与导出都不能把它
 * 写成历史精确掌握率或学习时长，因此把说明文案固定在常量里并由单测守住。
 */

export const PROGRESS_BASIS = 'current_completed_before_to'

/** 进度口径说明：必须提到快照近似，且不得出现掌握率/学习时长这类说法。 */
export const PROGRESS_BASIS_NOTE =
  '进度为当前快照近似：分子是当前仍标记完成、且完成时间早于窗口结束的知识点数，' +
  '分母是当前已发布知识点数；撤销过完成记录的历史不会重建，也不代表历史精确掌握率或学习时长。'

/** 资源口径说明：访问按 UTC 自然日去重，时间窗只过滤资源事件。 */
export const RESOURCE_WINDOW_NOTE =
  '资源访问按 UTC 自然日统计：同人、同版本、同类型、同一天只算一个去重事件；' +
  '同一人访问多个版本会各计一个事件，但人数只计一次。时间窗只过滤资源事件，不改变进度快照的口径。'

export const STATS_TIMEZONE_NOTE = '统计时区：UTC（自然日边界为 UTC 00:00）。'

/** Date → 'YYYY-MM-DD'（按 UTC 取日）。 */
export function utcDay(date) {
  const pad = (value) => String(value).padStart(2, '0')
  return `${date.getUTCFullYear()}-${pad(date.getUTCMonth() + 1)}-${pad(date.getUTCDate())}`
}

/** 'YYYY-MM-DD' → 接口要求的 UTC 整日边界。 */
export function dayStamp(day) {
  return day ? `${day}T00:00:00Z` : ''
}

/** 默认窗口：最近 30 个 UTC 自然日，截止到当前 UTC 日的下一日 00:00。 */
export function defaultUtcWindow(now = new Date()) {
  const tomorrow = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate() + 1))
  const start = new Date(tomorrow.getTime() - 30 * 24 * 60 * 60 * 1000)
  return { from: utcDay(start), to: utcDay(tomorrow) }
}

/** 组装查询串；进度与导出的筛选条件必须完全一致。 */
export function analyticsQuery({ classId, from, to, chapterId }) {
  const params = new URLSearchParams({ class_id: String(classId) })
  if (from && to) {
    params.set('from', dayStamp(from))
    params.set('to', dayStamp(to))
  }
  if (chapterId) params.set('chapter_id', String(chapterId))
  return params.toString()
}

/** 完成率的展示口径：null 表示没有已发布知识点，不是 0%。 */
export function rateText(rate) {
  if (rate === null || rate === undefined) return '—（无已发布知识点）'
  return `${Math.round(rate * 1000) / 10}%`
}
