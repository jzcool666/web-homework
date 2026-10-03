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
import DemoVisualStage from '@/components/demo/DemoVisualStage.vue'
import DemoWaveform from '@/components/demo/DemoWaveform.vue'
import PageHeader from '@/components/ui/PageHeader.vue'
import SectionCard from '@/components/ui/SectionCard.vue'
import StatePanel from '@/components/ui/StatePanel.vue'
import StatusBadge from '@/components/ui/StatusBadge.vue'
import { api } from '@/api/client'
import {
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

// Advance one effective edge, serially using each server acknowledgement's version.
// If CLK is already high, first return it low. Never calculate Q in the browser.
async function stepForward() {
  if (pending.value || !demo.value?.active) return
  pending.value = true
  error.value = null
  try {
    const events = demo.value.state.clock ? 2 : 1
    for (let index = 0; index < events; index += 1) {
      demo.value = await api.post(`/demo-sessions/${demo.value.id}/actions`, {
        expected_version: demo.value.version,
        event: { op: 'toggle_clock' },
      })
    }
  } catch (err) {
    error.value = err.message
    await load()
  } finally {
    pending.value = false
  }
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
      description="先设置输入，再前进一拍。看数据如何被记住、计数或移位。"
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
      <div class="demo-meta">
        <div class="meta">
          <StatusBadge :tone="demo.active ? 'success' : 'neutral'">
            {{ demo.active ? '进行中' : '已结束' }}
          </StatusBadge>
          <span>{{ modelLabel(simulatorType) }}</span>
          <span>{{ className }}</span>
          <span>版本 {{ demo.version }}</span>
          <span>已执行 {{ risingCount(demo.history) }} 个有效上升沿</span>
        </div>
        <p v-if="!demo.active" class="hint">
          演示已结束，不能再发送动作。可在「课堂」页为同一班级重新开一个演示。
        </p>
      </div>

      <p v-if="error" class="error" role="alert">{{ error }}</p>

      <DemoVisualStage
          :state="demo.state"
          :history="demo.history"
          :config="demo.experiment?.config"
          :next-q="demo.next_q"
          :reveal-next="demo.reveal_next"
          :simulator-type="simulatorType"
          interactive
          :disabled="pending || !demo.active"
          @input="toggleInput"
          @clock="toggleClock"
          @step="stepForward"
      />

      <div class="lesson-toolbar">
        <div class="lesson-toolbar__tools">
          <button class="button button--secondary" type="button" :disabled="pending" @click="toggleReveal">
            {{ demo.reveal_next ? '隐藏下一状态' : '揭示下一状态' }}
          </button>
          <button class="button button--secondary" type="button" :disabled="pending || !demo.active" @click="resetView">复位到初态（清空历史）</button>
          <button class="button button--secondary" type="button" :disabled="pending || !demo.active" @click="closeDemo">结束演示</button>
        </div>
        <p class="hint">先隐藏下一状态，请同学预测；再揭示或前进一拍验证。RESET 是同步复位输入；「复位到初态」会重新开始本次演示。</p>
      </div>

      <SectionCard title="时序波形">
        <DemoWaveform :history="demo.history" :simulator-type="simulatorType" />
      </SectionCard>

      <details class="lesson-details"><summary>展开事件历史 · {{ demo.history.length }} 次操作</summary>
        <DemoHistoryTable :history="demo.history" :simulator-type="simulatorType" />
      </details>

      <details class="lesson-details"><summary>查看实验步骤</summary>
        <pre class="steps">{{ demo.experiment?.steps_md ?? '（无步骤说明）' }}</pre>
      </details>
    </template>
  </div>
</template>

<style scoped>
.demo-page { width: 100%; }
.demo-page .section-card { margin-bottom: var(--space-4); }
.demo-meta { margin-bottom: 18px; padding: 0 4px; }.demo-meta .meta { gap: 12px; font-size: .74rem; }.demo-meta .hint { font-size: .75rem; color: var(--color-text-secondary); }
.meta { display: flex; align-items: center; gap: var(--space-3); flex-wrap: wrap; font-size: var(--font-size-sm); color: var(--color-text-secondary); }
.lesson-toolbar { margin: 16px 0 22px; padding: 0 4px; }.lesson-toolbar__tools { display: flex; gap: 10px; flex-wrap: wrap; }.lesson-toolbar .hint { font-size: .73rem; line-height: 1.8; margin: 12px 0 0; color: var(--color-text-secondary); }
.lesson-details { background: white; border: 1px solid var(--color-border); border-radius: 12px; padding: 16px; margin-bottom: 12px; }.lesson-details summary { cursor: pointer; font-size: .8rem; font-weight: 650; color: #6f83a5; }.lesson-details[open] summary { margin-bottom: 16px; }
.error { color: var(--color-danger); }
.steps { margin: 0; white-space: pre-wrap; font: inherit; font-size: var(--font-size-sm); color: var(--color-text-primary); }
</style>
