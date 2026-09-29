<script setup>
defineProps({ name: { type: String, required: true }, size: { type: Number, default: 20 } })
</script>

<template>
  <svg :width="size" :height="size" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
    <template v-if="name === 'home'"><path d="m3 10 9-7 9 7v10a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1z"/><path d="M9 21v-7h6v7"/></template>
    <template v-else-if="name === 'book'"><path d="M12 6c-3-2-6-2-9-1v15c3-1 6-1 9 1 3-2 6-2 9-1V5c-3-1-6-1-9 1Z"/><path d="M12 6v15"/></template>
    <template v-else-if="name === 'clock'"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l4 2"/></template>
    <template v-else-if="name === 'check'"><rect x="4" y="3" width="16" height="18" rx="2"/><path d="m8 10 2 2 3-3M8 16h8"/></template>
    <template v-else-if="name === 'flask'"><path d="M9 3h6M10 3v7l-6 9a1.5 1.5 0 0 0 1.3 2h13.4a1.5 1.5 0 0 0 1.3-2l-6-9V3M7.5 16h9"/></template>
    <template v-else-if="name === 'chart'"><path d="M4 20V11M10 20V4M16 20v-7M22 20V8"/></template>
    <template v-else-if="name === 'spark'"><path d="m12 2 2 7 7 2-7 2-2 7-7-2 7-2zM19 18l1 2 2 1-2 1"/></template>
    <template v-else-if="name === 'network'"><circle cx="5" cy="12" r="2"/><circle cx="19" cy="5" r="2"/><circle cx="19" cy="19" r="2"/><path d="m7 11 10-5M7 13l10 5M19 7v10"/></template>
    <template v-else-if="name === 'star'"><path d="m12 3 2.8 5.8 6.4.9-4.6 4.5 1.1 6.4-5.7-3-5.7 3 1.1-6.4-4.6-4.5 6.4-.9z"/></template>
    <template v-else-if="name === 'layers'"><path d="m12 3 9 5-9 5-9-5zM3 12l9 5 9-5M3 16l9 5 9-5"/></template>
    <template v-else-if="name === 'calendar'"><rect x="3" y="5" width="18" height="16" rx="2"/><path d="M7 3v4M17 3v4M3 10h18"/></template>
    <template v-else-if="name === 'people'"><circle cx="9" cy="8" r="3"/><path d="M3 20v-2a6 6 0 0 1 12 0v2M17 5a3 3 0 0 1 0 6M17 14a5 5 0 0 1 4 5v1"/></template>
    <template v-else-if="name === 'menu'"><path d="M4 6h16M4 12h16M4 18h16"/></template>
    <template v-else-if="name === 'close'"><path d="M5 5l14 14M19 5 5 19"/></template>
    <template v-else-if="name === 'arrow'"><path d="M4 12h16m-6-6 6 6-6 6"/></template>
  </svg>
</template>
