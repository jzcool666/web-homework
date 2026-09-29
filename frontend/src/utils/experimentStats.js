/**
 * SPEC-014 实验统计页面的展示与查询串逻辑。
 *
 * 后端返回的比例是 0—1 或 null；null 表示「没有可统计的参与」，必须显示成
 * 「—」而不是 0%，避免把缺数据误读成真实零分（PRD 第 6 节）。
 */

export function formatRate(rate) {
  if (rate === null || rate === undefined) return '—'
  return `${(rate * 100).toFixed(1)}%`
}

export function formatCount(value) {
  if (value === null || value === undefined) return '—'
  return String(value)
}

/** datetime-local 的值（本地时间）转成 APIC 要求的 RFC3339 UTC 秒级时间戳。 */
export function toUtcStamp(localValue) {
  if (!localValue) return ''
  const parsed = new Date(localValue)
  if (Number.isNaN(parsed.getTime())) return ''
  return parsed.toISOString().replace(/\.\d{3}Z$/, 'Z')
}

/** 省略空值，保证不把空字符串当成筛选条件发给后端。 */
export function buildQuery(params) {
  const search = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value === null || value === undefined || value === '') continue
    search.set(key, String(value))
  }
  return search.toString()
}

export function statsPath({ classId, from, to, experimentId, format } = {}) {
  const query = buildQuery({
    class_id: classId,
    from,
    to,
    experiment_id: experimentId,
    format,
  })
  return `/analytics/experiment?${query}`
}

/** 汇总口径的说明文字：顶层通过人数是「至少通过一个实验」。 */
export const SUMMARY_HINT =
  '通过人数指至少通过一个实验的学生；单个实验的通过率按该实验自己的参与学生计算。'
