export function completion(points, progress, experiments, attempts) {
  const pointIds = new Set(points.map((row) => row.id))
  const experimentIds = new Set(experiments.map((row) => row.id))
  const done = new Set(
    progress
      .filter((row) => row.completed && pointIds.has(row.knowledge_id))
      .map((row) => row.knowledge_id),
  )
  const passed = new Set(
    attempts
      .filter((row) => row.passed && experimentIds.has(row.experiment_id))
      .map((row) => row.experiment_id),
  )
  return {
    learned: done.size,
    knowledgeTotal: pointIds.size,
    passed: passed.size,
    experimentTotal: experimentIds.size,
    learningRatio: pointIds.size ? done.size / pointIds.size : null,
    experimentRatio: experimentIds.size
      ? passed.size / experimentIds.size
      : null,
  }
}

export function recommendedPoints(items) {
  return [
    ...new Map(
      items
        .filter((row) => row.kind === 'knowledge')
        .map((row) => [row.knowledge_id, row]),
    ).values(),
  ]
}

export function continuePoint(
  points,
  progress,
  recommendations,
  chapters = [],
) {
  const known = new Map(points.map((row) => [row.id, row]))
  const target = recommendations.find(
    (row) => row.kind === 'knowledge' && known.has(row.knowledge_id),
  )
  if (target) return known.get(target.knowledge_id)
  const completed = new Set(
    progress.filter((row) => row.completed).map((row) => row.knowledge_id),
  )
  const order = new Map(chapters.map((row) => [row.id, row.sort_order]))
  return (
    [...points]
      .sort(
        (a, b) =>
          (order.get(a.chapter_id) ?? 0) - (order.get(b.chapter_id) ?? 0) ||
          a.sort_order - b.sort_order ||
          a.id - b.id,
      )
      .find((row) => !completed.has(row.id)) ?? null
  )
}

export function recentAssessment(rows) {
  return (
    [...rows]
      .filter((row) => row.kind !== 'practice' && row.state !== 'draft')
      .sort(
        (a, b) =>
          String(b.starts_at ?? '').localeCompare(String(a.starts_at ?? '')) ||
          b.id - a.id,
      )[0] ?? null
  )
}

export function percent(value) {
  return value === null || value === undefined
    ? '暂无足够数据'
    : `${Math.round(value * 100)}%`
}

export function initialClassId(
  classes,
  search = typeof window === 'undefined' ? '' : window.location.search,
) {
  const requested = Number(new URLSearchParams(search).get('class_id'))
  return (
    classes.find((row) => row.id === requested && row.active !== false)?.id ??
    classes.find((row) => row.active !== false)?.id ??
    ''
  )
}
