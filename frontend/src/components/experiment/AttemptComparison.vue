<script setup>
import { computed } from 'vue'
import { bitLabels, bitsOf, stepPath } from '@/utils/demo'
const props = defineProps({
  result: { type: Object, required: true },
  simulatorType: { type: String, required: true },
})
const labels = computed(() => bitLabels(props.simulatorType))
const width = computed(
  () => 60 + Math.max(1, props.result.expected.length) * 38,
)
const height = computed(() => 35 + labels.value.length * 65)
function path(values, bitIndex, row, offset) {
  return stepPath(
    values.map((value) => bitsOf(value, props.simulatorType)[bitIndex]),
    {
      slot: 38,
      yLow: 35 + row * 65 + offset + 18,
      yHigh: 35 + row * 65 + offset,
    },
  )
}
</script>
<template>
  <section class="comparison">
    <h3>逐拍 Q 对照</h3>
    <p class="hint">
      紫色实线为服务端标准状态，橙色虚线为提交的预测。每格对应一个有效上升沿，不是完整半周期波形。
    </p>
    <div class="table-scroll">
      <svg
        :viewBox="`0 0 ${width} ${height}`"
        :style="{ width: `${width}px`, height: `${height}px` }"
        role="img"
        aria-label="逐拍标准状态与提交预测对照，详细数值见下方结果表"
      >
        <g v-for="(label, index) in labels" :key="label">
          <text x="0" :y="50 + index * 65">{{ label }}</text>
          <g transform="translate(55 0)">
            <path
              :d="path(result.expected, index, index, 0)"
              class="standard"
            />
            <path
              :d="path(result.actual, index, index, 26)"
              class="prediction"
            />
          </g>
        </g>
        <text
          v-for="(_, index) in result.expected"
          :key="index"
          :x="57 + index * 38"
          y="16"
        >
          {{ index + 1 }}拍
        </text>
      </svg>
    </div>
  </section>
</template>
<style scoped>
.comparison {
  margin-bottom: var(--space-5);
}
svg {
  display: block;
  font: 11px var(--font-mono);
}
text {
  fill: var(--color-text-secondary);
}
path {
  fill: none;
  stroke-width: 2;
}
.standard {
  stroke: var(--color-wave-q);
}
.prediction {
  stroke: var(--color-wave-k);
  stroke-dasharray: 4 2;
}
</style>
