<script setup>
/**
 * 教师演示控制台（SPEC-012 E053/E054）。
 *
 * 每次动作都带 expected_version：服务器从旧状态重算并递增版本，冲突返回 409，
 * 界面刷新后由教师决定是否重试，不自动重放过期请求（ADR-006）。
 * 连续点击会串行等待上一次动作回执，避免用旧版本号发出第二次请求。
 */
import { computed, onMounted, ref } from 'vue'
import { RouterLink, useRoute } from 'vue-router'

import AppIcon from '@/components/ui/AppIcon.vue'
import DemoHistoryTable from '@/components/demo/DemoHistoryTable.vue'
import DemoStatePanel from '@/components/demo/DemoStatePanel.vue'
import DemoWaveform from '@/components/demo/DemoWaveform.vue'
import PageHeader from '@/components/ui/PageHeader.vue'
import SectionCard from '@/components/ui/SectionCard.vue'
import StatePanel from '@/components/ui/StatePanel.vue'
import StatusBadge from '@/components/ui/StatusBadge.vue'
import { api } from '@/api/client'
import {
  INPUT_HINTS,
  inputLabel,
  inputsFor,
  modelLabel,
  risingCount,
} from '@/utils/demo'

const route = useRoute()
const demo = ref(null)
const classes = ref([])
const error = ref(null)
const loadError = ref(null)
const state = ref('loading')
const pending = ref(false)

const demoId = computed(() => Number(route.params.id))
const simulatorType = computed(() => demo.value?.experiment?.simulator_type ?? 'd')
const pins = computed(() => inputsFor(simulatorType.value))
const className = computed(() => {
  const found = classes.value.find((item) => item.id === demo.value?.class_id)
  return found ? found.name : `班级 #${demo.value?.class_id ?? '-'}`
})

async function load() {
  state.value = 'loading'
  try {
    const [detail, classList] = await Promise.all([
      api.get(`/demo-sessions/${demoId.value}`),
      api.get('/classes?page_size=100'),
    ])
    demo.value = detail
    classes.value = classList
    state.value = 'ready'
  } catch (err) {
    loadError.value = err.message
    state.value = 'error'
  }
}

/** 串行发送动作：失败或冲突时以服务器状态为准，不自动重试。 */
async function act(payload) {
  if (pending.value || !demo.value) return
  pending.value = true
  error.value = null
  try {
    demo.value = await api.post(`/demo-sessions/${demo.value.id}/actions`, {
      expected_version: demo.value.version,
      ...payload,
    })
  } catch (err) {
    error.value = err.message
    await load()
  } finally {
    pending.value = false
  }
}

function toggleInput(pin) {
  const current = demo.value?.state?.inputs?.[pin] ?? 0
  act({ event: { op: 'set', inputs: { [pin]: current ? 0 : 1 } } })
}

function toggleClock() {
  act({ event: { op: 'toggle_clock' } })
}

function resetView() {
  act({ event: { op: 'reset_view' } })
}

function toggleReveal() {
  act({ action: { op: 'set_reveal', value: !demo.value.reveal_next } })
}

function closeDemo() {
  act({ action: { op: 'close' } })
}

onMounted(load)
</script>

