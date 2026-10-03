<script setup>
import { computed, ref } from 'vue'
const props = defineProps({ rows: { type: Array, default: () => [] } })
const maximum = computed(() =>
  Math.max(2, ...props.rows.map((row) => row.submitted)),
)
const selected = ref(null)
function path(key) {
  return props.rows
    .map(
      (row, i) =>
        `${i ? 'L' : 'M'}${40 + i * 48} ${135 - (row[key] / maximum.value) * 100}`,
    )
    .join(' ')
}
</script>
<template>
  <figure class="activity-chart">
    <div class="activity-chart__legend">
      <span>● 提交次数</span><span>● 通过次数</span>
    </div>
    <svg
      viewBox="0 0 370 167"
      role="img"
      aria-label="最近七个 UTC 自然日的实验提交与通过次数"
    >
      <g v-for="i in 3" :key="i">
        <path
          :d="`M40 ${35 + (i - 1) * 50}H345`"
          stroke="#e9eff9"
          stroke-dasharray="3 3"
        />
        <text x="4" :y="39 + (i - 1) * 50" font-size="10" fill="#687c9e">
          {{ Math.round((maximum * (3 - i)) / 2) }}
        </text>
      </g>
      <path
        :d="path('submitted')"
        fill="none"
        stroke="#4578ff"
        stroke-width="2"
      />
      <path :d="path('passed')" fill="none" stroke="#35b57b" stroke-width="2" />
      <g v-for="(row, index) in rows" :key="row.day" tabindex="0" :aria-label="`${row.day} 提交 ${row.submitted} 次，通过 ${row.passed} 次`" @focus="selected = row" @mouseenter="selected = row" @mouseleave="selected = null" @blur="selected = null">
        <circle
          :cx="40 + index * 48"
          :cy="135 - (row.submitted / maximum) * 100"
          r="3"
          fill="#4578ff"
        >
          <title>
            {{ row.day }}：提交 {{ row.submitted }} 次，通过 {{ row.passed }} 次
          </title>
        </circle>
        <circle :cx="40 + index * 48" :cy="135 - (row.passed / maximum) * 100" r="2.5" fill="#35b57b" />
        <text
          :x="40 + index * 48"
          y="159"
          text-anchor="middle"
          font-size="9"
          fill="#687c9e"
        >
          {{ row.day.slice(5) }}
        </text>
      </g>
    </svg>
    <figcaption>{{ selected ? `${selected.day}：提交 ${selected.submitted} 次，通过 ${selected.passed} 次` : '按记录创建时间统计（UTC），重复尝试各计一次。' }}</figcaption>
  </figure>
</template>
<style scoped>
.activity-chart {
  margin: 0;
}
.activity-chart__legend {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  font-size: 10px;
  color: #4578ff;
}
.activity-chart__legend span + span {
  color: #258756;
}
svg {
  width: 100%;
  display: block;
  max-height: 190px;
}
figcaption {
  color: var(--color-text-secondary);
  font-size: 10px;
}
</style>
