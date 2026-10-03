<script setup>
import AppIcon from './AppIcon.vue'

defineProps({
  title: { type: String, required: true },
  description: { type: String, default: '' },
  eyebrow: { type: String, default: '' },
  icon: { type: String, default: '' },
  steps: { type: Array, default: () => [] },
})
</script>

<template>
  <header class="page-header">
    <div class="page-header__content">
      <span v-if="eyebrow" class="eyebrow">{{ eyebrow }}</span>
      <div class="page-header__title"><span v-if="icon" class="page-header__icon"><AppIcon :name="icon" :size="23" /></span><h1>{{ title }}</h1></div>
      <p v-if="description">{{ description }}</p>
      <ol v-if="steps.length" class="workflow-guide" aria-label="操作顺序">
        <li v-for="(step, index) in steps" :key="index"><span aria-hidden="true">{{ index + 1 }}</span>{{ step }}</li>
      </ol>
    </div>
    <div v-if="$slots.actions" class="page-header__actions"><slot name="actions" /></div>
  </header>
</template>
