<script setup>
import { computed, onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'

import HealthBadge from '@/components/HealthBadge.vue'
import AppIcon from '@/components/ui/AppIcon.vue'
import PageHeader from '@/components/ui/PageHeader.vue'
import SectionCard from '@/components/ui/SectionCard.vue'
import StatePanel from '@/components/ui/StatePanel.vue'
import StatusBadge from '@/components/ui/StatusBadge.vue'
import { api } from '@/api/client'
import { useAuthStore } from '@/stores/auth'
import { useHealthStore } from '@/stores/health'

const auth = useAuthStore()
const health = useHealthStore()
const classes = ref([])
const classState = ref('idle')
const classError = ref('')
const role = computed(() => auth.user?.role)
const isStudent = computed(() => role.value === 'student')
const isTeacher = computed(() => role.value === 'teacher')
const isAdmin = computed(() => role.value === 'admin')

async function loadClasses() {
  classState.value = 'loading'
  try {
    classes.value = await api.get('/classes?page_size=100')
    classState.value = 'ready'
  } catch (err) {
    classError.value = err.message
    classState.value = 'error'
  }
}

onMounted(() => {
  health.load()
  if (isStudent.value || isTeacher.value) loadClasses()
})
</script>

<template>
  <div class="home-page">
    <template v-if="auth.user">
      <PageHeader :eyebrow="isStudent ? '学习空间' : isTeacher ? '教学空间' : '管理空间'" :title="`你好，${auth.user.display_name}`" :description="isStudent ? '从当前课堂出发，逐步理解时序逻辑。' : isTeacher ? '围绕备课、演示与讲评组织课堂。' : '管理账号、班级和入班关系。'" />
    </template>
    <PageHeader v-else eyebrow="学海通" title="把时序逻辑学清楚" description="面向教师课堂的数字逻辑学习系统。当前开放课程学习、课堂演示、习题训练与考勤。" />

    <section class="hero">
      <div class="hero__copy">
        <span class="hero__tag">数字逻辑 · 时序逻辑</span>
        <h2>{{ isTeacher ? '让每一次状态变化，都有清楚的讲解。' : isAdmin ? '从可靠的账号与班级关系开始。' : '从触发器开始，理解时序的节奏。' }}</h2>
        <p>课程内容围绕 D / JK 触发器、计数器、寄存器与状态转换展开。现在可以观看逐拍演示，也可以做习题训练。</p>
        <RouterLink v-if="auth.user" class="button hero__button" :to="{ name: isAdmin ? 'admin-users' : 'profile' }">
          {{ isAdmin ? '管理账号' : '查看个人资料' }} <AppIcon name="arrow" :size="17" />
        </RouterLink>
        <RouterLink v-else class="button hero__button" :to="{ name: 'login' }">登录学习空间 <AppIcon name="arrow" :size="17" /></RouterLink>
      </div>
      <div class="hero__visual" aria-hidden="true">
        <span class="hero__chip">CLK</span>
        <svg viewBox="0 0 320 160" preserveAspectRatio="xMidYMid meet">
          <path class="hero__grid" d="M0 40H320M0 80H320M0 120H320M40 0V160M80 0V160M120 0V160M160 0V160M200 0V160M240 0V160M280 0V160"/>
          <path class="hero__wave" d="M8 120H42V50H80V120H120V50H160V120H200V50H240V120H280V50H312"/>
          <path class="hero__wave hero__wave--light" d="M8 142H80V97H160V142H240V97H312"/>
        </svg>
        <span class="hero__binary">Q(t) → Q(t+1)</span>
      </div>
    </section>

    <div class="home-grid">
      <SectionCard :title="isAdmin ? '管理入口' : '当前课堂'">
        <template v-if="isAdmin">
          <div class="quick-links">
            <RouterLink class="quick-link" :to="{ name: 'admin-users' }"><AppIcon name="people" />账号管理<AppIcon name="arrow" :size="17" /></RouterLink>
            <RouterLink class="quick-link" :to="{ name: 'admin-classes' }"><AppIcon name="layers" />班级管理<AppIcon name="arrow" :size="17" /></RouterLink>
          </div>
        </template>
        <template v-else-if="!auth.user">
          <StatePanel title="登录后查看班级" description="学生与教师使用同一登录入口；公开注册只创建学生账号。" />
        </template>
        <StatePanel v-else-if="classState === 'loading'" kind="loading" title="正在读取班级信息" />
        <StatePanel v-else-if="classState === 'error'" kind="error" title="班级信息暂时无法读取" :description="classError" />
        <StatePanel v-else-if="classes.length === 0" :title="isStudent ? '你当前尚未加入班级' : '当前没有任教班级'" description="请联系管理员分配班级。分配完成后，这里会显示你的课堂入口。" />
        <template v-else>
          <div class="class-list">
            <div v-for="schoolClass in classes" :key="schoolClass.id" class="class-row">
              <span class="class-row__icon"><AppIcon name="book" /></span>
              <div><strong>{{ schoolClass.name }}</strong><small>课程学习、课堂演示、习题训练与考勤已开放</small></div>
              <StatusBadge :tone="schoolClass.active ? 'neutral' : 'warning'">{{ schoolClass.active ? '已分配' : '班级已停用' }}</StatusBadge>
            </div>
          </div>
        </template>
      </SectionCard>

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
    </div>

    <div class="home-grid home-grid--bottom">
      <SectionCard title="学习与教学模块">
        <div class="module-list">
          <div><AppIcon name="book" /><span>课程知识与教学资源</span><StatusBadge tone="success">已开放</StatusBadge></div>
          <div><AppIcon name="clock" /><span>课堂演示与时序仿真</span><StatusBadge tone="success">已开放</StatusBadge></div>
          <div><AppIcon name="check" /><span>题库练习与错题</span><StatusBadge tone="success">已开放</StatusBadge></div>
          <div><AppIcon name="flask" /><span>实验辅助与验证</span><StatusBadge>待开放</StatusBadge></div>
        </div>
      </SectionCard>
      <SectionCard title="系统连接">
        <HealthBadge />
        <button class="button button--secondary" type="button" :disabled="health.loading" @click="health.load()">重新检查</button>
      </SectionCard>
    </div>
  </div>
</template>

<style scoped>
.home-page { width: 100%; }
.hero { display: grid; grid-template-columns: minmax(0, 1.3fr) minmax(18rem, .7fr); overflow: hidden; margin-bottom: var(--space-4); border-radius: var(--radius-lg); background: var(--color-hero); color: white; box-shadow: var(--shadow-card); }
.hero__copy { padding: clamp(var(--space-6), 3vw, 2.5rem); }
.hero__tag { color: var(--color-hero-label); font-size: var(--font-size-xs); font-weight: 800; letter-spacing: .1em; }
.hero h2 { font-size: clamp(1.45rem, 2.6vw, 2.35rem); line-height: 1.3; max-width: 34rem; margin: var(--space-3) 0; }
.hero p { color: var(--color-hero-text); max-width: 36rem; font-size: var(--font-size-sm); }
.hero__button { background: white; color: var(--color-primary); margin-top: var(--space-2); }
.hero__visual { position: relative; align-self: stretch; display: grid; place-items: center; padding: var(--space-5); background: var(--color-hero-panel); }
.hero__visual svg { width: 100%; max-width: 23rem; }
.hero__grid { stroke: rgb(255 255 255 / 8%); stroke-width: 1; fill: none; }
.hero__wave { stroke: var(--color-wave-clock); stroke-width: 3; fill: none; }
.hero__wave--light { stroke: var(--color-wave-state); }
.hero__chip, .hero__binary { position: absolute; font: 700 var(--font-size-sm) var(--font-mono); color: var(--color-hero-text); }
.hero__chip { top: var(--space-5); left: var(--space-5); }
.hero__binary { right: var(--space-5); bottom: var(--space-4); }
.home-grid { display: grid; grid-template-columns: minmax(0, 1.2fr) minmax(18rem, .8fr); gap: var(--space-4); }
.home-grid .section-card { min-width: 0; }
.home-grid--bottom { grid-template-columns: minmax(0, 1.4fr) minmax(18rem, .6fr); }
.quick-links { display: grid; gap: var(--space-3); }
.quick-link { display: flex; align-items: center; gap: var(--space-3); min-height: 3.3rem; padding: var(--space-3); border: 1px solid var(--color-border); border-radius: var(--radius-sm); text-decoration: none; font-weight: 700; }
.quick-link svg:last-child { margin-left: auto; }
.class-list { display: grid; gap: var(--space-3); }
.class-row { display: flex; align-items: center; gap: var(--space-3); padding: var(--space-3); border: 1px solid var(--color-border); border-radius: var(--radius-sm); }
.class-row__icon { display: grid; place-items: center; width: 2.7rem; height: 2.7rem; border-radius: var(--radius-sm); color: var(--color-primary); background: var(--color-primary-soft); }
.class-row div { display: grid; }
.class-row small { color: var(--color-text-secondary); }
.class-row .status-badge { margin-left: auto; }
.concept__diagram { display: flex; align-items: center; justify-content: center; gap: var(--space-4); min-height: 10rem; padding: var(--space-4); border: 1px solid var(--color-border); border-radius: var(--radius-sm); background-color: var(--color-grid-surface); background-image: linear-gradient(var(--color-grid-line) 1px, transparent 1px), linear-gradient(90deg, var(--color-grid-line) 1px, transparent 1px); background-size: 18px 18px; font: 650 var(--font-size-sm) var(--font-mono); }
.concept__input, .concept__output { line-height: 2.2; }
.concept__block { position: relative; display: grid; place-items: center; width: 6rem; height: 6rem; border: 2px solid var(--color-text-primary); background: white; text-align: center; line-height: 1.2; }
.concept__block::before, .concept__block::after { content: ''; position: absolute; top: 50%; width: 1.5rem; height: 2px; background: var(--color-text-primary); }
.concept__block::before { right: 100%; }.concept__block::after { left: 100%; }
.concept__block small { font-size: var(--font-size-xs); font-weight: 650; font-family: inherit; }
.concept p { color: var(--color-text-secondary); font-size: var(--font-size-xs); margin: var(--space-3) 0 0; }
.module-list { display: grid; gap: var(--space-3); }
.module-list > div { display: flex; align-items: center; gap: var(--space-3); padding: var(--space-2) 0; border-bottom: 1px solid var(--color-border); font-size: var(--font-size-sm); }
.module-list > div:last-child { border-bottom: 0; }
.module-list svg { color: var(--color-primary); }
.module-list .status-badge { margin-left: auto; }
@media (max-width: 1050px) { .hero { grid-template-columns: 1fr; }.hero__visual { display: none; } }
@media (max-width: 740px) { .home-grid, .home-grid--bottom { grid-template-columns: 1fr; } }
</style>
