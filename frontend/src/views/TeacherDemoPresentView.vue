<script setup>
/**
 * 投屏页（SPEC-012 E053，页面设计第 3 节）。
 *
 * 大字号、高对比，只显示模型、当前状态、下一状态、波形与已执行历史；
 * 没有编辑表单，也不显示任何学生姓名或成绩。约 3 秒轮询一次，
 * 页面隐藏时停止、回到前台立即刷新（ADR-006）。
 */
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { RouterLink, useRoute } from 'vue-router'

import DemoHistoryTable from '@/components/demo/DemoHistoryTable.vue'
import DemoVisualStage from '@/components/demo/DemoVisualStage.vue'
import DemoWaveform from '@/components/demo/DemoWaveform.vue'
import StatePanel from '@/components/ui/StatePanel.vue'
import StatusBadge from '@/components/ui/StatusBadge.vue'
import { api } from '@/api/client'
import { modelLabel, risingCount } from '@/utils/demo'

const POLL_MS = 3000

const route = useRoute()
const demo = ref(null)
const loadError = ref(null)
const state = ref('loading')
const connected = ref(true)
const lastSync = ref('')
const presentRoot = ref(null)
const fullscreen = ref(false)
const fullscreenError = ref('')

const demoId = computed(() => Number(route.params.id))
const simulatorType = computed(() => demo.value?.experiment?.simulator_type ?? 'd')
let timer = null

async function refresh() {
  try {
    demo.value = await api.get(`/demo-sessions/${demoId.value}`)
    state.value = 'ready'
    connected.value = true
    lastSync.value = new Date().toLocaleTimeString('zh-CN', { hour12: false })
  } catch (err) {
    if (state.value !== 'ready') {
      loadError.value = err.message
      state.value = 'error'
      return
    }
    // 已经有内容时只标记断线，保留最后一次同步时间与版本（ADR-006）
    connected.value = false
  }
}

function startPolling() {
  stopPolling()
  timer = setInterval(refresh, POLL_MS)
}

function stopPolling() {
  if (timer !== null) {
    clearInterval(timer)
    timer = null
  }
}

function onVisibilityChange() {
  if (document.hidden) {
    stopPolling()
  } else {
    refresh()
    startPolling()
  }
}

function onFullscreenChange() { fullscreen.value = document.fullscreenElement === presentRoot.value }
async function toggleFullscreen() {
  fullscreenError.value = ''
  try {
    if (document.fullscreenElement) await document.exitFullscreen()
    else await presentRoot.value.requestFullscreen()
  } catch { fullscreenError.value = '当前浏览器无法进入全屏，可使用浏览器的全屏功能。' }
}

onMounted(() => {
  refresh()
  startPolling()
  document.addEventListener('visibilitychange', onVisibilityChange)
  document.addEventListener('fullscreenchange', onFullscreenChange)
})

onBeforeUnmount(() => {
  stopPolling()
  document.removeEventListener('visibilitychange', onVisibilityChange)
  document.removeEventListener('fullscreenchange', onFullscreenChange)
})
</script>

<template>
  <div ref="presentRoot" class="present">
    <StatePanel v-if="state === 'loading'" kind="loading" title="正在读取演示状态" />
    <StatePanel v-else-if="state === 'error'" kind="error" title="演示无法读取" :description="loadError" />

    <template v-else>
      <header class="present__header">
        <div>
          <span class="present__eyebrow">{{ modelLabel(simulatorType) }}</span>
          <h1>{{ demo.experiment?.title }}</h1>
        </div>
        <div class="present__status">
          <StatusBadge :tone="demo.active ? 'success' : 'neutral'">
            {{ demo.active ? '进行中' : '已结束' }}
          </StatusBadge>
          <span v-if="!connected" class="present__offline">连接中断 · 最后同步 {{ lastSync }}</span>
          <span v-else>版本 {{ demo.version }} · 同步于 {{ lastSync }}</span>
          <button class="button button--secondary" type="button" @click="toggleFullscreen">{{ fullscreen ? '退出全屏' : '全屏展示' }}</button>
        </div>
      </header>
      <p v-if="fullscreenError" role="alert">{{ fullscreenError }}</p>

      <DemoVisualStage
        class="present__state"
        :state="demo.state"
        :history="demo.history"
        :config="demo.experiment?.config"
        :next-q="demo.next_q"
        :reveal-next="demo.reveal_next"
        :simulator-type="simulatorType"
        large
      />

      <details class="present__block">
        <summary>展开时序波形</summary>
        <DemoWaveform :history="demo.history" :simulator-type="simulatorType" />
      </details>

      <details class="present__block">
        <summary>展开状态表（已执行 {{ risingCount(demo.history) }} 个有效上升沿）</summary>
        <DemoHistoryTable :history="demo.history" :simulator-type="simulatorType" :limit="10" />
      </details>

      <p class="present__foot">
        离散逻辑演示，不包含传播延迟和亚稳态。
        <RouterLink :to="{ name: 'teacher-demo', params: { id: demoId } }">返回控制台</RouterLink>
      </p>
    </template>
  </div>
</template>

<style scoped>
.present {
  width: 100%;
  max-width: 86rem;
  margin: 0 auto;
}

.present__header {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: var(--space-4);
  flex-wrap: wrap;
  padding-bottom: var(--space-3);
  border-bottom: 2px solid var(--color-border);
}

.present__eyebrow {
  font-size: var(--font-size-sm);
  font-weight: 800;
  letter-spacing: 0.08em;
  color: var(--color-primary);
}

.present h1 {
  font-size: 2.1rem;
  margin: var(--space-1) 0 0;
}

.present__status {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  color: var(--color-text-secondary);
  font-size: var(--font-size-sm);
}

.present__offline {
  color: var(--color-danger);
  font-weight: 700;
}

.present__inputs {
  font-size: 1.35rem;
  margin: var(--space-4) 0 var(--space-3);
  font-family: var(--font-mono);
}

.present__state {
  margin: var(--space-5) 0;
}

.present__block {
  margin-bottom: 12px; border: 1px solid #dfe8f5; border-radius: 12px; padding: 15px 18px; background: #ffffffb0;
}
.present__block summary { cursor: pointer; color: #7187a8; font-size: .85rem; font-weight: 600; }.present__block[open] summary { margin-bottom: 15px; }
.present:fullscreen { max-width: none; width: 100%; height: 100%; overflow-y: auto; padding: 24px 32px; background: #f2f7ff; box-sizing: border-box; }
@media(max-width:600px) { .present h1 { font-size: 1.45rem; }.present__status { gap: 8px; font-size: .68rem; }.present:fullscreen { padding: 18px 12px; } }

.present__block h2 {
  font-size: var(--font-size-lg);
  margin-bottom: var(--space-2);
}

.present__foot {
  color: var(--color-text-secondary);
  font-size: var(--font-size-sm);
}
</style>
