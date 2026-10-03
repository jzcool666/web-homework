<script setup>
import { computed, onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { api } from '@/api/client'
import { useAuthStore } from '@/stores/auth'
import { labStatus, modeLabel } from '@/utils/lab'
import PageHeader from '@/components/ui/PageHeader.vue'
import SectionCard from '@/components/ui/SectionCard.vue'
import StatePanel from '@/components/ui/StatePanel.vue'
const auth = useAuthStore(); const teacher = computed(() => auth.user?.role === 'teacher')
const classes = ref([]); const classId = ref(''); const taskId = ref(''); const tasks = ref([]); const rows = ref([]); const summary = ref([]); const page = ref(1); const mode = ref(''); const status = ref(''); const error = ref(''); const busy = ref(false)
let generation = 0
async function load(reset = false) {
  if (reset) page.value = 1
  const current = ++generation; busy.value = true; error.value = ''
  try {
    const query = new URLSearchParams({ page: String(page.value), page_size: '100' })
    if (teacher.value) query.set('class_id', String(classId.value))
    if (mode.value) query.set('mode', mode.value)
    if (status.value) query.set('status', status.value)
    if (taskId.value) query.set('task_id', String(taskId.value))
    const records = await api.get(`/lab-attempts?${query}`)
    const stats = teacher.value ? await api.get(`/analytics/labs?class_id=${classId.value}${taskId.value ? `&task_id=${taskId.value}` : ''}`) : null
    if (current === generation) { rows.value = records; summary.value = stats?.tasks ?? [] }
  } catch (err) { if (current === generation) error.value = err.message } finally { if (current === generation) busy.value = false }
}
async function init() {
  try {
    classes.value = await api.get('/classes?page_size=100'); classId.value = classes.value[0]?.id ?? ''
    if (classes.value.some(c => c.active)) tasks.value = await api.get('/lab-tasks?page_size=100')
    if (!teacher.value || classId.value) await load()
  } catch (err) { error.value = err.message }
}
const title = id => tasks.value.find(item => item.id === id)?.title ?? `任务${id}`
onMounted(init)
</script>

<template>
  <div class="lab-records">
    <PageHeader :title="teacher ? '实验记录与统计' : '我的实验记录'" description="实验箱接线与Logisim文件分别统计，系统故障不计入得分或通过率。">
      <template #actions><RouterLink class="button" :to="{ name: teacher ? 'teacher-labs' : 'student-labs' }">返回实验任务</RouterLink></template>
    </PageHeader>
    <SectionCard title="筛选记录">
      <div class="filters">
        <label v-if="teacher">班级<select v-model="classId" @change="load(true)"><option v-for="item in classes" :key="item.id" :value="item.id">{{ item.name }}</option></select></label>
        <label>任务<select v-model="taskId" @change="load(true)"><option value="">全部</option><option v-for="item in tasks" :key="item.id" :value="item.id">{{ item.title }}</option></select></label>
        <label>方式<select v-model="mode" @change="load(true)"><option value="">全部</option><option value="wiring">实验箱接线</option><option value="circ">Logisim文件</option></select></label>
        <label>状态<select v-model="status" @change="load(true)"><option value="">全部</option><option v-for="(label, value) in labStatus" :key="value" :value="value">{{ label }}</option></select></label>
        <button class="button" :disabled="busy" @click="load()">刷新</button>
      </div>
      <p v-if="error" class="error" role="alert">{{ error }}</p>
    </SectionCard>
    <SectionCard v-if="teacher && summary.length" title="本班实验汇总">
      <p class="hint">只计本班当前有效在册学生。参与和通过人数去重，任一次通过即计通过；尝试数只计已完成测评。无参与的通过率显示“—”。</p>
      <div class="table-scroll"><table><thead><tr><th>任务</th><th>方式</th><th>参与／通过</th><th>完成尝试</th><th>通过率</th><th>等待／运行／故障</th></tr></thead><tbody><tr v-for="item in summary" :key="`${item.task_id}-${item.mode}`"><td>{{ title(item.task_id) }}</td><td>{{ modeLabel(item.mode) }}</td><td>{{ item.participant_count }} / {{ item.passed_student_count }}</td><td>{{ item.attempt_count }}</td><td>{{ item.pass_rate === null ? '—' : `${(item.pass_rate * 100).toFixed(1)}%` }}</td><td>{{ item.queued_count }} / {{ item.running_count }} / {{ item.error_count }}</td></tr></tbody></table></div>
    </SectionCard>
    <SectionCard title="实验记录">
      <StatePanel v-if="busy" kind="loading" title="正在读取记录" />
      <StatePanel v-else-if="!rows.length" title="没有符合条件的记录" />
      <div v-else class="table-scroll"><table><thead><tr><th v-if="teacher">学生</th><th>任务／方式</th><th>状态</th><th>成绩</th><th>提交时间</th><th>详情</th></tr></thead><tbody><tr v-for="item in rows" :key="item.id"><td v-if="teacher">{{ item.student_display_name }}<br />{{ item.student_no }}</td><td>{{ item.task_code }}<br />{{ modeLabel(item.mode) }}</td><td>{{ labStatus[item.status] }}</td><td>{{ item.score === null ? '—' : `${item.score}分` }}</td><td>{{ item.created_at }}</td><td><RouterLink class="button" :to="{ name: 'lab-attempt', params: { id: item.id } }">查看{{ item.mode === 'wiring' ? '与回放' : '结果' }}</RouterLink></td></tr></tbody></table></div>
      <div class="filters"><button class="button" :disabled="busy || page <= 1" @click="page--; load()">上一页</button><span>第 {{ page }} 页</span><button class="button" :disabled="busy || rows.length < 100" @click="page++; load()">下一页</button></div>
    </SectionCard>
  </div>
</template>

<style scoped>
.lab-records { display: grid; grid-template-columns: minmax(0, 1fr); gap: 18px; } .filters { display: flex; flex-wrap: wrap; align-items: end; gap: 12px; } select { display: block; max-width: 240px; } table { width: 100%; min-width: 700px; } .table-scroll { overflow: auto; margin-bottom: 16px; } th,td { text-align: left; padding: 10px; border-bottom: 1px solid #e2e8f0; } .error { color: #b42318; } .hint { line-height: 1.7; }
</style>
