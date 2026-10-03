<script setup>
import { computed, ref, watch } from 'vue'
import CircuitPreview from '@/components/home/CircuitPreview.vue'
import { inputLabel, formatBits } from '@/utils/demo'
const props = defineProps({ experiment: { type: Object, required: true }, answers: { type: Array, required: true }, locked: Boolean })
const emit = defineEmits(['answer'])
const cursor = ref(0)
const checkpoints = computed(() => props.experiment.checkpoints ?? [])
const current = computed(() => checkpoints.value[cursor.value])
const range = computed(() => ['d', 'jk'].includes(props.experiment.simulator_type) ? 2 : 16)
watch(() => `${props.experiment.id}:${props.experiment.version}`, () => { cursor.value = 0 })
function select(value) { emit('answer', current.value.index, value) }
</script>
<template>
  <div class="prediction-console">
    <CircuitPreview :kind="experiment.simulator_type" />
    <div class="prediction-console__controls" v-if="current">
      <h3>逐拍工作台 <small>第 {{ cursor + 1 }} / {{ checkpoints.length }} 拍</small></h3>
      <div class="signal-readouts" aria-label="本拍固定输入">
        <div v-for="(value, name) in current.inputs" :key="name"><span>{{ inputLabel(name) }}</span><strong :class="{ 'signal-high': value === 1 }">{{ value }}</strong></div>
        <div><span>CLK</span><strong class="signal-high">↑</strong></div>
      </div>
      <label class="prediction-choice">预测 Q
        <select aria-label="当前拍预测 Q" :value="answers[current.index]" :disabled="locked" @change="select($event.target.value)">
          <option value="">待预测</option><option v-for="n in range" :key="n" :value="String(n - 1)">{{ formatBits(n - 1, experiment.simulator_type) }}（{{ n - 1 }}）</option>
        </select>
      </label>
      <div class="console-stepping"><button class="button button--secondary" type="button" :disabled="cursor === 0" @click="cursor--">上一拍</button><button class="button button--primary" type="button" :disabled="cursor >= checkpoints.length - 1" @click="cursor++">查看下一拍 →</button></div>
      <p class="hint">按固定输入序列查看每个上升沿，Q 由你预测。</p>
    </div>
  </div>
</template>
<style scoped>
.prediction-console { display: grid; grid-template-columns: minmax(170px, 1.1fr) minmax(230px, 1fr); gap: 24px; align-items: center; }
.prediction-console :deep(.circuit-preview) { width: 100%; max-width: 250px; margin-inline: auto; padding: 8px; border: 0; background: transparent; }
h3 { display: flex; justify-content: space-between; gap: 8px; font-size: 13px; margin-bottom: 12px; } h3 small { font-size: 10px; color: var(--color-text-secondary); font-weight: 400; white-space: nowrap; }
.signal-readouts { display: flex; flex-wrap: wrap; gap: 9px; margin-bottom: 12px; } .signal-readouts > div { display: flex; align-items: center; gap: 6px; font: 12px var(--font-mono); }
.signal-readouts strong { display: grid; place-items: center; min-width: 26px; height: 25px; border: 1px solid #dbe6fa; border-radius: 5px; color: #7283a5; background: #f5f8fc; }
.signal-readouts .signal-high { color: var(--color-primary); background: #eaf1ff; border-color: #adc5ff; }
.prediction-choice { display: flex; align-items: center; gap: 12px; font-size: 12px; font-weight: 650; }
select { padding: 5px 10px; color: var(--color-primary); border: 1px solid #cad9f6; border-radius: 5px; background: #f8fbff; min-width: 110px; }
.console-stepping { display: flex; gap: 8px; margin-top: 12px; } .console-stepping button { min-height: 31px; font-size: 11px; padding: 6px 9px; }
.hint { margin: 10px 0 0; font-size: 10px; }
@media (max-width: 620px) { .prediction-console { grid-template-columns: 1fr; gap: 14px; } .prediction-console :deep(.circuit-preview) { max-width: 230px; margin-inline: auto; } }
</style>
