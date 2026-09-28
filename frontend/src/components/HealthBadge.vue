<script setup>
import { computed } from 'vue'

import { useHealthStore } from '@/stores/health'

const health = useHealthStore()

const label = computed(() => {
  if (health.loading) return '检查中…'
  if (health.status === 'ok') return `服务正常（版本 ${health.version}）`
  if (health.status === 'unavailable') return '服务不可用'
  return '尚未检查'
})

const detail = computed(() => (health.status === 'unavailable' ? health.reason : null))
</script>

<template>
  <p class="health" :data-status="health.status">
    <span>{{ label }}</span>
    <span v-if="detail" class="health-detail">{{ detail }}</span>
  </p>
</template>

<style scoped>
.health {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  font-size: 0.95rem;
}

.health[data-status='ok'] span:first-child {
  color: #1b5e20;
}

.health[data-status='unavailable'] span:first-child {
  color: #b3261e;
}

.health-detail {
  color: #5f6368;
  font-size: 0.85rem;
}
</style>
