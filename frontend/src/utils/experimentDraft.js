import { inputsFor } from '@/utils/demo'

export const MAX_EXPERIMENT_EVENTS = 128
export const EVENT_LABELS = { set: '设置输入', toggle_clock: '切换时钟半周期', reset_view: '恢复初态' }
export const defaultInputs = type => Object.fromEntries(inputsFor(type).map(pin => [pin, pin === 'enable' ? 1 : 0]))
export const copySequence = sequence => sequence.map(event => event.op === 'set' ? { op: 'set', inputs: { ...event.inputs } } : { op: event.op })

export function newExperimentDraft(knowledgeId = '') {
  return { title: '', knowledge_id: knowledgeId, simulator_type: 'd', initial_q: 0, modulus: 6, steps_md: '', input_sequence: [] }
}

export function experimentDraft(row) {
  return { title: row.title, knowledge_id: row.knowledge_id, simulator_type: row.simulator_type,
    initial_q: row.config.initial_q, modulus: row.config.modulus ?? 6, steps_md: row.steps_md,
    input_sequence: copySequence(row.input_sequence) }
}

// Only clock and input context are projected here. Q and expected answers stay on the server.
export function sequenceTimeline(type, sequence) {
  let clock = 0, step = 0, inputs = defaultInputs(type)
  return sequence.map((event, index) => {
    let rising = false
    if (event.op === 'set') inputs = { ...inputs, ...event.inputs }
    else if (event.op === 'reset_view') { clock = 0; step = 0; inputs = defaultInputs(type) }
    else if (event.op === 'toggle_clock') { clock = 1 - clock; rising = clock === 1; if (rising) step += 1 }
    return { index, op: event.op, clock, step_no: step, rising, inputs: { ...inputs } }
  })
}

export class ExperimentDraftError extends Error {
  constructor(field, message) { super(message); this.fields = { [field]: message } }
}
const invalid = (field, message) => { throw new ExperimentDraftError(field, message) }

export function experimentPayload(form, published) {
  const type = form.simulator_type
  if (!['d', 'jk', 'counter', 'shift'].includes(type)) invalid('simulator_type', '请选择支持的实验模型')
  const title = form.title.trim()
  if (title.length < 1 || title.length > 100) invalid('title', '实验标题需为1—100个字符')
  const knowledgeId = Number(form.knowledge_id)
  if (!Number.isInteger(knowledgeId) || knowledgeId < 1) invalid('knowledge_id', '请选择关联知识点')
  const initialQ = Number(form.initial_q), max = ['d', 'jk'].includes(type) ? 1 : 15
  if (form.initial_q === '' || !Number.isInteger(initialQ) || initialQ < 0 || initialQ > max) invalid('config.initial_q', `初态Q需为0—${max}的整数`)
  const config = { initial_q: initialQ }
  if (type === 'counter') {
    const modulus = Number(form.modulus)
    if (form.modulus === '' || !Number.isInteger(modulus) || modulus < 2 || modulus > 16) invalid('config.modulus', '模数M需为2—16的整数')
    config.modulus = modulus
  }
  if (typeof form.steps_md !== 'string' || form.steps_md.length < 1 || form.steps_md.length > 10000) invalid('steps_md', '实验说明需为1—10000个字符')
  const sequence = form.input_sequence
  if (!Array.isArray(sequence) || sequence.length > MAX_EXPERIMENT_EVENTS) invalid('input_sequence', '输入序列最多128个事件')
  sequence.forEach((event, index) => {
    const field = `input_sequence[${index}]`
    if (!event || !Object.hasOwn(EVENT_LABELS, event.op)) invalid(field, `第${index + 1}次操作不受支持`)
    const allowed = event.op === 'set' ? ['op', 'inputs'] : ['op']
    if (Object.keys(event).some(key => !allowed.includes(key))) invalid(field, `第${index + 1}次操作含不支持的字段`)
    if (event.op === 'set') {
      if (!event.inputs || !Object.keys(event.inputs).length) invalid(field, `第${index + 1}次操作必须指定输入`)
      for (const [pin, value] of Object.entries(event.inputs)) {
        if (!inputsFor(type).includes(pin) || ![0, 1].includes(value)) invalid(`${field}.inputs`, `第${index + 1}次操作的输入不符合所选模型`)
      }
    }
  })
  return { title, knowledge_id: knowledgeId, simulator_type: type, config, steps_md: form.steps_md,
    input_sequence: copySequence(sequence), published: Boolean(published) }
}

export function appendClockStep(type, sequence) {
  const timeline = sequenceTimeline(type, sequence)
  const count = timeline.at(-1)?.clock ? 2 : 1
  if (sequence.length + count > MAX_EXPERIMENT_EVENTS) invalid('input_sequence', '添加这一拍会超过128个事件，请先删减序列')
  return [...copySequence(sequence), ...Array.from({ length: count }, () => ({ op: 'toggle_clock' }))]
}
