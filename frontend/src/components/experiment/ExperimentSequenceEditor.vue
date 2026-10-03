<script setup>
import { computed, ref } from 'vue'
import { inputLabel, inputsFor } from '@/utils/demo'
import { appendClockStep, copySequence, defaultInputs, EVENT_LABELS, MAX_EXPERIMENT_EVENTS, sequenceTimeline } from '@/utils/experimentDraft'
const props = defineProps({ modelValue: { type: Array, default: () => [] }, simulatorType: { type: String, required: true }, disabled: Boolean })
const emit = defineEmits(['update:modelValue'])
const error = ref('')
const timeline = computed(() => sequenceTimeline(props.simulatorType, props.modelValue))
const checkpointCount = computed(() => timeline.value.at(-1)?.step_no ?? 0)
const full = computed(() => props.modelValue.length >= MAX_EXPERIMENT_EVENTS)
function update(rows) { if (props.disabled) return; error.value = ''; emit('update:modelValue', rows) }
function append(op) {
  if (props.disabled || full.value) return
  const event = op === 'set' ? { op, inputs: { ...(timeline.value.at(-1)?.inputs ?? defaultInputs(props.simulatorType)) } } : { op }
  update([...copySequence(props.modelValue), event])
}
function appendStep() {
  if (props.disabled) return
  try { update(appendClockStep(props.simulatorType, props.modelValue)) } catch (err) { error.value = err.message }
}
function replace(index, event) { update(props.modelValue.map((row, position) => position === index ? event : copySequence([row])[0])) }
function changeOp(index, op) {
  const inputs = timeline.value[index - 1]?.inputs ?? defaultInputs(props.simulatorType)
  replace(index, op === 'set' ? { op, inputs: { ...inputs } } : { op })
}
function changeInput(index, pin, value) {
  const event = props.modelValue[index]
  replace(index, { op: 'set', inputs: { ...event.inputs, [pin]: Number(value) } })
}
function move(index, direction) { const rows = copySequence(props.modelValue); [rows[index], rows[index + direction]] = [rows[index + direction], rows[index]]; update(rows) }
</script>

<template>
  <section class="sequence-editor" aria-label="实验输入序列编辑器">
    <div class="sequence-heading"><div><h3>输入序列</h3><p>按操作顺序设置输入和时钟；学生需要预测每个有效上升沿后的Q。</p></div><span>{{ modelValue.length }} / 128 次操作 · {{ checkpointCount }} 个检查点</span></div>
    <div v-if="!disabled" class="sequence-tools">
      <button type="button" class="button button--secondary" :disabled="full" @click="append('set')">＋ 设置输入</button>
      <button type="button" class="button button--secondary" :disabled="full" @click="appendStep">＋ 一拍</button>
      <button type="button" class="button button--secondary" :disabled="full" @click="append('toggle_clock')">＋ 半周期</button>
      <button type="button" class="button button--secondary" :disabled="full" @click="append('reset_view')">＋ 恢复初态</button>
    </div>
    <p v-if="error" class="sequence-error" role="alert">{{ error }}</p>
    <div v-if="!modelValue.length" class="sequence-empty">还没有操作。先添加输入，再添加一拍，逐步组成实验流程。</div>
    <ol v-else class="event-list">
      <li v-for="(event,index) in modelValue" :key="index" class="event-row">
        <span class="event-index">{{ index + 1 }}</span>
        <div class="event-main">
          <select :value="event.op" :disabled="disabled" :aria-label="`第${index + 1}次操作类型`" @change="changeOp(index, $event.target.value)"><option v-for="(label,op) in EVENT_LABELS" :key="op" :value="op">{{ label }}</option></select>
          <div v-if="event.op === 'set'" class="event-inputs"><label v-for="pin in inputsFor(simulatorType)" :key="pin">{{ inputLabel(pin) }}<select :value="event.inputs[pin] ?? timeline[index].inputs[pin]" :disabled="disabled" :aria-label="`第${index + 1}次操作 ${inputLabel(pin)}`" @change="changeInput(index,pin,$event.target.value)"><option :value="0">0</option><option :value="1">1</option></select></label></div>
          <small v-if="event.op === 'reset_view'" class="reset-note">时钟和输入恢复初态，之前的检查点不计入本次预测。</small>
          <span v-else class="event-context" :class="{ 'event-context--rise': timeline[index].rising }">CLK={{ timeline[index].clock }} · {{ timeline[index].rising ? `↑ 第${timeline[index].step_no}拍` : '输出保持' }}</span>
        </div>
        <div v-if="!disabled" class="event-actions"><button type="button" :disabled="index === 0" :aria-label="`上移第${index + 1}次操作`" @click="move(index,-1)">↑</button><button type="button" :disabled="index === modelValue.length - 1" :aria-label="`下移第${index + 1}次操作`" @click="move(index,1)">↓</button><button type="button" :aria-label="`移除第${index + 1}次操作`" @click="update(copySequence(modelValue).filter((_,position)=>position !== index))">×</button></div>
      </li>
    </ol>
    <p v-if="!checkpointCount" class="sequence-warning">当前序列没有有效上升沿，学生将无法进行状态预测。发布前建议至少添加一拍。</p>
    <p class="sequence-footnote">这里只预览操作顺序与检查点数量；标准输出由服务器计算。添加“一拍”会在需要时先补一个下降沿。</p>
  </section>
