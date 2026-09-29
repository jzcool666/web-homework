<script setup>
/**
 * 时序波形（SPEC-012 第 4 节第 5 条）。
 *
 * 数据只来自服务器的 history：每行事件占半个时钟周期，CLK 取事件后的电平，
 * Q 只在有效上升沿变化。有效沿用虚线加「第 N 拍」文字标注，
 * 不把颜色当作唯一编码。
 */
import { computed } from 'vue'

import { bitLabels, formatBits, stepPath, waveSignals, waveWidth } from '@/utils/demo'

const props = defineProps({
  history: { type: Array, default: () => [] },
  simulatorType: { type: String, required: true },
})

const SLOT = 26
const LABEL_W = 54
const ROW_H = 30
const TOP = 14
const PAD = 10

const signals = computed(() => waveSignals(props.history, props.simulatorType))
const labels = computed(() => bitLabels(props.simulatorType))
const rows = computed(() => ['CLK', ...labels.value])
const width = computed(() => LABEL_W + waveWidth(props.history, SLOT) + PAD)
const height = computed(() => TOP + rows.value.length * ROW_H + PAD)
const risings = computed(() => signals.value.filter((signal) => signal.rising))

function band(index) {
  const top = TOP + index * ROW_H
  return { high: top + 8, low: top + ROW_H - 8 }
}

function levelsFor(rowIndex) {
  if (rowIndex === 0) return signals.value.map((signal) => signal.clock)
  return signals.value.map((signal) => signal.bits[rowIndex - 1])
}

function pathFor(rowIndex) {
  const { high, low } = band(rowIndex)
  return stepPath(levelsFor(rowIndex), { slot: SLOT, yLow: low, yHigh: high })
}

const ariaLabel = computed(() => {
  if (!signals.value.length) return '暂无波形：还没有执行任何事件'
  const last = props.history[props.history.length - 1]
  return `时序波形，共 ${signals.value.length} 次事件；当前 CLK=${last.clock ? 1 : 0}，Q=${formatBits(last.q ?? 0, props.simulatorType)}`
})
</script>

<template>
  <div class="wave-scroll">
    <svg
      class="wave"
      :viewBox="`0 0 ${width} ${height}`"
      :style="{ width: `${width}px`, height: `${height}px` }"
      role="img"
      :aria-label="ariaLabel"
    >
      <g v-for="(row, index) in rows" :key="row">
        <text class="wave__label" :x="0" :y="band(index).low + 4">{{ row }}</text>
        <line
          class="wave__baseline"
          :x1="LABEL_W"
          :x2="width - PAD"
          :y1="band(index).low"
          :y2="band(index).low"
        />
      </g>

      <g :transform="`translate(${LABEL_W} 0)`">
        <path
          v-for="(row, index) in rows"
          :key="`path-${row}`"
          class="wave__signal"
          :class="{ 'wave__signal--state': index > 0 }"
          :d="pathFor(index)"
        />
      </g>

      <g v-for="signal in risings" :key="`rise-${signal.seq}`">
        <line
          class="wave__edge"
          :x1="LABEL_W + signal.index * SLOT"
          :x2="LABEL_W + signal.index * SLOT"
          :y1="TOP - 6"
          :y2="height - PAD"
        />
        <text
          class="wave__edge-label"
          :x="LABEL_W + signal.index * SLOT + 3"
          :y="TOP - 8"
        >
          第 {{ signal.stepNo }} 拍
        </text>
      </g>
    </svg>
  </div>
</template>

<style scoped>
.wave-scroll {
  overflow-x: auto;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: var(--color-grid-surface);
}

.wave {
  display: block;
}

.wave__label {
  font: 650 var(--font-size-xs) var(--font-mono);
  fill: var(--color-text-secondary);
}

.wave__baseline {
  stroke: var(--color-grid-line);
  stroke-width: 1;
}

.wave__signal {
  fill: none;
  stroke: var(--color-primary);
  stroke-width: 2;
}

.wave__signal--state {
  stroke: var(--color-text-primary);
}

.wave__edge {
  stroke: var(--color-success);
  stroke-width: 1;
  stroke-dasharray: 3 3;
}

.wave__edge-label {
  font: 650 10px var(--font-mono);
  fill: var(--color-success);
}
</style>
