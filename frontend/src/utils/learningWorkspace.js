import { inputsFor, inputLabel } from './demo'

/** Display only: map public input events to clock/input levels; never compute Q. */
export function inputTimeline(events, kind) {
  const names = inputsFor(kind)
  const defaults = Object.fromEntries(names.map(name => [name, name === 'enable' ? 1 : 0]))
  let clock = 0, inputs = { ...defaults }
  const rows = [{ label: 'CLK', levels: [] }, ...names.map(name => ({ label: inputLabel(name), name, levels: [] }))]
  for (const event of events ?? []) {
    if (event.op === 'reset_view') { clock = 0; inputs = { ...defaults } }
    else if (event.op === 'toggle_clock') clock = clock ? 0 : 1
    else if (event.op === 'set') inputs = { ...inputs, ...event.inputs }
    rows[0].levels.push(clock)
    for (const row of rows.slice(1)) row.levels.push(inputs[row.name] ?? 0)
  }
  return rows
}

/** Prefer visible points attached to the four published teaching models. */
export function featuredKnowledge(points, experiments) {
  const visible = new Map(points.map(point => [point.id, point]))
  const result = [], seen = new Set()
  for (const kind of ['d', 'jk', 'counter', 'shift']) {
    const experiment = experiments.find(row => row.simulator_type === kind && visible.has(row.knowledge_id))
    if (!experiment || seen.has(experiment.knowledge_id)) continue
    result.push({ ...visible.get(experiment.knowledge_id), kind }); seen.add(experiment.knowledge_id)
  }
  for (const point of points) {
    if (result.length >= 4) break
    if (!seen.has(point.id)) { result.push({ ...point, kind: null }); seen.add(point.id) }
  }
  return result
}
