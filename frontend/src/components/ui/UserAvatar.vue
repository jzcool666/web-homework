<script setup>
defineProps({ role: { type: String, default: 'student' }, size: { type: Number, default: 34 } })
</script>
<template>
  <svg :width="size" :height="size" viewBox="0 0 48 48" class="portrait-avatar" aria-hidden="true">
    <circle cx="24" cy="24" r="24" fill="#e7efff" />
    <path d="M8 48v-8c0-8 7-12 16-12s16 4 16 12v8" :fill="role === 'teacher' ? '#315a9f' : '#5888ed'" />
    <path d="m18 30 6 8 6-8" fill="#fff" />
    <path d="M20 24h8v8l-4 3-4-3" fill="#e9b69b" />
    <ellipse cx="24" cy="18" rx="10" ry="13" fill="#f6cbb0" />
    <path d="M14 20c-5-15 6-21 16-15 6 3 6 10 3 15l-3-7c-6 2-10-1-11-2l-3 8" fill="#263454" />
    <path d="M20 23q4 3 8 0" fill="none" stroke="#bf7866" stroke-width="1.3" stroke-linecap="round" />
    <circle cx="20" cy="18" r="1" fill="#263454" /><circle cx="28" cy="18" r="1" fill="#263454" />
    <path v-if="role === 'teacher'" d="M15 17h7v4h-7zm11 0h7v4h-7zm-4 1h4" fill="none" stroke="#263454" stroke-width="1.2" />
  </svg>
</template>
<style scoped>.portrait-avatar { flex: none; border-radius: 50%; display: block; }</style>
