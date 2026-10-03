export function chapterCompletion(points, progress, chapters) {
  const done = new Set(
    progress.filter((row) => row.completed).map((row) => row.knowledge_id),
  )
  const groups = new Map(
    chapters.map((row) => [
      row.id,
      {
        id: row.id,
        title: row.title,
        order: row.sort_order ?? 0,
        total: 0,
        completed: 0,
      },
    ]),
  )
  for (const point of new Map(points.map((row) => [row.id, row])).values()) {
    if (!groups.has(point.chapter_id))
      groups.set(point.chapter_id, {
        id: point.chapter_id,
        title: '其他知识点',
        order: 999,
        total: 0,
        completed: 0,
      })
    const group = groups.get(point.chapter_id)
    group.total += 1
    if (done.has(point.id)) group.completed += 1
  }
  return [...groups.values()]
    .filter((row) => row.total)
    .sort((a, b) => a.order - b.order || a.id - b.id)
    .map((row) => ({ ...row, ratio: row.completed / row.total }))
}

/** 只按服务端创建时间统计最近 7 个 UTC 自然日的实验记录，不外推掌握度。 */
export function attemptActivity(attempts, now = new Date()) {
  const end = Date.UTC(
    now.getUTCFullYear(),
    now.getUTCMonth(),
    now.getUTCDate(),
  )
  const rows = Array.from({ length: 7 }, (_, index) => {
    const day = new Date(end - (6 - index) * 86400000)
      .toISOString()
      .slice(0, 10)
    return { day, submitted: 0, passed: 0 }
  })
  const days = new Map(rows.map((row) => [row.day, row])),
    seen = new Set()
  for (const attempt of attempts) {
    if (seen.has(attempt.id)) continue
    seen.add(attempt.id)
    const date = new Date(attempt.created_at)
    if (!attempt.created_at || Number.isNaN(date.valueOf()) || date > now)
      continue
    const row = days.get(date.toISOString().slice(0, 10))
    if (!row) continue
    row.submitted += 1
    if (attempt.passed) row.passed += 1
  }
  return rows
}
