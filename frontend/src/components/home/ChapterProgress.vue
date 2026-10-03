<script setup>
import { percent } from '@/utils/overview'
defineProps({ rows: { type: Array, default: () => [] } })
const colors = ['#4578ff', '#54b6c5', '#72a4f7', '#f0c565']
</script>
<template>
  <div v-if="!rows.length" class="chart-empty">暂无章节完成记录</div>
  <div v-else class="chapter-progress">
    <div
      v-for="(row, index) in rows"
      :key="row.id"
      class="chapter-progress__row"
    >
      <span :title="row.title">{{ row.title }}</span>
      <div
        class="chapter-progress__track"
        role="progressbar"
        :aria-label="`${row.title}自报完成`"
        :aria-valuenow="row.completed"
        :aria-valuemax="row.total"
        aria-valuemin="0"
      >
        <i
          :style="{
            width: `${row.ratio * 100}%`,
            background: colors[index % colors.length],
          }"
        ></i>
      </div>
      <small
        >{{ row.completed }}/{{ row.total }} · {{ percent(row.ratio) }}</small
      >
    </div>
  </div>
</template>
<style scoped>
.chapter-progress {
  display: grid;
  gap: 15px;
  padding-block: 5px;
}
.chapter-progress__row {
  display: grid;
  grid-template-columns: minmax(60px, 1fr) minmax(40px, 1.3fr) auto;
  gap: 10px;
  align-items: center;
}
.chapter-progress__row > span {
  font-size: 12px;
  white-space: nowrap;
  text-overflow: ellipsis;
  overflow: hidden;
}
.chapter-progress__track {
  height: 7px;
  border-radius: 4px;
  background: #edf2ff;
  overflow: hidden;
}
.chapter-progress__track i {
  height: 100%;
  display: block;
  border-radius: inherit;
}
small {
  color: var(--color-text-secondary);
  font-size: 10px;
}
</style>
