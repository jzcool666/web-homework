<script setup>
import { initialClassId } from '@/utils/overview'
/**
 * 教师课堂入口（SPEC-012 E052）。
 *
 * 选择一个任教班级，从预置实验中开一个共享演示；每班同时只能有一个进行中的
 * 演示（服务器用部分唯一索引保证，冲突返回 409）。
 */
import { computed, onMounted, ref } from 'vue'
import { RouterLink, useRouter } from 'vue-router'

import AppIcon from '@/components/ui/AppIcon.vue'
import DemoLessonArt from '@/components/demo/DemoLessonArt.vue'
import PageHeader from '@/components/ui/PageHeader.vue'
import SectionCard from '@/components/ui/SectionCard.vue'
import StatePanel from '@/components/ui/StatePanel.vue'
import StatusBadge from '@/components/ui/StatusBadge.vue'
import { api } from '@/api/client'
import { modelLabel } from '@/utils/demo'
import { MODEL_LESSONS } from '@/utils/demoPresentation'

const router = useRouter()

const classes = ref([])
const experiments = ref([])
const demos = ref([])
const classId = ref('')
const experimentId = ref('')
const state = ref('loading')
const loadError = ref('')
const error = ref(null)
const busy = ref(false)

const activeDemo = computed(() => demos.value.find((demo) => demo.active) ?? null)
const selectedExperiment = computed(() => experiments.value.find(item => item.id === Number(experimentId.value)))

async function load() {
  state.value = 'loading'
  error.value = null
  try {
    const [classList, experimentList] = await Promise.all([
      api.get('/classes?page_size=100'),
      api.get('/experiments?page_size=100'),
    ])
    classes.value = classList
    experiments.value = experimentList
    if (!classId.value) classId.value = initialClassId(classList)
    if (!experimentId.value) experimentId.value = experimentList[0]?.id ?? ''
    demos.value = classId.value
      ? await api.get(`/demo-sessions?class_id=${classId.value}&page_size=100`)
      : []
    state.value = 'ready'
  } catch (err) {
    loadError.value = err.message
    state.value = 'error'
  }
}

async function onClassChange() {
  experimentId.value = experimentId.value || (experiments.value[0]?.id ?? '')
  await load()
}

async function startDemo() {
  if (busy.value) return
  busy.value = true
  error.value = null
  try {
    const demo = await api.post('/demo-sessions', {
      class_id: Number(classId.value),
      experiment_id: Number(experimentId.value),
    })
    demos.value = [demo, ...demos.value]
    await router.push({ name: 'teacher-demo', params: { id: demo.id } })
  } catch (err) {
    const message = err.message
    await load()
    error.value = message
  } finally {
    busy.value = false
  }
}

onMounted(load)
</script>

