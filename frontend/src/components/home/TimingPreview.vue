<script setup>
import { computed } from 'vue'
import { inputsFor, inputLabel, stepPath } from '@/utils/demo'
const props = defineProps({
  checkpoints: { type: Array, default: null },
  kind: { type: String, default: 'jk' },
})
// 缺省是明确标注的 JK 教学样例；真实检查点只绘制已下发输入，不产生标准 Q。
const sample = computed(() => props.checkpoints === null)
const rows = computed(() =>
  sample.value
    ? [
        { label: 'CLK', levels: [0, 1, 0, 1, 0, 1, 0, 1] },
        { label: 'J', levels: [0, 0, 1, 1, 0, 0, 1, 1] },
        { label: 'K', levels: [0, 0, 0, 0, 1, 1, 1, 1] },
        { label: 'Q', levels: [0, 0, 0, 1, 1, 0, 0, 1] },
      ]
    : inputsFor(props.kind).map((name) => ({
        label: inputLabel(name),
        levels: props.checkpoints.map((row) => row.inputs?.[name] ?? 0),
      })),
)
const count = computed(() => rows.value[0]?.levels.length ?? 0)
const width = computed(() => 55 + Math.max(count.value, 1) * 26)
const colors = ['#3564ff', '#35b57b', '#efa546', '#9374e8']
</script>
<template>
  <figure class="timing-preview">
    <div v-if="!count" class="chart-empty">暂无输入采样</div>
    <div v-else class="timing-preview__scroll">
      <svg
        :viewBox="`0 0 ${width} ${rows.length * 32 + 24}`"
        :style="{ minWidth: `${Math.min(width, 600)}px` }"
        role="img"
        :aria-label="
          sample
            ? 'JK 触发器教学时序示例'
            : '实验检查点的输入采样，不包含标准状态'
        "
      >
        <path
          v-for="i in count"
          :key="i"
          :d="`M${45 + (i - 1) * 26} 0V${rows.length * 32}`"
          stroke="#e8eef9"
          stroke-dasharray="3 3"
        />
        <g
          v-for="(row, index) in rows"
          :key="row.label"
          :transform="`translate(0 ${index * 32})`"
        >
          <text x="0" y="20" font-size="11" fill="#51688e">
            {{ row.label }}
          </text>
          <path
            :d="stepPath(row.levels, { yHigh: 5, yLow: 26 })"
            transform="translate(45 0)"
            :stroke="colors[index % colors.length]"
            stroke-width="1.6"
            fill="none"
          />
        </g>
        <g v-if="!sample">
          <text
            v-for="i in count"
            :key="i"
            :x="48 + (i - 1) * 26"
            :y="rows.length * 32 + 16"
            font-size="9"
            fill="#687c9e"
          >
            {{ i }}
          </text>
        </g>
      </svg>
    </div>
    <figcaption>
      {{
        sample
          ? '教学示例 · 初态 Q=0，非当前实验答案'
          : '有效上升沿的输入采样 · 输出由你预测'
      }}
    </figcaption>
  </figure>
</template>
<style scoped>
.timing-preview {
  margin: 0;
  min-width: 0;
}
.timing-preview__scroll {
  overflow-x: auto;
  padding: 8px 0;
}
svg {
  display: block;
  width: 100%;
  max-height: 175px;
  font-family: var(--font-mono);
}
figcaption {
  font-size: 10px;
  color: var(--color-text-secondary);
  margin-top: 5px;
}
</style>
