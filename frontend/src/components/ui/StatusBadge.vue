<script setup>
defineProps({
  tone: { type: String, default: 'neutral', validator: (value) => ['neutral', 'success', 'warning', 'danger'].includes(value) },
})
</script>

<template><span class="status-badge" :class="`status-badge--${tone}`"><slot /></span></template>
