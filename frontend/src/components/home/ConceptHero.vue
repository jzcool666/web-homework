<script setup>
import { RouterLink } from 'vue-router'

import AppIcon from '@/components/ui/AppIcon.vue'

defineProps({
  tag: { type: String, default: '数字逻辑 · 时序逻辑' },
  title: { type: String, required: true },
  lead: { type: String, default: '' },
  ctaLabel: { type: String, required: true },
  ctaTo: { type: [String, Object], required: true },
})
</script>

<template>
  <section class="hero hero--compact">
    <div class="hero__copy">
      <span class="hero__tag">{{ tag }}</span>
      <h2>{{ title }}</h2>
      <p v-if="lead" class="hero__lead">{{ lead }}</p>
      <RouterLink class="button hero__button" :to="ctaTo">
        {{ ctaLabel }} <AppIcon name="arrow" :size="16" />
      </RouterLink>
    </div>
    <div class="hero__visual" aria-hidden="true">
      <span class="hero__chip">CLK</span>
      <svg viewBox="0 0 320 120" preserveAspectRatio="xMidYMid meet">
        <path class="hero__grid" d="M0 30H320M0 60H320M0 90H320M40 0V120M80 0V120M120 0V120M160 0V120M200 0V120M240 0V120M280 0V120"/>
        <path class="hero__wave" d="M8 92H42V40H80V92H120V40H160V92H200V40H240V92H280V40H312"/>
        <path class="hero__wave hero__wave--light" d="M8 106H80V72H160V106H240V72H312"/>
      </svg>
      <span class="hero__binary">Q(t) → Q(t+1)</span>
    </div>
  </section>
</template>

<style scoped>
/* 压缩 Hero：高度目标 ≤ 210px，第一屏要留出卡片空间（骨架 §5a / §9）。 */
.hero {
  display: grid; grid-template-columns: minmax(0, 1.4fr) minmax(14rem, .6fr);
  overflow: hidden; margin-bottom: var(--space-4); border-radius: var(--radius-lg);
  background: var(--color-hero); color: white; box-shadow: var(--shadow-card);
}
.hero--compact .hero__copy { padding: var(--space-5) var(--space-6); }
.hero__tag { color: var(--color-hero-label); font-size: var(--font-size-xs); font-weight: 800; letter-spacing: .1em; }
.hero h2 { font-size: clamp(1.3rem, 2vw, 1.7rem); line-height: 1.3; margin: var(--space-2) 0 var(--space-3); }
.hero__lead { color: var(--color-hero-text); font-size: var(--font-size-sm); margin: 0 0 var(--space-3); }
.hero__button { background: white; color: var(--color-primary); }
.hero__visual { position: relative; display: grid; place-items: center; padding: var(--space-4); background: var(--color-hero-panel); }
.hero__visual svg { width: 100%; max-width: 20rem; }
.hero__grid { stroke: rgb(255 255 255 / 8%); stroke-width: 1; fill: none; }
.hero__wave { stroke: var(--color-wave-clock); stroke-width: 3; fill: none; }
.hero__wave--light { stroke: var(--color-wave-state); }
.hero__chip, .hero__binary { position: absolute; font: 700 var(--font-size-xs) var(--font-mono); color: var(--color-hero-text); }
.hero__chip { top: var(--space-3); left: var(--space-4); }
.hero__binary { right: var(--space-4); bottom: var(--space-2); }
@media (max-width: 1050px) { .hero { grid-template-columns: 1fr; } .hero__visual { display: none; } }
</style>
