<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import { api, ApiError } from '@/api/client'
import { useAuthStore } from '@/stores/auth'
import { boardLayout, inverseWireAction, newLabKey, outputText } from '@/utils/lab'
import LabBoard from '@/components/LabBoard.vue'
import PageHeader from '@/components/ui/PageHeader.vue'
import SectionCard from '@/components/ui/SectionCard.vue'
import StatePanel from '@/components/ui/StatePanel.vue'
const route = useRoute(); const router = useRouter(); const auth = useAuthStore()
const row = ref(null); const error = ref(''); const loading = ref(true); const busy = ref(false); const selected = ref(''); const from = ref(''); const to = ref('')
const pending = ref(null); const pendingGrade = ref(null); const undoStack = ref([]); const redoStack = ref([])
const present = computed(() => route.query.present === '1')
const readonly = computed(() => present.value || row.value?.owner_id !== auth.user?.id)
const endpoints = computed(() => row.value ? boardLayout(row.value.task).endpoints : [])
const switches = computed(() => row.value?.task.board.terminals.filter(item => item.kind === 'switch') ?? [])
const edited = computed(() => busy.value || Boolean(pending.value) || readonly.value)
let timer
async function load() {
  try { row.value = await api.get(`/lab-sessions/${route.params.id}`) } catch (err) { error.value = err.message } finally { loading.value = false }
}
async function sendPending() {
  if (busy.value || !pending.value) return
  busy.value = true; error.value = ''
  const job = pending.value
  try {
    row.value = await api.post(`/lab-sessions/${route.params.id}/actions`, job.body)
    if (job.kind === 'undo') { undoStack.value.pop(); redoStack.value.push(job.opposite) }
    else if (job.kind === 'redo') { redoStack.value.pop(); undoStack.value.push(job.opposite) }
    else if (job.inverse) { undoStack.value.push(job.inverse); redoStack.value = [] }
    if (job.body.op === 'reset') { undoStack.value = []; redoStack.value = [] }
    pending.value = null; selected.value = ''; pendingGrade.value = null
  } catch (err) {
    error.value = err.message
    if (err instanceof ApiError) {
      pending.value = null
      if (err.status === 409) { await load(); undoStack.value = []; redoStack.value = [] }
    } else error.value = '连接中断，操作是否保存尚未确认。请重试同一操作。'
  } finally { busy.value = false }
}
async function action(op, payload, kind = '', opposite = null) {
  if (edited.value) return
  pending.value = { body: { version: row.value.version, action_key: newLabKey(), op, payload }, kind, opposite, inverse: inverseWireAction(op, payload, row.value.board) }
  await sendPending()
}
async function connect() { if (from.value && to.value && from.value !== to.value) await action('connect', { from: from.value, to: to.value }) }
async function endpoint(id) {
  if (edited.value || row.value.board.power) return
  if (selected.value === id) selected.value = ''
  else if (!selected.value) { selected.value = id; from.value = id }
  else { to.value = id; await connect() }
}
async function remove(id) { if (!row.value.board.power) await action('disconnect', { wire_id: id }) }
async function undo(kind) {
  const stack = kind === 'undo' ? undoStack.value : redoStack.value; const item = stack.at(-1)
  if (!item || row.value.board.power) return
  await action(item.op, item.payload, kind, inverseWireAction(item.op, item.payload, row.value.board))
}
async function submit() {
  if (edited.value || row.value.kind !== 'practice') return
  busy.value = true; error.value = ''
  pendingGrade.value ??= { session_id: row.value.id, session_version: row.value.version, task_version: row.value.task_version, request_key: newLabKey() }
  try {
    const result = await api.post('/lab-attempts/wiring', pendingGrade.value)
    pendingGrade.value = null; await router.push({ name: 'lab-attempt', params: { id: result.id } })
  } catch (err) {
    error.value = err.message
    if (err instanceof ApiError) pendingGrade.value = null
    if (err.status === 409) await load()
  } finally { busy.value = false }
}
watch(() => route.params.id, async () => { loading.value = true; pending.value = null; undoStack.value = []; redoStack.value = []; await load() })
onMounted(async () => { await load(); timer = setInterval(() => { if (present.value && !document.hidden) load() }, 2000) })
onBeforeUnmount(() => clearInterval(timer))
</script>

