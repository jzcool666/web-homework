/**
 * 复习推荐的展示换算（SPEC-015 E065）。
 *
 * 服务器已经把排序、分值与理由算好；这里只做展示：条目分类、分值口径文案、
 * 以及在哪一页继续（知识点页或自练页）。`score` 为 null 表示这条是基础路径、
 * 没有个性化信号——不能显示成 0 分，那会被读成「已经掌握」。
 */

export const KIND_LABEL = {
  knowledge: '知识点',
  question: '练习',
}

export const KIND_TONE = {
  knowledge: 'neutral',
  question: 'warning',
}

export const BASE_PATH_REASON = '按章节顺序的基础路径'

export const MIN_LIMIT = 1
export const MAX_LIMIT = 10
export const DEFAULT_LIMIT = 5

export function kindLabel(kind) {
  return KIND_LABEL[kind] ?? kind
}

/** 分值口径必须写清楚：null 不是 0 分。 */
export function scoreLabel(score) {
  if (score === null || score === undefined) return '基础路径（无个性化信号）'
  return `个性化优先度 ${score}`
}

export function scoreTone(score) {
  if (score === null || score === undefined) return 'neutral'
  return score >= 50 ? 'warning' : 'neutral'
}

/** null 分值不能被当成 0 参与排序展示。 */
export function hasPersonalScore(item) {
  return item?.score !== null && item?.score !== undefined
}

export function isBasePath(item) {
  return !hasPersonalScore(item)
}

/**
 * 条目落到哪一页继续：
 * - 知识点 → 知识点详情页（该页有正文与收藏/完成标记）
 * - 练习 → 自练页。自练页目前不读 URL 参数，所以这里不伪造「已按知识点筛选」的
 *   深链接，只把人送到自练页；知识点由条目自身标出。
 */
export function itemLink(item) {
  if (item.kind === 'question') {
    return { name: 'student-practice' }
  }
  return { name: 'student-knowledge', params: { id: item.knowledge_id } }
}

export function linkLabel(item) {
  return item.kind === 'question' ? '去练这个知识点' : '去看知识点'
}

export function summarize(items = []) {
  const personalized = items.filter(hasPersonalScore)
  return {
    total: items.length,
    personalized: personalized.length,
    basePath: items.length - personalized.length,
    kinds: items.reduce((acc, item) => {
      acc[item.kind] = (acc[item.kind] ?? 0) + 1
      return acc
    }, {}),
  }
}

/** limit 只接受 1—10 的整数，越界的输入不提交给服务器。 */
export function normalizeLimit(value) {
  const numeric = Number(value)
  if (!Number.isInteger(numeric) || numeric < MIN_LIMIT || numeric > MAX_LIMIT) return null
  return numeric
}

export function reasonsOf(item) {
  return (item?.reasons ?? []).filter((reason) => typeof reason === 'string' && reason.length > 0)
}
