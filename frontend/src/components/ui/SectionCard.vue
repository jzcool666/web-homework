<script setup>
defineProps({ title: { type: String, default: '' } })
</script>

<template>
  <section class="section-card">
    <h2 v-if="title">{{ title }}</h2>
    <slot />
  </section>
</template>