<template>
  <div class="lab-session">
    <PageHeader :title="row?.task.title || '实验箱接线'" :description="row?.task.instructions_md || ''">
      <template v-if="!present" #actions>
        <RouterLink class="button" :to="{ name: auth.user?.role === 'teacher' ? 'teacher-labs' : 'student-labs' }">返回实验任务</RouterLink>
        <RouterLink v-if="row?.kind === 'demo'" class="button" :to="{ name: 'lab-session', params: { id: row.id }, query: { present: '1' } }" target="_blank">打开投屏</RouterLink>
      </template>
    </PageHeader>
    <StatePanel v-if="loading" kind="loading" title="正在恢复实验过程" />
    <StatePanel v-else-if="!row" kind="error" title="实验无法读取" :description="error" />
    <template v-else>
      <p v-if="error" class="error" role="alert">{{ error }}</p>
      <SectionCard v-if="!readonly" title="实验操作">
        <div class="lab-controls">
          <button class="button" :disabled="edited" @click="action('power', { on: !row.board.power })">{{ row.board.power ? '关闭电源' : '开启电源' }}</button>
          <button class="button" :disabled="edited || !row.board.power" @click="action('set_clock', { value: row.board.clock ? 0 : 1 })">时钟 {{ row.board.clock }} → {{ row.board.clock ? 0 : 1 }}</button>
          <button class="button" :disabled="edited || row.board.power || !undoStack.length" @click="undo('undo')">撤销连线</button>
          <button class="button" :disabled="edited || row.board.power || !redoStack.length" @click="undo('redo')">重做连线</button>
          <button class="button" :disabled="edited" @click="action('reset', {})">清空实验箱</button>
          <button v-if="row.kind === 'practice'" class="button button--primary" :disabled="edited" @click="submit">{{ pendingGrade ? '重试提交' : '提交接线测评' }}</button>
          <button v-if="pending" class="button button--primary" :disabled="busy" @click="sendPending">重试保存操作</button>
        </div>
        <div class="lab-controls switches">
          <button v-for="item in switches" :key="item.id" class="button" :aria-pressed="Boolean(row.board.switches[item.id])" :disabled="edited" @click="action('set_switch', { terminal_id: item.id, value: row.board.switches[item.id] ? 0 : 1 })">{{ item.label }} = {{ row.board.switches[item.id] || 0 }}</button>
        </div>
        <p class="hint">所有操作自动保存。先关电接线，开电后先清零，再释放清零并切换时钟。导线交叉不表示相连。X：状态未知；Z：未连接／关电。</p>
        <details>
          <summary>按端点名称接线</summary>
          <div class="lab-controls">
            <label>起点<select v-model="from"><option value="">选择端点</option><option v-for="item in endpoints" :key="item.id" :value="item.id">{{ item.label }}</option></select></label>
            <label>终点<select v-model="to"><option value="">选择端点</option><option v-for="item in endpoints" :key="item.id" :value="item.id">{{ item.label }}</option></select></label>
            <button class="button" :disabled="edited || row.board.power || !from || !to || from === to" @click="connect">连接两端点</button>
          </div>
        </details>
      </SectionCard>
      <SectionCard :title="`实验箱 · ${row.board.power ? '已通电' : '已关电'} · ${outputText(row.state.outputs)}`">
        <LabBoard :task="row.task" :board="row.board" :state="row.state" :selected="selected" :readonly="edited || row.board.power" @endpoint="endpoint" @wire="remove" />
        <p v-if="!present" class="hint">已保存 {{ row.saved_at }} · 过程 {{ row.events.length }}/512 步 · {{ row.board.wires.length }}/256 条线</p>
        <ul v-if="row.state.diagnostics.length" class="error"><li v-for="(item, index) in row.state.diagnostics" :key="index">{{ item.message }}：{{ item.endpoints.join('、') }}</li></ul>
      </SectionCard>
      <SectionCard v-if="!present && row.board.wires.length" title="导线列表">
        <div class="wire-list"><div v-for="wire in row.board.wires" :key="wire.id">{{ wire.from }} → {{ wire.to }} <button v-if="!readonly" class="button" :disabled="edited || row.board.power" @click="remove(wire.id)">删除</button></div></div>
      </SectionCard>
    </template>
  </div>
</template>

<style scoped>
.lab-session { display: grid; grid-template-columns: minmax(0, 1fr); gap: 18px; } .lab-controls { display: flex; flex-wrap: wrap; align-items: center; gap: 10px; } .switches { margin-top: 16px; } .error { color: #b42318; overflow-wrap: anywhere; } .hint { line-height: 1.7; } .wire-list { display: grid; gap: 8px; overflow-wrap: anywhere; } select { max-width: 230px; display: block; } details { margin-top: 12px; } details .lab-controls { margin-top: 10px; }
</style>
