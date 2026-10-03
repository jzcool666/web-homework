<script setup>
import { modelLabel } from '@/utils/demo'
defineProps({ kind: { type: String, required: true } })
</script>
<template>
  <figure class="circuit-preview">
    <svg
      viewBox="0 0 230 130"
      role="img"
      :aria-label="`${modelLabel(kind)}概念框图，非实时仿真`"
    >
      <path
        d="M16 38H74M16 68H74M148 38H204M148 92H204"
        fill="none"
        stroke="currentColor"
        stroke-width="2"
      />
      <rect
        x="74"
        y="17"
        width="74"
        height="96"
        rx="6"
        fill="var(--color-bg-card)"
        stroke="currentColor"
        stroke-width="2"
      />
      <text x="111" y="57" text-anchor="middle">{{ kind.toUpperCase() }}</text>
      <text x="111" y="81" text-anchor="middle" font-size="11">
        {{ modelLabel(kind) }}
      </text>
      <text x="2" y="30" font-size="11">输入</text>
      <text x="2" y="62" font-size="11">CLK</text>
      <text x="206" y="42">Q</text>
      <text x="194" y="112" font-size="10">状态输出</text>
      <path
        d="M74 60L84 68L74 76"
        fill="none"
        stroke="currentColor"
        stroke-width="2"
      />
    </svg>
    <figcaption>概念示意 · 非实时仿真</figcaption>
  </figure>
</template>
<style scoped>
.circuit-preview {
  margin: 0;
  max-width: 17rem;
  color: var(--color-primary);
}
svg {
  display: block;
  width: 100%;
  font-family: var(--font-mono);
}
figcaption {
  text-align: center;
  font-size: var(--font-size-xs);
  color: var(--color-text-secondary);
}
</style>
