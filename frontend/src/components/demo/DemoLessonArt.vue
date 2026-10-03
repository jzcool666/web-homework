<script setup>
defineProps({ type: { type: String, required: true } })
</script>
<template>
  <svg class="lesson-art" viewBox="0 0 270 112" aria-hidden="true">
    <template v-if="type === 'd' || type === 'jk'">
      <path d="M40 41 H98 M170 51 H223 M42 86 H77 V77 H98" class="art-wire"/>
      <path v-if="type === 'jk'" d="M40 63 H98" class="art-wire"/>
      <rect x="98" y="16" width="72" height="74" rx="12" class="art-memory"/>
      <text x="134" y="52" class="art-white">{{ type === 'd' ? 'D' : 'JK' }}</text><text x="134" y="72" class="art-small-white">记忆</text>
      <circle cx="32" cy="41" r="12" class="art-input"/><circle cx="233" cy="51" r="16" class="art-lamp"/>
      <text x="32" y="46" class="art-small">1</text><text x="233" y="57" class="art-number">1</text>
      <path d="M24 88 V75 H37 V88 H50" class="art-clock"/>
    </template>
    <template v-else-if="type === 'counter'">
      <path d="M47 41 H224 V83 H47" class="art-wire"/>
      <g v-for="n in 6" :key="n"><circle :cx="n <= 3 ? 47 + (n - 1) * 88 : 47 + (6 - n) * 88" :cy="n <= 3 ? 35 : 83" r="17" :class="n === 3 ? 'art-active' : 'art-node'"/><text :x="n <= 3 ? 47 + (n - 1) * 88 : 47 + (6 - n) * 88" :y="n <= 3 ? 41 : 89" class="art-number" :class="{ 'art-text-active': n === 3 }">{{ n - 1 }}</text></g>
    </template>
    <template v-else>
      <path d="M15 56 H253" class="art-wire"/>
      <g v-for="(bit,index) in [1,0,1,0]" :key="index"><rect :x="24 + index * 60" y="27" width="44" height="55" rx="9" :class="bit ? 'art-cell-on' : 'art-node'"/><text :x="46 + index * 60" y="61" class="art-number">{{ bit }}</text><text :x="46 + index * 60" y="100" class="art-small">Q{{ 3 - index }}</text></g>
      <path d="m77 51 5 5-5 5m60-10 5 5-5 5m60-10 5 5-5 5" class="art-wire"/>
    </template>
  </svg>
</template>
<style scoped>
.lesson-art { width: 100%; height: 112px; display: block; }.art-wire { fill: none; stroke: #bfcfe5; stroke-width: 2; }.art-memory { fill: #597fdf; }.art-white { fill: white; text-anchor: middle; font: 700 24px var(--font-mono); }.art-small-white { fill: #d3e0ff; text-anchor: middle; font: 11px sans-serif; }.art-input { fill: #dce8ff; stroke: #89a8eb; stroke-width: 2; }.art-lamp { fill: #ffdda2; stroke: #f2bd68; stroke-width: 3; }.art-small { fill: #7892b5; text-anchor: middle; font: 11px var(--font-mono); }.art-number { fill: #657da0; text-anchor: middle; font: 700 19px var(--font-mono); }.art-clock { fill: none; stroke: #ac8ed8; stroke-width: 2.5; }.art-node { fill: white; stroke: #d5e0ef; stroke-width: 2; }.art-active { fill: #3caaa4; stroke: #e1f4f1; stroke-width: 4; }.art-text-active { fill: white; }.art-cell-on { fill: #fff0d8; stroke: #e1b16b; stroke-width: 2; }
</style>
