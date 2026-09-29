<script setup>
/**
 * 当前状态与下一状态面板（SPEC-012 第 4 节第 5、7 条）。
 *
 * 「下一个有效上升沿」是否可见完全取决于服务器的 reveal_next：
 * 隐藏时 next_q 为 null，这里显示「待揭示」，绝不在前端自行推算。
 */
import { computed } from 'vue'

import StatusBadge from '@/components/ui/StatusBadge.vue'
import { bitLabels, bitsOf, formatStateValue, inputLabel, inputsFor } from '@/utils/demo'

const props = defineProps({
  state: { type: Object, default: () => ({}) },
  nextQ: { type: Number, default: null },
  revealNext: { type: Boolean, default: false },
  simulatorType: { type: String, required: true },
  large: { type: Boolean, default: false },
})

const labels = computed(() => bitLabels(props.simulatorType))
const pins = computed(() => inputsFor(props.simulatorType))
const qBits = computed(() => bitsOf(props.state?.q ?? 0, props.simulatorType))
const nextBits = computed(() =>
  props.nextQ === null || props.nextQ === undefined ? [] : bitsOf(props.nextQ, props.simulatorType),
)
const nextVisible = computed(() => props.revealNext && props.nextQ !== null && props.nextQ !== undefined)
</script>

<template>
  <div class="state-grid" :class="{ 'state-grid--large': large }">
    <div class="state-block">
      <span class="state-block__title">时钟 CLK</span>
      <div class="state-block__value">
        <span class="bit" :class="{ 'bit--on': state?.clock }">{{ state?.clock ? 1 : 0 }}</span>
        <small>初始为 0；切换一次是半个周期</small>
      </div>
    </div>

    <div class="state-block">
      <span class="state-block__title">当前状态 Q</span>
      <div class="state-block__value">
        <span
          v-for="(bit, index) in qBits"
          :key="labels[index]"
          class="state-bit"
        >
          <small>{{ labels[index] }}</small>
          <span class="bit" :class="{ 'bit--on': bit }">{{ bit }}</span>
        </span>
        <small>{{ formatStateValue(state?.q ?? 0, simulatorType) }}</small>
      </div>
    </div>

    <div class="state-block">
      <span class="state-block__title">输入</span>
      <div class="state-block__value">
        <span v-for="pin in pins" :key="pin" class="state-bit">
          <small>{{ inputLabel(pin) }}</small>
          <span class="bit" :class="{ 'bit--on': state?.inputs?.[pin] }">
            {{ state?.inputs?.[pin] ?? 0 }}
          </span>
        </span>
      </div>
    </div>

    <div class="state-block">
      <span class="state-block__title">下一状态 Q(t+1)</span>
      <div class="state-block__value">
        <template v-if="nextVisible">
          <span v-for="(bit, index) in nextBits" :key="`next-${labels[index]}`" class="state-bit">
            <small>{{ labels[index] }}</small>
            <span class="bit bit--next" :class="{ 'bit--on': bit }">{{ bit }}</span>
          </span>
          <small>{{ formatStateValue(nextQ, simulatorType) }}</small>
        </template>
        <template v-else>
          <StatusBadge tone="warning">待揭示</StatusBadge>
          <small>预测模式进行中，服务器未返回下一状态</small>
        </template>
      </div>
    </div>

    <div class="state-block">
      <span class="state-block__title">已执行拍数</span>
      <div class="state-block__value">
        <strong class="step-no">{{ state?.step_no ?? 0 }}</strong>
        <small>只统计有效上升沿；下降沿与单独改输入不增加</small>
      </div>
    </div>
  </div>
</template>

<style scoped>
.state-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(15rem, 1fr));
  gap: var(--space-3);
}

.state-block {
  padding: var(--space-3);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: var(--color-grid-surface);
}

.state-block__title {
  display: block;
  font-size: var(--font-size-xs);
  font-weight: 800;
  letter-spacing: 0.06em;
  color: var(--color-text-secondary);
}

.state-block__value {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  flex-wrap: wrap;
  margin-top: var(--space-2);
}

.state-block__value small {
  color: var(--color-text-secondary);
  font-size: var(--font-size-xs);
}

.state-bit {
  display: grid;
  justify-items: center;
  gap: 2px;
}

.state-bit small {
  font: 650 var(--font-size-xs) var(--font-mono);
  color: var(--color-text-secondary);
}

.bit {
  display: inline-grid;
  place-items: center;
  min-width: 1.9rem;
  height: 1.9rem;
  padding: 0 var(--space-1);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: #fff;
  font: 700 var(--font-size-base) var(--font-mono);
  color: var(--color-text-secondary);
}

.bit--on {
  border-color: var(--color-primary);
  background: var(--color-primary-soft);
  color: var(--color-primary);
}

.bit--next {
  border-style: dashed;
  border-color: var(--color-accent);
}

.step-no {
  font: 800 var(--font-size-lg) var(--font-mono);
  color: var(--color-text-primary);
}

.state-grid--large .bit {
  min-width: 2.6rem;
  height: 2.6rem;
  font-size: var(--font-size-lg);
}

.state-grid--large .state-block__title {
  font-size: var(--font-size-sm);
}

.state-grid--large .state-block__value small {
  font-size: var(--font-size-sm);
}
</style>
