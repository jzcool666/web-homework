<script setup>
import { RouterLink } from 'vue-router'

import AppIcon from '@/components/ui/AppIcon.vue'
</script>

<template>
  <div class="auth-layout">
    <header class="auth-layout__header">
      <RouterLink class="brand" :to="{ name: 'home' }">
        <span class="brand__mark"><AppIcon name="book" :size="25" /></span>
        <span class="brand__name">学海通<span class="brand__divider">·</span><small>数字逻辑课程学习系统</small></span>
      </RouterLink>
    </header>
    <main class="auth-layout__main" id="main-content">
      <div class="auth-layout__intro">
        <span class="eyebrow">时序逻辑学习空间</span>
        <h2>看懂每一次<br />状态变化。</h2>
        <p>从触发器到计数器，沿着清晰的课堂流程学习数字逻辑。</p>
        <div class="auth-layout__signal" aria-hidden="true">
          <span>CLK</span><svg viewBox="0 0 300 48" preserveAspectRatio="none"><path d="M0 38H35V10H70V38H105V10H140V38H175V10H210V38H245V10H280V38H300"/></svg>
          <span>Q(t) → Q(t+1)</span>
        </div>
      </div>
      <div class="auth-layout__form"><slot /></div>
    </main>
  </div>
</template>
