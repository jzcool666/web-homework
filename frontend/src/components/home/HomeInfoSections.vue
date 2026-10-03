<script setup>
/** 各角色首页共用的信息区块：概念示意、模块开放情况与系统连接。 */
import { onMounted } from 'vue'

import HealthBadge from '@/components/HealthBadge.vue'
import AppIcon from '@/components/ui/AppIcon.vue'
import SectionCard from '@/components/ui/SectionCard.vue'
import StatusBadge from '@/components/ui/StatusBadge.vue'
import { useHealthStore } from '@/stores/health'

const health = useHealthStore()

onMounted(() => health.load())
</script>

<template>
  <div class="home-grid home-grid--bottom">
    <SectionCard title="时序逻辑概览">
      <div class="concept">
        <div class="concept__diagram" aria-label="JK 触发器概念示意图">
          <span class="concept__input">J<br />CLK<br />K</span>
          <span class="concept__block">JK<br /><small>触发器</small></span>
          <span class="concept__output">Q<br /><br />Q̅</span>
        </div>
        <p>这里是概念示意。逐拍演示与波形请进入「我的课堂」或教师「课堂」。</p>
      </div>
    </SectionCard>
    <SectionCard title="系统连接">
      <HealthBadge />
      <button class="button button--secondary" type="button" :disabled="health.loading" @click="health.load()">重新检查</button>
    </SectionCard>
  </div>

  <SectionCard title="学习与教学模块">
    <div class="module-list">
      <div><AppIcon name="book" /><span>课程知识与教学资源</span><StatusBadge tone="success">已开放</StatusBadge></div>
      <div><AppIcon name="clock" /><span>课堂演示与时序仿真</span><StatusBadge tone="success">已开放</StatusBadge></div>
      <div><AppIcon name="check" /><span>题库练习与错题</span><StatusBadge tone="success">已开放</StatusBadge></div>
      <div><AppIcon name="flask" /><span>实验辅助与验证</span><StatusBadge tone="success">已开放</StatusBadge></div>
      <div><AppIcon name="spark" /><span>课程检索问答</span><StatusBadge tone="success">已开放</StatusBadge></div>
    </div>
  </SectionCard>
</template>

<style scoped>
.concept__diagram { display: flex; align-items: center; justify-content: center; gap: var(--space-4); min-height: 10rem; padding: var(--space-4); border: 1px solid var(--color-border); border-radius: var(--radius-sm); background-color: var(--color-grid-surface); background-image: linear-gradient(var(--color-grid-line) 1px, transparent 1px), linear-gradient(90deg, var(--color-grid-line) 1px, transparent 1px); background-size: 18px 18px; font: 650 var(--font-size-sm) var(--font-mono); }
.concept__input, .concept__output { line-height: 2.2; }
.concept__block { position: relative; display: grid; place-items: center; width: 6rem; height: 6rem; border: 2px solid var(--color-text-primary); background: white; text-align: center; line-height: 1.2; }
.concept__block::before, .concept__block::after { content: ''; position: absolute; top: 50%; width: 1.5rem; height: 2px; background: var(--color-text-primary); }
.concept__block::before { right: 100%; }
.concept__block::after { left: 100%; }
.concept__block small { font-size: var(--font-size-xs); font-weight: 650; font-family: inherit; }
.concept p { color: var(--color-text-secondary); font-size: var(--font-size-xs); margin: var(--space-3) 0 0; }
.module-list { display: grid; gap: var(--space-3); }
.module-list > div { display: flex; align-items: center; gap: var(--space-3); padding: var(--space-2) 0; border-bottom: 1px solid var(--color-border); font-size: var(--font-size-sm); }
.module-list > div:last-child { border-bottom: 0; }
.module-list svg { color: var(--color-primary); }
.module-list .status-badge { margin-left: auto; }
</style>