<template>
  <div class="demo-page">
    <PageHeader
      :eyebrow="`演示 #${demoId}`"
      :title="demo?.experiment?.title ?? '课堂演示'"
      description="服务器从旧状态重算每一步；只有 0→1 的有效上升沿会更新 Q。"
    >
      <template #actions>
        <RouterLink class="button button--primary" :to="{ name: 'teacher-demo-present', params: { id: demoId } }">
          <AppIcon name="clock" :size="17" /> 打开投屏页
        </RouterLink>
        <RouterLink class="button button--secondary" :to="{ name: 'teacher-classroom' }">
          返回课堂
        </RouterLink>
      </template>
    </PageHeader>

    <StatePanel v-if="state === 'loading'" kind="loading" title="正在读取演示状态" />
    <StatePanel v-else-if="state === 'error'" kind="error" title="演示无法读取" :description="loadError" />

    <template v-else>
      <SectionCard title="演示信息">
        <div class="meta">
          <StatusBadge :tone="demo.active ? 'success' : 'neutral'">
            {{ demo.active ? '进行中' : '已结束' }}
          </StatusBadge>
          <span>{{ modelLabel(simulatorType) }}</span>
          <span>{{ className }}</span>
          <span>版本 {{ demo.version }}</span>
          <span>最后更新 {{ demo.last_updated }}</span>
          <span>已执行 {{ risingCount(demo.history) }} 个有效上升沿</span>
        </div>
        <p v-if="!demo.active" class="hint">
          演示已结束，不能再发送动作。可在「课堂」页为同一班级重新开一个演示。
        </p>
      </SectionCard>

      <p v-if="error" class="error" role="alert">{{ error }}</p>

      <SectionCard title="当前状态">
        <DemoStatePanel
          :state="demo.state"
          :next-q="demo.next_q"
          :reveal-next="demo.reveal_next"
          :simulator-type="simulatorType"
        />
      </SectionCard>

      <SectionCard title="控制">
        <div class="controls">
          <div class="control-group">
            <span class="control-group__title">输入</span>
            <button
              v-for="pin in pins"
              :key="pin"
              class="button button--secondary input-toggle"
              type="button"
              :disabled="pending || !demo.active"
              @click="toggleInput(pin)"
            >
              <span class="mono">{{ inputLabel(pin) }}</span>
              <span class="value" :class="{ 'value--on': demo.state.inputs[pin] }">
                {{ demo.state.inputs[pin] ?? 0 }}
              </span>
              <small v-if="INPUT_HINTS[pin]">{{ INPUT_HINTS[pin] }}</small>
            </button>
          </div>

          <div class="control-group">
            <span class="control-group__title">时钟与复位</span>
            <button class="button button--primary" type="button" :disabled="pending || !demo.active" @click="toggleClock">
              切换时钟半周期（{{ demo.state.clock ? '将产生下降沿' : '将产生有效上升沿' }}）
            </button>
            <button class="button button--secondary" type="button" :disabled="pending || !demo.active" @click="resetView">
              复位到初态（清空历史）
            </button>
          </div>

          <div class="control-group">
            <span class="control-group__title">预测模式</span>
            <button class="button button--secondary" type="button" :disabled="pending" @click="toggleReveal">
              {{ demo.reveal_next ? '隐藏下一状态' : '揭示下一状态' }}
            </button>
            <small class="hint">
              隐藏时服务器不返回下一状态，学生端同样取不到。
            </small>
          </div>

          <div class="control-group">
            <span class="control-group__title">演示</span>
            <button class="button button--secondary" type="button" :disabled="pending || !demo.active" @click="closeDemo">
              结束演示
            </button>
          </div>
        </div>
        <p class="hint">
          「复位到初态」是重新开始演示，与同步复位引脚不同；同步复位由输入的 RESET 控制，只在有效上升沿生效。
        </p>
      </SectionCard>

      <SectionCard title="时序波形">
        <DemoWaveform :history="demo.history" :simulator-type="simulatorType" />
      </SectionCard>

      <SectionCard title="事件历史">
        <DemoHistoryTable :history="demo.history" :simulator-type="simulatorType" />
      </SectionCard>

      <SectionCard title="实验步骤">
        <pre class="steps">{{ demo.experiment?.steps_md ?? '（无步骤说明）' }}</pre>
      </SectionCard>
    </template>
  </div>
</template>

<style scoped>
.demo-page { width: 100%; }
.demo-page .section-card { margin-bottom: var(--space-4); }
.meta { display: flex; align-items: center; gap: var(--space-3); flex-wrap: wrap; font-size: var(--font-size-sm); color: var(--color-text-secondary); }
.controls { display: grid; grid-template-columns: repeat(auto-fit, minmax(16rem, 1fr)); gap: var(--space-4); }
.control-group { display: grid; gap: var(--space-2); align-content: start; }
.control-group__title { font-size: var(--font-size-xs); font-weight: 800; letter-spacing: .06em; color: var(--color-text-secondary); }
.input-toggle { display: flex; align-items: center; gap: var(--space-2); justify-content: space-between; }
.input-toggle .mono { font-family: var(--font-mono); font-weight: 700; }
.input-toggle .value { display: inline-grid; place-items: center; min-width: 1.7rem; height: 1.7rem; border-radius: var(--radius-sm); background: var(--color-bg-page); font-family: var(--font-mono); }
.input-toggle .value--on { background: var(--color-primary); color: #fff; }
.input-toggle small { color: var(--color-text-secondary); font-size: var(--font-size-xs); }
.error { color: var(--color-danger); }
.steps { margin: 0; white-space: pre-wrap; font: inherit; font-size: var(--font-size-sm); color: var(--color-text-primary); }
</style>
