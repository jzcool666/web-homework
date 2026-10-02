/**
 * 学习预警页面的展示换算与口径文案（SPEC-004）。
 *
 * 措辞是口径的一部分：等级是项目规则算出的分数档，不是校准过的学业风险概率，
 * 也不能读成挂科预测；样本不足时显示「样本不足」而不是低风险。这些说明由单测守住。
 */

export const LEVEL_LABELS = {
  insufficient: '样本不足',
  low: '低',
  medium: '中',
  high: '高',
}

export const FACTOR_LABELS = {
  attendance: '出勤',
  progress: '学习进度',
  accuracy: '知识点首答',
}

export const LEVEL_TONES = {
  insufficient: 'neutral',
  low: 'success',
  medium: 'warning',
  high: 'danger',
}

export const WARNING_NOTE =
  '等级由项目规则按可用因素加权算出（出勤风险 0.3、进度风险 0.2、答题风险 0.5），' +
  '不是经训练校准的学业风险概率，也不能读成挂科预测。样本不足时不给分。'

export const CLUSTER_NOTE =
  '分组是三因素齐全的学生在三因素向量上的 KMeans 描述，按各簇中心平均风险升序编号 0/1/2；' +
  '它只描述班级内的相似性，不覆盖规则等级。'

/** 分数：样本不足时为 null，显示「—」而不是 0。 */
export function scoreText(score) {
  if (score === null || score === undefined) return '—'
  return Number(score).toFixed(1)
}

export function levelText(level) {
  return LEVEL_LABELS[level] ?? level ?? '—'
}

export function levelTone(level) {
  return LEVEL_TONES[level] ?? 'neutral'
}

/** 风险因素值：不可用显示「未计入」，可用显示两位小数。 */
export function factorText(value) {
  if (value === null || value === undefined) return '未计入'
  return Number(value).toFixed(2)
}

export function clusterText(label) {
  if (label === null || label === undefined) return '—'
  return `组 ${label}`
}

/** 已实现的因素列表转成中文标签串，用于「可用因素」列。 */
export function availableFactorsText(factors) {
  if (!factors || factors.length === 0) return '无'
  return factors.map((name) => FACTOR_LABELS[name] ?? name).join('、')
}
