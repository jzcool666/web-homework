<script setup>
/**
 * 学生只读演示（SPEC-012 E053、ADR-006）。
 *
 * 约 3 秒轮询一次服务器状态，页面隐藏时停止、回到前台立即刷新；连续失败显示
 * 断线并保留最后版本与同步时间。学生没有任何修改入口，预测未揭示时服务器
 * 根本不会返回下一状态。
 */
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { RouterLink, useRoute } from 'vue-router'

import DemoHistoryTable from '@/components/demo/DemoHistoryTable.vue'
import DemoStatePanel from '@/components/demo/DemoStatePanel.vue'
import DemoWaveform from '@/components/demo/DemoWaveform.vue'
import PageHeader from '@/components/ui/PageHeader.vue'
import SectionCard from '@/components/ui/SectionCard.vue'
import StatePanel from '@/components/ui/StatePanel.vue'
import StatusBadge from '@/components/ui/StatusBadge.vue'
import { api } from '@/api/client'
import { modelLabel, risingCount } from '@/utils/demo'

const POLL_MS = 3000

const route = useRoute()
const demo = ref(null)
const state = ref('loading')
const loadError = ref('')
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
  <div class="student-demo">
    <PageHeader
      :eyebrow="`演示 #${demoId}`"
      :title="demo?.experiment?.title ?? '课堂演示'"
      description="只读观看：状态由教师操作、服务器重算后同步到这里。"
    >
      <template #actions>
        <RouterLink class="button button--secondary" :to="{ name: 'student-demos' }">返回我的课堂</RouterLink>
      </template>
    </PageHeader>

    <StatePanel v-if="state === 'loading'" kind="loading" title="正在读取演示状态" />
    <StatePanel v-else-if="state === 'error'" kind="error" title="演示无法读取" :description="loadError" />

    <template v-else>
      <p v-if="!connected" class="offline" role="alert">
        与服务器连接中断，显示的是最后同步的状态（版本 {{ demo.version }}，{{ lastSync }}）。恢复后会自动刷新。
      </p>

      <SectionCard title="演示信息">
        <div class="meta">
          <StatusBadge :tone="demo.active ? 'success' : 'neutral'">
            {{ demo.active ? '进行中' : '已结束' }}
          </StatusBadge>
          <span>{{ modelLabel(simulatorType) }}</span>
          <span>版本 {{ demo.version }}</span>
          <span>已执行 {{ risingCount(demo.history) }} 个有效上升沿</span>
          <span v-if="connected">同步于 {{ lastSync }}</span>
        </div>
        <p v-if="!demo.active" class="hint">本次演示已结束，下面保留的是最后一次状态。</p>
      </SectionCard>

      <SectionCard title="当前状态">
        <DemoStatePanel
          :state="demo.state"
          :next-q="demo.next_q"
          :reveal-next="demo.reveal_next"
          :simulator-type="simulatorType"
        />
      </SectionCard>

      <SectionCard title="时序波形">
        <DemoWaveform :history="demo.history" :simulator-type="simulatorType" />
      </SectionCard>

      <SectionCard title="状态表">
        <DemoHistoryTable :history="demo.history" :simulator-type="simulatorType" />
      </SectionCard>

      <p class="hint">离散逻辑演示，不包含传播延迟和亚稳态。</p>
    </template>
  </div>
</template>

<style scoped>
.student-demo { width: 100%; }
.student-demo .section-card { margin-bottom: var(--space-4); }
.meta { display: flex; align-items: center; gap: var(--space-3); flex-wrap: wrap; font-size: var(--font-size-sm); color: var(--color-text-secondary); }
.offline { padding: var(--space-3); border: 1px solid var(--color-danger); border-radius: var(--radius-sm); background: color-mix(in srgb, var(--color-danger) 6%, white); color: var(--color-danger); font-size: var(--font-size-sm); margin-bottom: var(--space-3); }
.hint { color: var(--color-text-secondary); font-size: var(--font-size-sm); }
</style>
