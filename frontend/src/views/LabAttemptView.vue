<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { RouterLink, useRoute } from 'vue-router'
import { api } from '@/api/client'
import { useAuthStore } from '@/stores/auth'
import { labStatus, modeLabel, outputText } from '@/utils/lab'
import LabBoard from '@/components/LabBoard.vue'
import PageHeader from '@/components/ui/PageHeader.vue'
import SectionCard from '@/components/ui/SectionCard.vue'
import StatePanel from '@/components/ui/StatePanel.vue'
const route = useRoute(); const auth = useAuthStore()
const row = ref(null); const replay = ref(null); const at = ref(0); const max = ref(0); const error = ref(''); const refreshing = ref(false)
const waiting = computed(() => row.value && ['queued', 'running'].includes(row.value.status))
let timer; let requestId = 0; let disposed = false
async function load() {
  refreshing.value = true
  try {
    const result = await api.get(`/lab-attempts/${route.params.id}`)
    if (disposed) return
    row.value = result
    if (!replay.value && result.session_snapshot) { replay.value = result.session_snapshot; max.value = result.session_snapshot.events.length; at.value = max.value }
    error.value = ''
  } catch (err) { error.value = err.message } finally { refreshing.value = false }
}
async function seek() {
  const id = ++requestId
  try {
    const result = await api.get(`/lab-attempts/${route.params.id}?at_seq=${at.value}`)
    if (id === requestId && !disposed) replay.value = result.session_snapshot
  } catch (err) { if (id === requestId) error.value = err.message }
}
onMounted(async () => { await load(); timer = setInterval(() => { if (waiting.value && !document.hidden && !refreshing.value) load() }, 2000) })
onBeforeUnmount(() => { disposed = true; clearInterval(timer) })
</script>

<template>
  <div class="lab-result">
    <PageHeader :title="row ? `${row.task.title} · ${modeLabel(row.mode)}` : '实验结果'" description="成绩、任务版本和提交时的实验过程均作为独立记录保留。">
      <template #actions><RouterLink class="button" :to="{ name: auth.user?.role === 'teacher' ? 'teacher-lab-records' : 'student-lab-records' }">返回实验记录</RouterLink></template>
    </PageHeader>
    <p v-if="error" class="error" role="alert">{{ error }}</p>
    <StatePanel v-if="!row" kind="loading" title="正在读取实验结果" />
    <template v-else>
      <SectionCard :title="labStatus[row.status]">
        <p v-if="waiting">提交已接收，页面会自动刷新。关闭页面后可从实验记录继续查看。</p>
        <p v-else-if="row.status === 'done'" class="grade">{{ row.passed ? '全部通过' : '尚未通过' }} · {{ row.score }} 分 · 通过 {{ row.passed_checkpoints }}/{{ row.total_checkpoints }} 个计分点</p>
        <p v-else class="error">{{ row.error?.message || '测评服务故障，请重新提交' }}。本次没有成绩。</p>
        <p v-if="auth.user?.role === 'teacher'">{{ row.student_display_name }} · {{ row.student_no }}</p>
        <p class="hint">提交 {{ row.created_at }} · 任务版本 {{ row.task_version }} · 测试集 {{ row.suite_version }} · 引擎 {{ row.engine_version }}</p>
        <button class="button" :disabled="refreshing" @click="load">刷新状态</button>
        <RouterLink v-if="row.mode === 'circ' && auth.user?.role === 'student'" class="button" :to="{ name: 'lab-upload', params: { id: row.task_id }, query: { class_id: row.class_id } }">重新上传</RouterLink>
        <RouterLink v-if="row.mode === 'wiring' && auth.user?.role === 'student'" class="button" :to="{ name: 'lab-session', params: { id: row.session_id } }">继续修改接线</RouterLink>
      </SectionCard>
      <SectionCard v-if="row.first_failure" title="首个出错计分点">
        <p>第 {{ row.first_failure.checkpoint }} 个计分点：{{ row.first_failure.reason }}</p>
        <p>输入：{{ outputText(row.first_failure.inputs) }}</p><p>实际：{{ outputText(row.first_failure.actual) }}</p><p>期望：{{ outputText(row.first_failure.expected) }}</p>
      </SectionCard>
      <SectionCard v-if="row.file" title="提交文件">
        <p>{{ row.file.original_name }} · {{ row.file.size_bytes }} 字节</p><p class="hash">SHA-256：{{ row.file.sha256 }}</p>
        <a class="button" :href="`/api/v1/lab-attempts/${row.id}/file`">下载原始电路文件</a>
      </SectionCard>
      <SectionCard v-if="replay" title="提交时的过程回放">
        <div class="replay-controls">
          <button class="button" :disabled="at <= 0" @click="at--; seek()">上一步</button>
          <label>步骤 {{ at }}/{{ max }} <input v-model.number="at" type="range" :min="0" :max="max" @input="seek" /></label>
          <button class="button" :disabled="at >= max" @click="at++; seek()">下一步</button>
        </div>
        <p>{{ at === 0 ? '实验初始状态' : `${replay.events.at(-1)?.op || ''} · ${replay.events.at(-1)?.received_at || ''}` }} · {{ outputText(replay.state.outputs) }}</p>
        <LabBoard :task="row.task" :board="replay.board" :state="replay.state" readonly />
        <p class="hint">回放读取提交时的快照，之后修改接线不会改变此记录。</p>
        <details><summary>操作明细</summary><ol><li v-for="event in row.session_snapshot.events" :key="event.seq">{{ event.received_at }} · {{ event.op }} · {{ JSON.stringify(event.payload) }}</li></ol></details>
      </SectionCard>
    </template>
  </div>
</template>

<style scoped>
.lab-result { display: grid; grid-template-columns: minmax(0, 1fr); gap: 18px; } .error { color: #b42318; } .grade { font-size: 20px; font-weight: 700; } .hint { line-height: 1.7; } .hash,li { overflow-wrap: anywhere; } .replay-controls { display: flex; flex-wrap: wrap; gap: 12px; align-items: center; } .replay-controls input { display: block; min-width: 190px; } .button { margin-right: 8px; } li { margin: 8px 0; }
</style>
