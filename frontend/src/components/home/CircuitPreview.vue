<script setup>
import { modelLabel, inputsFor, inputLabel } from '@/utils/demo'
defineProps({ kind: { type: String, required: true } })
</script>
<template>
  <figure class="circuit-preview">
    <svg
      viewBox="0 0 230 130"
      role="img"
      :aria-label="`${modelLabel(kind)}概念框图，非实时仿真`"
    >
      <g
        v-for="(pin, index) in inputsFor(kind).filter((pin) => pin !== 'reset')"
        :key="pin"
      >
        <path
          :d="`M34 ${32 + index * 24}H82`"
          fill="none"
          stroke="currentColor"
          stroke-width="1.5"
        />
        <text x="10" :y="36 + index * 24" font-size="12">
          {{ inputLabel(pin) }}
        </text>
      </g>
      <path
        d="M34 96H82M150 40H202M150 83H202"
        fill="none"
        stroke="currentColor"
        stroke-width="1.5"
      />
      <rect
        x="82"
        y="17"
        width="68"
        height="96"
        rx="6"
        fill="var(--color-bg-card)"
        stroke="currentColor"
        stroke-width="2"
      />
      <text x="116" y="58" text-anchor="middle" font-size="16">
        {{ { d: 'D', jk: 'JK', counter: 'CTR', shift: 'SR' }[kind] ?? '?' }}
      </text>
      <text x="116" y="77" text-anchor="middle" font-size="9">
        {{
          {
            d: '触发器',
            jk: '触发器',
            counter: '4 位计数器',
            shift: '4 位寄存器',
          }[kind] ?? '未知模型'
        }}
      </text>
      <text x="8" y="100" font-size="11">CLK</text>
      <text x="206" y="42">
        {{ kind === 'counter' || kind === 'shift' ? 'Q3' : 'Q' }}
      </text>
      <text x="204" y="87" font-size="11">
        {{ kind === 'd' || kind === 'jk' ? 'Q̅' : 'Q0' }}
      </text>
      <path
        d="M82 89L90 96L82 103"
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
  color: #28478c;
  padding: 12px;
  border: 1px solid var(--color-border);
  border-radius: 9px;
  background: linear-gradient(145deg, #fff, #f7faff);
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
