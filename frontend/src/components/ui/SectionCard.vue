<script setup>
defineProps({ title: { type: String, default: '' } })
</script>

<template>
  <section class="section-card">
    <h2 v-if="title" class="section-card__heading">{{ title }}</h2>
    <slot />
  </section>
</template>
