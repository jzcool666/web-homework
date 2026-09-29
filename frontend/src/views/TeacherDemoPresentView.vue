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
import DemoStatePanel from '@/components/demo/DemoStatePanel.vue'
import DemoWaveform from '@/components/demo/DemoWaveform.vue'
import StatePanel from '@/components/ui/StatePanel.vue'
import StatusBadge from '@/components/ui/StatusBadge.vue'
import { api } from '@/api/client'
import { formatInputs, modelLabel, risingCount } from '@/utils/demo'

const POLL_MS = 3000

const route = useRoute()
const demo = ref(null)
const loadError = ref(null)
const state = ref('loading')
const connected = ref(true)
const lastSync = ref('')

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

onMounted(() => {
  refresh()
  startPolling()
  document.addEventListener('visibilitychange', onVisibilityChange)
})

onBeforeUnmount(() => {
  stopPolling()
  document.removeEventListener('visibilitychange', onVisibilityChange)
})
</script>

<template>
  <div class="present">
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
        </div>
      </header>

      <p class="present__inputs">
        输入：
        <strong>{{ formatInputs(demo.state.inputs, simulatorType) }}</strong>
      </p>

      <DemoStatePanel
        class="present__state"
        :state="demo.state"
        :next-q="demo.next_q"
        :reveal-next="demo.reveal_next"
        :simulator-type="simulatorType"
        large
      />

      <section class="present__block">
        <h2>时序波形</h2>
        <DemoWaveform :history="demo.history" :simulator-type="simulatorType" />
      </section>

      <section class="present__block">
        <h2>状态表（已执行 {{ risingCount(demo.history) }} 个有效上升沿）</h2>
        <DemoHistoryTable :history="demo.history" :simulator-type="simulatorType" :limit="10" />
      </section>

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
  max-width: 72rem;
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
  margin-bottom: var(--space-5);
}

.present__block {
  margin-bottom: var(--space-5);
}

.present__block h2 {
  font-size: var(--font-size-lg);
  margin-bottom: var(--space-2);
}

.present__foot {
  color: var(--color-text-secondary);
  font-size: var(--font-size-sm);
}
</style>