</template>

<style scoped>
.sequence-editor { border: 1px solid var(--color-border); border-radius: 14px; background: #fbfcff; padding: 18px; }.sequence-heading { display: flex; justify-content: space-between; gap: 14px; flex-wrap: wrap; margin-bottom: 14px; }.sequence-heading h3 { font-size: .92rem; color: #3f5b84; margin: 0 0 6px; }.sequence-heading p { font-size: .73rem; color: #8495ad; margin: 0; line-height: 1.8; }.sequence-heading>span { font-size: .7rem; color: #7b93b7; white-space: nowrap; }.sequence-tools { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 16px; }.sequence-tools .button { font-size: .72rem; padding: 7px 10px; }.sequence-empty { padding: 26px 14px; border: 1px dashed #d7e2f2; border-radius: 10px; text-align: center; color: #8c9cb4; font-size: .78rem; }.event-list { list-style: none; padding: 0; margin: 0; display: grid; gap: 9px; max-height: 460px; overflow-y: auto; }.event-row { display: flex; align-items: center; gap: 12px; padding: 12px; background: white; border: 1px solid #e4ebf6; border-radius: 10px; }.event-index { font: 700 .72rem var(--font-mono); color: #a0afc4; width: 18px; flex-shrink: 0; }.event-main { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; flex: 1; min-width: 0; }.event-main>select { padding: 7px; border: 1px solid #dce5f3; border-radius: 7px; color: #587299; font-size: .73rem; background: #f8faff; }.event-inputs { display: flex; gap: 10px; flex-wrap: wrap; }.event-inputs label { display: flex; gap: 5px; align-items: center; font: 600 .7rem var(--font-mono); color: #6d83a4; }.event-inputs select { width: 43px; padding: 4px; border: 1px solid #dce5f3; background: white; border-radius: 6px; font-size: .74rem; }.event-context { font-size: .65rem; color: #9aa9bf; }.event-context--rise { color: #349f88; }.reset-note { font-size: .66rem; color: #b18851; }.event-actions { display: flex; gap: 3px; }.event-actions button { border: 0; border-radius: 5px; color: #8c9fb9; background: #f1f5fc; width: 25px; height: 26px; padding: 0; }.event-actions button:disabled { opacity: .3; cursor: default; }.sequence-warning { font-size: .72rem; padding: 10px; color: #a47835; background: #fff8eb; border-radius: 8px; margin: 14px 0 0; }.sequence-footnote { font-size: .67rem; line-height: 1.8; color: #9eabc0; margin: 12px 0 0; }.sequence-error { color: var(--color-danger); font-size: .75rem; }
@media(max-width:600px) { .sequence-editor { padding: 13px; }.event-row { padding: 10px; gap: 8px; align-items: flex-start; }.event-main { flex-direction: column; align-items: flex-start; gap: 9px; }.event-actions { flex-direction: column; }.sequence-tools .button { font-size: .65rem; }.sequence-heading>span { white-space: normal; } }
</style>
