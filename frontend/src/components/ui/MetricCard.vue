<script setup>
import AppIcon from './AppIcon.vue'
defineProps({
  label: { type: String, required: true },
  value: { type: [String, Number], default: null },
  note: { type: String, default: '' },
  icon: { type: String, default: 'chart' },
})
</script>
<template>
  <article class="metric-card">
    <span class="metric-card__icon"><AppIcon :name="icon" /></span>
    <div>
      <p class="metric-card__label">{{ label }}</p>
      <strong :class="{ 'metric-card__empty': value === null }">{{
        value === null ? '暂无足够数据' : value
      }}</strong
      ><small v-if="note">{{ note }}</small>
    </div>
  </article>
</template>
