/**
 * 备课与预习的纯换算（SPEC-008）。
 *
 * 条目在界面上按数组顺序编辑，提交前统一重排 sort_order（服务端要求计划内唯一、
 * 且每条恰好一个目标）。这里不碰网络，便于单测。
 */

export const TARGET_LABEL = {
  knowledge: '知识点',
  resource_version: '资源版本',
  question: '题目',
  experiment: '实验',
}

export const TARGET_TYPES = ['knowledge', 'resource_version', 'question', 'experiment']

/** 条目身份：同一份备课单里用类型 + ID 区分。 */
export function targetKey(item) {
  return `${item.target_type}:${item.target_id}`
}

/** 按当前数组顺序重排 sort_order（从 1 开始）。 */
export function renumber(items) {
  return (items ?? []).map((item, index) => ({ ...item, sort_order: index + 1 }))
}

/** 追加一个目标；已在单内的目标不再重复添加。 */
export function addItem(items, targetType, targetId) {
  if (!TARGET_TYPES.includes(targetType)) return renumber(items)
  const exists = (items ?? []).some((item) => targetKey(item) === `${targetType}:${targetId}`)
  if (exists) return renumber(items)
  return renumber([...(items ?? []), { target_type: targetType, target_id: Number(targetId) }])
}

export function removeAt(items, index) {
  const next = [...(items ?? [])]
  next.splice(index, 1)
  return renumber(next)
}

/** 上移/下移一个位置，越界时原样返回。 */
export function move(items, index, delta) {
  const next = [...(items ?? [])]
  const target = index + delta
  if (index < 0 || index >= next.length || target < 0 || target >= next.length) {
    return renumber(next)
  }
  const [entry] = next.splice(index, 1)
  next.splice(target, 0, entry)
  return renumber(next)
}

/** 条目统计，用于列表与预习卡片的摘要文案。 */
export function summarizeItems(items) {
  const counts = { knowledge: 0, resource_version: 0, question: 0, experiment: 0 }
  for (const item of items ?? []) {
    if (counts[item.target_type] !== undefined) counts[item.target_type] += 1
  }
  return TARGET_TYPES.filter((type) => counts[type] > 0).map((type) => `${TARGET_LABEL[type]} ${counts[type]}`)
}

/** 预习待办的截止状态；due_at 是带 Z 的 UTC 时间，null 表示无期限。 */
export function dueState(dueAt, now = new Date()) {
  if (!dueAt) return { tone: 'neutral', text: '无期限', overdue: false }
  const due = new Date(dueAt)
  if (Number.isNaN(due.getTime())) return { tone: 'neutral', text: '无期限', overdue: false }
  if (due.getTime() < now.getTime()) return { tone: 'danger', text: `已过期 ${dueAt}`, overdue: true }
  const sameDay =
    due.getUTCFullYear() === now.getUTCFullYear() &&
    due.getUTCMonth() === now.getUTCMonth() &&
    due.getUTCDate() === now.getUTCDate()
  if (sameDay) return { tone: 'warning', text: `今天到期 ${dueAt}`, overdue: false }
  return { tone: 'neutral', text: `截止 ${dueAt}`, overdue: false }
}

/**
 * 预习条目的一句话说明。Preview 模型不含备课单标题，待办文案由条目内容拼出，
 * 因此这里按类型取快照里冻结的内容摘要。
 */
export function previewItemLabel(item) {
  const content = item?.content ?? {}
  const label = TARGET_LABEL[item?.target_type] ?? item?.target_type ?? '条目'
  if (item?.target_type === 'knowledge') return `${label}「${content.title ?? ''}」`
  if (item?.target_type === 'resource_version') {
    return `${label}「${content.resource_title ?? ''}」v${content.version_no ?? '?'}`
  }
  if (item?.target_type === 'question') {
    const stem = content.stem_md ?? ''
    return `${label}「${stem.length > 40 ? `${stem.slice(0, 40)}…` : stem}」`
  }
  if (item?.target_type === 'experiment') return `${label}「${content.title ?? ''}」`
  return label
}