<template>
  <div class="classroom-page">
    <PageHeader
      eyebrow="教师空间"
      title="把时序逻辑，讲得看得见"
      description="选一个主题，拨动输入、推进时钟，和同学一起观察每一拍的变化。"
    />

    <StatePanel v-if="state === 'loading'" kind="loading" title="正在读取班级与实验" />
    <StatePanel v-else-if="state === 'error'" kind="error" title="课堂信息无法读取" :description="loadError" />

    <template v-else>
      <StatePanel
        v-if="classes.length === 0"
        title="当前没有任教班级"
        description="请联系管理员分配班级后再开展课堂演示。"
      />

      <template v-else>
        <div class="classroom-context">
            <div class="field class-field">
              <label for="class_id"><AppIcon name="people" :size="18" /> 当前课堂</label>
              <select id="class_id" v-model="classId" @change="onClassChange">
                <option v-for="item in classes" :key="item.id" :value="item.id">
                  {{ item.name }}
                </option>
              </select>
            </div>
            <span class="classroom-context__hint">一班一节共享演示 · 学生同步观看</span>
        </div>

        <div v-if="activeDemo" class="active-lesson">
          <span class="active-lesson__icon"><AppIcon name="clock" :size="26" /></span>
          <div><span class="active-lesson__label">课堂正在进行</span><h2>{{ activeDemo.experiment?.title }}</h2><p>已经执行 {{ activeDemo.state?.step_no ?? 0 }} 拍 · 继续刚才的讲解</p></div>
          <div class="active-lesson__actions"><RouterLink class="button button--primary" :to="{ name: 'teacher-demo', params: { id: activeDemo.id } }">继续演示 <AppIcon name="arrow" :size="16" /></RouterLink><RouterLink class="button button--secondary" :to="{ name: 'teacher-demo-present', params: { id: activeDemo.id } }">打开投屏</RouterLink></div>
        </div>

        <section class="lesson-picker" aria-label="选择课堂演示主题">
          <div class="lesson-picker__heading"><h2>今天讲什么？</h2><span>四个主题，把抽象的规则变成可观察的过程</span></div>
          <div class="lesson-cards">
            <button v-for="item in experiments" :key="item.id" class="lesson-card" :class="{ 'lesson-card--selected': Number(experimentId) === item.id }" type="button" :aria-pressed="Number(experimentId) === item.id" :disabled="busy" @click="experimentId = item.id">
              <div class="lesson-card__top"><span>{{ MODEL_LESSONS[item.simulator_type]?.caption || modelLabel(item.simulator_type) }}</span><span class="lesson-card__check">{{ Number(experimentId) === item.id ? '✓' : '○' }}</span></div>
              <DemoLessonArt :type="item.simulator_type" />
              <strong>{{ MODEL_LESSONS[item.simulator_type]?.title }}</strong><p>{{ MODEL_LESSONS[item.simulator_type]?.description }}</p><small>{{ item.title }}</small>
            </button>
          </div>
          <p v-if="experiments.length === 0" class="hint">
            还没有可演示的实验，请先准备并发布实验内容。
          </p>
          <p v-if="activeDemo" class="hint">
            该班级已有进行中的演示；要换实验请先在控制台结束它。
          </p>
          <p v-if="error" class="error" role="alert">{{ error }}</p>
          <div class="lesson-start"><div><strong>{{ selectedExperiment?.title || '选择一个演示主题' }}</strong><p>{{ activeDemo ? '请先结束正在进行的演示，再开启新主题。' : '设置输入 → 前进一拍 → 观察变化 → 请同学预测下一拍' }}</p></div><button class="button button--primary" type="button" :disabled="busy || !experimentId || Boolean(activeDemo)" @click="startDemo"><AppIcon name="clock" :size="17" /> {{ busy ? '正在开启…' : '开始演示' }}</button></div>
        </section>

        <SectionCard title="本班演示记录">
          <div v-if="demos.length === 0" class="empty">
            这个班级还没有演示记录。选择实验后点「开始演示」。
          </div>
          <div v-else class="demo-list">
            <div v-for="demo in demos" :key="demo.id" class="demo-row">
              <span class="demo-row__icon"><AppIcon name="clock" /></span>
              <div class="demo-row__body">
                <strong>{{ demo.experiment?.title }}</strong>
                <small>
                  {{ modelLabel(demo.experiment?.simulator_type) }} ·
                  已执行 {{ demo.state?.step_no ?? 0 }} 拍 · 版本 {{ demo.version }} ·
                  {{ demo.last_updated }}
                </small>
              </div>
              <StatusBadge :tone="demo.active ? 'success' : 'neutral'">
                {{ demo.active ? '进行中' : '已结束' }}
              </StatusBadge>
              <RouterLink class="button button--secondary" :to="{ name: 'teacher-demo', params: { id: demo.id } }">
                控制台
              </RouterLink>
              <RouterLink
                v-if="demo.active"
                class="button button--secondary"
                :to="{ name: 'teacher-demo-present', params: { id: demo.id } }"
              >
                投屏
              </RouterLink>
            </div>
          </div>
        </SectionCard>
      </template>
    </template>
  </div>
</template>

