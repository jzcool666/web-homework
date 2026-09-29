<script setup>
/**
 * 事件历史（SPEC-012 第 4 节第 5 条）。
 *
 * 每个事件都记录时钟、输入、旧 Q、新 Q 与是否有效沿；下降沿与单独改输入
 * 也入表，只是「有效沿」一列为否。历史只包含已执行事件，不含未来轨迹。
 */
import { computed } from 'vue'

import StatusBadge from '@/components/ui/StatusBadge.vue'
import { actionLabel, bitLabels, formatBits, inputLabel, rowSummary } from '@/utils/demo'

const props = defineProps({
  history: { type: Array, default: () => [] },
  simulatorType: { type: String, required: true },
  limit: { type: Number, default: 0 },
})

const labels = computed(() => bitLabels(props.simulatorType))
const rows = computed(() => {
  const all = props.history ?? []
  return props.limit > 0 ? all.slice(-props.limit) : all
})

function pinsOf(row) {
  return Object.entries(row.inputs ?? {})
}
</script>

<template>
  <div class="history-scroll">
    <table class="history">
      <caption class="sr-only">已执行事件历史，共 {{ history.length }} 行</caption>
      <thead>
        <tr>
          <th scope="col">#</th>
          <th scope="col">操作</th>
          <th scope="col">CLK</th>
          <th scope="col">输入</th>
          <th scope="col">旧 Q {{ labels.join('') }}</th>
          <th scope="col">新 Q {{ labels.join('') }}</th>
          <th scope="col">有效沿</th>
          <th scope="col">拍数</th>
        </tr>
      </thead>
      <tbody>
        <tr
          v-for="row in rows"
          :key="row.seq"
          :class="{ 'history__row--rising': row.rising }"
          :title="rowSummary(row, simulatorType)"
        >
          <td>{{ row.seq }}</td>
          <td>{{ actionLabel(row.op) }}</td>
          <td>{{ row.clock }}</td>
          <td>
            <span v-for="[name, value] in pinsOf(row)" :key="name" class="pin">
              {{ inputLabel(name) }}={{ value }}
            </span>
          </td>
          <td class="mono">{{ formatBits(row.q_before ?? 0, simulatorType) }}</td>
          <td class="mono">{{ formatBits(row.q ?? 0, simulatorType) }}</td>
          <td>
            <StatusBadge :tone="row.rising ? 'success' : 'neutral'">
              {{ row.rising ? '是' : '否' }}
            </StatusBadge>
          </td>
          <td>{{ row.step_no }}</td>
        </tr>
        <tr v-if="rows.length === 0">
          <td colspan="8" class="history__empty">还没有执行任何事件。</td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<style scoped>
.history-scroll {
  overflow-x: auto;
}

.history {
  min-width: 40rem;
}

.history__row--rising {
  background: color-mix(in srgb, var(--color-success) 7%, white);
}

.pin {
  margin-right: var(--space-2);
  font: 650 var(--font-size-xs) var(--font-mono);
}

.mono {
  font-family: var(--font-mono);
}

.history__empty {
  color: var(--color-text-secondary);
  text-align: center;
}

.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  clip: rect(0 0 0 0);
  white-space: nowrap;
}
</style>
