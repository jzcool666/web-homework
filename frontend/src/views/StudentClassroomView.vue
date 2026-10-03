<script setup>
import { computed, onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'

import { api } from '@/api/client'
import PageHeader from '@/components/ui/PageHeader.vue'
import {
  LEAVE_STATUS_LABEL,
  PHASE_LABEL,
  STATUS_LABEL,
  formatLocal,
  taskPhase,
} from '@/utils/attendance'

const classes = ref([])
const classId = ref('')
const tasks = ref([])
const myRecords = ref({})
const myLeaves = ref([])
const selectedId = ref(null)
const code = ref('')
const reason = ref('')
const error = ref(null)
const notice = ref(null)

const selected = computed(() => tasks.value.find((t) => t.id === selectedId.value) ?? null)
const myRecord = computed(() =>
  selectedId.value === null ? null : (myRecords.value[selectedId.value] ?? []).at(0) ?? null,
)
const myLeave = computed(() =>
  myLeaves.value.find((l) => l.task_id === selectedId.value) ?? null,
)
const canSignIn = computed(() => {
  if (!selected.value || !myRecord.value) return false
  const phase = taskPhase(selected.value)
  return (phase === 'open' || phase === 'late') && myRecord.value.status === 'pending'
})
const canApplyLeave = computed(() => {
  if (!selected.value) return false
  return taskPhase(selected.value) !== 'closed' && myLeave.value === null
})

function recordOf(taskId) {
  return (myRecords.value[taskId] ?? []).at(0) ?? null
}

async function load() {
  error.value = null
  try {
    classes.value = await api.get('/classes?page_size=100')
    if (!classId.value) classId.value = classes.value[0]?.id ?? ''
    if (!classId.value) return

    const [taskList, leaveList] = await Promise.all([
      api.get(`/attendance-tasks?class_id=${classId.value}&page_size=100`),
      api.get(`/leave-requests?class_id=${classId.value}&page_size=100`),
    ])
    tasks.value = taskList
    myLeaves.value = leaveList

    const pairs = await Promise.all(
      taskList.map(async (task) => [
        task.id,
        await api.get(`/attendance-tasks/${task.id}/records?page_size=100`),
      ]),
    )
    myRecords.value = Object.fromEntries(pairs)
    if (selectedId.value === null && taskList.length > 0) selectedId.value = taskList[0].id
  } catch (err) {
    error.value = err.message
  }
}

async function signIn() {
  error.value = null
  notice.value = null
  try {
    const record = await api.post(`/attendance-tasks/${selectedId.value}/sign-ins`, {
      code: code.value,
    })
    notice.value = `签到成功：${STATUS_LABEL[record.status]}（${formatLocal(record.signed_at)}）`
    code.value = ''
    await load()
  } catch (err) {
    error.value = err.message
  }
}

async function applyLeave() {
  error.value = null
  notice.value = null
  try {
    await api.post('/leave-requests', {
      task_id: selectedId.value,
      reason: reason.value,
    })
    notice.value = '请假申请已提交，等待教师审批'
    reason.value = ''
    await load()
  } catch (err) {
    error.value = err.message
  }
}

onMounted(load)
</script>

<template>
  <main class="page">
    <PageHeader icon="calendar" title="签到与请假" description="使用教师当堂公布的签到码，或提交本次任务的请假申请。结果以服务器记录为准。" :steps="['选择课堂任务', '签到或申请请假', '核对本人记录']" />

    <template v-if="classes.length === 0">
      <p class="hint">尚未分配班级，请联系任课教师或管理员。</p>
    </template>

    <template v-else>
      <p class="hint">
        班级：{{ classes[0].name }}。签到以服务器时间为准，请使用教师当堂公布的六位签到码。
      </p>

      <p v-if="notice" class="success">{{ notice }}</p>
      <p v-if="error" class="error" role="alert">{{ error }}</p>

      <section class="card">
        <h2>签到任务</h2>
        <div class="table-scroll" tabindex="0" role="region" aria-label="本人课堂数据表，可横向滚动">
<table>
          <thead>
            <tr>
              <th>标题</th>
              <th>截止</th>
              <th>状态</th>
              <th>我的出勤</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="task in tasks" :key="task.id">
              <td>{{ task.title }}</td>
              <td>{{ formatLocal(task.closes_at) }}</td>
              <td><span class="badge">{{ PHASE_LABEL[taskPhase(task)] }}</span></td>
              <td>{{ STATUS_LABEL[recordOf(task.id)?.status] ?? '—' }}</td>
              <td>
                <button class="link" type="button" @click="selectedId = task.id">选中</button>
              </td>
            </tr>
          </tbody>
        </table>
</div>
        <p v-if="tasks.length === 0" class="hint">本班还没有签到任务。</p>
      </section>

      <section v-if="selected" class="card">
        <h2>「{{ selected.title }}」</h2>
        <p class="hint">
          {{ formatLocal(selected.opens_at) }} 开始签到，{{ formatLocal(selected.late_at) }}
          之后记迟到，{{ formatLocal(selected.closes_at) }} 截止。
        </p>
        <p>
          当前状态：<span class="badge">{{ PHASE_LABEL[taskPhase(selected)] }}</span>
          我的出勤：<span class="badge">{{
            STATUS_LABEL[myRecord?.status] ?? '未在名单'
          }}</span>
        </p>

        <form v-if="canSignIn" @submit.prevent="signIn">
          <div class="field">
            <label for="sign_code">六位签到码</label>
            <input
              id="sign_code"
              v-model="code"
              inputmode="numeric"
              pattern="\d{6}"
              maxlength="6"
              placeholder="000000"
              required
            />
          </div>
          <button class="primary" type="submit">签到</button>
        </form>
        <p v-else-if="myRecord?.status === 'leave'" class="hint">已批准请假，无需签到。</p>
        <p v-else-if="myRecord && myRecord.status !== 'pending'" class="hint">
          已签到，重复提交不会改变记录。
        </p>
        <p v-else-if="taskPhase(selected) === 'closed'" class="hint">签到已结束。</p>
        <p v-else class="hint">签到尚未开始。</p>

        <template v-if="myLeave">
          <p class="hint">
            请假申请：{{ LEAVE_STATUS_LABEL[myLeave.status] }}（{{ myLeave.reason }}）
          </p>
        </template>
        <form v-else-if="canApplyLeave" @submit.prevent="applyLeave">
          <div class="field">
            <label for="leave_reason">请假理由（结束前提交，教师可在结束后审批）</label>
            <input id="leave_reason" v-model="reason" maxlength="300" required />
          </div>
          <button class="primary" type="submit">提交请假申请</button>
        </form>
      </section>
    </template>
  </main>
</template>

<style scoped>
h2 {
  font-size: 1.05rem;
  margin: 0 0 0.75rem;
}
</style>