<style scoped>
.classroom-page { width: 100%; }
.classroom-context { display: flex; align-items: center; justify-content: space-between; gap: 15px; margin: 5px 0 24px; }.classroom-context .class-field { flex-direction: row; align-items: center; gap: 15px; }.class-field label { display: flex; align-items: center; gap: 7px; }.classroom-context__hint { color: #8d9db5; font-size: .74rem; }
.active-lesson { display: flex; gap: 20px; align-items: center; padding: 24px; border-radius: 18px; border: 1px solid #ccdcfa; background: linear-gradient(110deg,#edf3ff,#fcfdff); margin-bottom: 24px; }.active-lesson__icon { display: grid; place-items: center; width: 54px; height: 54px; border-radius: 16px; background: #dce7ff; color: #4a76de; flex-shrink: 0; }.active-lesson__label { color: #5179c4; font-size: .72rem; }.active-lesson h2 { color: #294c7d; font-size: 1.1rem; margin: 7px 0; }.active-lesson p { color: #8193ad; font-size: .75rem; margin: 0; }.active-lesson__actions { display: flex; gap: 10px; margin-left: auto; flex-wrap: wrap; }
.lesson-picker { margin-bottom: 28px; }.lesson-picker__heading { display: flex; align-items: baseline; gap: 14px; flex-wrap: wrap; margin-bottom: 16px; }.lesson-picker__heading h2 { color: #38547d; font-size: 1.06rem; margin: 0; }.lesson-picker__heading span { color: #94a2b8; font-size: .74rem; }.lesson-cards { display: grid; grid-template-columns: repeat(4,minmax(0,1fr)); gap: 16px; }.lesson-card { padding: 17px; border: 1px solid #e2eaf6; border-radius: 17px; background: white; text-align: left; cursor: pointer; transition: border-color .2s,box-shadow .2s,transform .2s; min-width: 0; }.lesson-card:hover { transform: translateY(-3px); border-color: #a9bfee; box-shadow: 0 10px 25px #4c70af12; }.lesson-card--selected { border: 2px solid #6687e5; padding: 16px; background: linear-gradient(180deg,#f0f5ff,white); box-shadow: 0 6px 20px #5279d915; }.lesson-card:focus-visible { outline: 3px solid #b0c6ff; outline-offset: 3px; }.lesson-card__top { display: flex; justify-content: space-between; gap: 10px; color: #7187a8; font-size: .73rem; }.lesson-card__check { color: #6789dc; }.lesson-card strong { font-size: .93rem; color: #3c587f; display: block; margin: 6px 0 9px; }.lesson-card p { font-size: .75rem; line-height: 1.8; color: #889ab4; min-height: 2.8em; margin: 0 0 12px; }.lesson-card small { display: block; border-top: 1px solid #eaf0f9; padding-top: 10px; color: #a0afc4; font-size: .62rem; line-height: 1.5; }.lesson-start { display: flex; align-items: center; justify-content: space-between; gap: 16px; padding: 19px 4px 0; }.lesson-start strong { font-size: .82rem; color: #527097; }.lesson-start p { font-size: .72rem; color: #93a3b9; margin: 6px 0 0; }
@media(max-width:1200px) { .lesson-cards { grid-template-columns: repeat(2,minmax(0,1fr)); }.active-lesson { flex-wrap: wrap; }.active-lesson__actions { margin-left: 74px; } }
@media(max-width:600px) { .classroom-context { flex-direction: column; align-items: flex-start; gap: 10px; }.classroom-context .class-field { width: 100%; flex-direction: column; align-items: stretch; gap: 8px; }.class-field select { min-width: 0; width: 100%; }.classroom-context__hint { font-size: .65rem; }.lesson-cards { gap: 10px; }.lesson-card { padding: 12px; }.lesson-card--selected { padding: 11px; }.lesson-card strong { font-size: .79rem; }.lesson-card p { font-size: .65rem; }.lesson-card small { display: none; }.active-lesson { padding: 18px; gap: 13px; }.active-lesson__icon { width: 42px; height: 42px; }.active-lesson h2 { font-size: .92rem; }.active-lesson__actions { margin-left: 0; }.lesson-start { align-items: flex-start; flex-direction: column; }.lesson-start .button { width: 100%; } }
@media(prefers-reduced-motion:reduce) { .lesson-card { transition: none; }.lesson-card:hover { transform: none; } }
.classroom-page .section-card { margin-bottom: var(--space-4); }
.picker { display: flex; align-items: flex-end; gap: var(--space-3); flex-wrap: wrap; }
.field { display: flex; flex-direction: column; gap: var(--space-1); }
.field select { padding: var(--space-2) var(--space-3); border: 1px solid var(--color-border); border-radius: var(--radius-sm); background: #fff; min-width: 14rem; }
.field label { font-size: var(--font-size-sm); color: var(--color-text-secondary); }
.demo-list { display: grid; gap: var(--space-3); }
.demo-row { display: flex; align-items: center; gap: var(--space-3); flex-wrap: wrap; padding: var(--space-3); border: 1px solid var(--color-border); border-radius: var(--radius-sm); }
.demo-row__icon { display: grid; place-items: center; width: 2.6rem; height: 2.6rem; border-radius: var(--radius-sm); color: var(--color-primary); background: var(--color-primary-soft); }
.demo-row__body { display: grid; gap: 2px; margin-right: auto; }
.demo-row__body small { color: var(--color-text-secondary); font-size: var(--font-size-xs); }
.empty { color: var(--color-text-secondary); }
.hint { color: var(--color-text-secondary); font-size: var(--font-size-sm); }
.error { color: var(--color-danger); }
code { font-family: var(--font-mono); font-size: var(--font-size-xs); }
</style>
