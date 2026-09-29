<script setup>
/**
 * 教师课堂入口（SPEC-012 E052）。
 *
 * 选择一个任教班级，从预置实验中开一个共享演示；每班同时只能有一个进行中的
 * 演示（服务器用部分唯一索引保证，冲突返回 409）。
 */
import { computed, onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'

import AppIcon from '@/components/ui/AppIcon.vue'
import PageHeader from '@/components/ui/PageHeader.vue'
import SectionCard from '@/components/ui/SectionCard.vue'
import StatePanel from '@/components/ui/StatePanel.vue'
import StatusBadge from '@/components/ui/StatusBadge.vue'
import { api } from '@/api/client'
import { modelLabel } from '@/utils/demo'

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
    if (!classId.value) classId.value = classList[0]?.id ?? ''
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
  } catch (err) {
    error.value = err.message
    await load()
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
      title="课堂"
      description="从预置实验开一个班级共享演示：单步切换时钟、复位、隐藏或揭示下一状态，并把投屏页投给全班。"
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
        <SectionCard title="开一节演示">
          <div class="picker">
            <div class="field">
              <label for="class_id">班级</label>
              <select id="class_id" v-model="classId" @change="onClassChange">
                <option v-for="item in classes" :key="item.id" :value="item.id">
                  {{ item.name }}
                </option>
              </select>
            </div>
            <div class="field">
              <label for="experiment_id">预置实验</label>
              <select id="experiment_id" v-model="experimentId">
                <option v-for="item in experiments" :key="item.id" :value="item.id">
                  {{ modelLabel(item.simulator_type) }} · {{ item.title }}
                </option>
              </select>
            </div>
            <button class="button button--primary" type="button" :disabled="busy || !experimentId" @click="startDemo">
              <AppIcon name="clock" :size="17" /> 开始演示
            </button>
          </div>
          <p v-if="experiments.length === 0" class="hint">
            还没有实验定义。可先执行 <code>flask --app app:create_app seed-experiments</code> 建立四个预置实验。
          </p>
          <p v-if="activeDemo" class="hint">
            该班级已有进行中的演示；要换实验请先在控制台结束它。
          </p>
          <p v-if="error" class="error" role="alert">{{ error }}</p>
        </SectionCard>

        <SectionCard title="本班演示">
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
