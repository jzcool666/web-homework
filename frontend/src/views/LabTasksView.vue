<script setup>
import { computed, onMounted, ref } from 'vue'
import { RouterLink, useRouter } from 'vue-router'
import { api } from '@/api/client'
import { useAuthStore } from '@/stores/auth'
import { newLabKey } from '@/utils/lab'
import PageHeader from '@/components/ui/PageHeader.vue'
import SectionCard from '@/components/ui/SectionCard.vue'
import StatePanel from '@/components/ui/StatePanel.vue'
const auth = useAuthStore(); const router = useRouter()
const tasks = ref([]); const classes = ref([]); const classId = ref(''); const error = ref(''); const loading = ref(true); const busy = ref(false)
const teacher = computed(() => auth.user?.role === 'teacher')
async function load() {
  loading.value = true; error.value = ''
  try {
    classes.value = (await api.get('/classes?page_size=100')).filter(item => item.active)
    classId.value = classes.value[0]?.id ?? ''
    if (classId.value) tasks.value = await api.get('/lab-tasks?page_size=100')
  } catch (err) { error.value = err.message } finally { loading.value = false }
}
async function start(task, fresh = false) {
  if (busy.value) return
  busy.value = true; error.value = ''
  const storageKey = `lab-session-${auth.user.id}-${classId.value}-${task.id}-${task.version}`
  try {
    let row = null
    if (!fresh && localStorage.getItem(storageKey)) {
      try { row = await api.get(`/lab-sessions/${localStorage.getItem(storageKey)}`) } catch { localStorage.removeItem(storageKey) }
    }
    if (!row) {
      row = await api.post('/lab-sessions', { task_id: task.id, task_version: task.version, class_id: Number(classId.value), request_key: newLabKey() })
      localStorage.setItem(storageKey, String(row.id))
    }
    await router.push({ name: 'lab-session', params: { id: row.id } })
  } catch (err) { error.value = err.message } finally { busy.value = false }
}
onMounted(load)
</script>

<template>
  <div class="lab-page">
    <PageHeader title="实验箱与电路测评" description="先完成芯片连线、开关和时钟操作，也可以在桌面 Logisim 中设计电路并上传测评。">
      <template #actions><RouterLink class="button" :to="{ name: teacher ? 'teacher-lab-records' : 'student-lab-records' }">实验记录{{ teacher ? '与统计' : '' }}</RouterLink></template>
    </PageHeader>
    <StatePanel v-if="loading" kind="loading" title="正在读取实验任务" />
    <StatePanel v-else-if="!classes.length" title="没有有效班级" :description="error || '加入班级后即可开展实验。'" />
    <template v-else>
      <SectionCard title="实验班级">
        <label for="lab-class">班级</label>
        <select id="lab-class" v-model="classId"><option v-for="item in classes" :key="item.id" :value="item.id">{{ item.name }}</option></select>
        <p v-if="error" class="error" role="alert">{{ error }}</p>
      </SectionCard>
      <div class="lab-task-grid">
        <SectionCard v-for="item in tasks" :key="item.id" :title="item.title">
          <p>{{ item.instructions_md }}</p>
          <p class="hint">{{ item.code }} · {{ item.board.chips.map(chip => chip.model).join(' / ') }}</p>
          <div class="lab-actions">
            <button class="button button--primary" :disabled="busy" @click="start(item)">{{ teacher ? '打开演示' : '开始／继续接线' }}</button>
            <button class="button" :disabled="busy" @click="start(item, true)">新建{{ teacher ? '演示' : '练习' }}</button>
            <RouterLink v-if="!teacher" class="button" :to="{ name: 'lab-upload', params: { id: item.id }, query: { class_id: classId } }">上传电路</RouterLink>
            <a class="button" :href="`/api/v1/lab-tasks/${item.id}/template`">下载端口模板</a>
          </div>
        </SectionCard>
      </div>
      <StatePanel v-if="!tasks.length" title="暂未开放实验任务" />
    </template>
  </div>
</template>

<style scoped>
.lab-page { display: grid; grid-template-columns: minmax(0, 1fr); gap: 20px; } .lab-task-grid { display: grid; grid-template-columns: repeat(auto-fit,minmax(min(100%,420px),1fr)); gap: 18px; }
.lab-actions { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 16px; } select { margin-left: 12px; } p { line-height: 1.7; } .error { color: var(--color-danger, #b42318); }
</style>
