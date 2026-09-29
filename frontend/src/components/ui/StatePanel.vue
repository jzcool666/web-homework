<script setup>
import AppIcon from './AppIcon.vue'

defineProps({
  kind: { type: String, default: 'empty', validator: (value) => ['empty', 'loading', 'error', 'forbidden'].includes(value) },
  title: { type: String, required: true },
  description: { type: String, default: '' },
})
</script>

<template>
  <div class="state-panel" :role="kind === 'error' ? 'alert' : 'status'">
    <span class="state-panel__icon"><AppIcon :name="kind === 'loading' ? 'clock' : kind === 'error' ? 'close' : 'layers'" /></span>
    <div>
      <h3>{{ title }}</h3>
      <p v-if="description">{{ description }}</p>
      <slot />
    </div>
  </div>
</template>
