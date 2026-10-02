/**
 * SPEC-007 检索问答的显示工具。
 *
 * 相似度只表示文本相近程度：这里把它转成百分比**并且**由页面同时标注
 * 「不是正确率」，避免读者把它当成答对的概率（SPEC-007 第 4 节第 2 条）。
 */

/** 0—1 的比例转百分比；null/undefined 返回「—」，与真实的 0 区分开。 */
export function formatSimilarity(ratio) {
  if (ratio === null || ratio === undefined || Number.isNaN(Number(ratio))) return '—'
  return `${Math.round(Number(ratio) * 100)}%`
}

/** 来源只显示主机名，避免长链接撑破布局；解析失败时回退为原文。 */
export function sourceLabel(url) {
  if (!url) return ''
  try {
    const host = new URL(url).hostname
    return host || url
  } catch {
    return url
  }
}

/** 匹配条数说明：0 条时要明确说「没有可靠匹配」，而不是留空。 */
export function matchSummary(matched, count) {
  if (!matched || count === 0) return '没有可靠匹配'
  return `找到 ${count} 个可能相关的知识点`
}
