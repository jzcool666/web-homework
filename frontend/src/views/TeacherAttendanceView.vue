<script setup>
import { initialClassId } from '@/utils/overview'
import { computed, onMounted, ref } from 'vue'

import { api } from '@/api/client'
import PageHeader from '@/components/ui/PageHeader.vue'
import {
  LEAVE_STATUS_LABEL,
  PHASE_LABEL,
  STATUS_LABEL,
  defaultWindow,
  formatLocal,
  localInputToUtc,
  taskPhase,
  utcToLocalInput,
} from '@/utils/attendance'

const classes = ref([])
const classId = ref('')
const tasks = ref([])
const recordsByTask = ref({})
const leaves = ref([])
const openTaskId = ref(null)
const issued = ref(null) // {title, code, kind}：明文码只在创建/重置响应中出现一次
const error = ref(null)
const notice = ref(null)

const form = ref({ title: '随堂签到', ...toLocalWindow(defaultWindow()) })

function toLocalWindow(window) {
  return {
    opens_at: utcToLocalInput(window.opens_at),
    late_at: utcToLocalInput(window.late_at),
    closes_at: utcToLocalInput(window.closes_at),
  }
}

const openTask = computed(() => tasks.value.find((t) => t.id === openTaskId.value) ?? null)
const taskLeaves = computed(() =>
  leaves.value.filter((l) => l.task_id === openTaskId.value),
)
const records = computed(() =>
  openTaskId.value === null ? [] : recordsByTask.value[openTaskId.value] ?? [],
)

async function loadClasses() {
  try {
    classes.value = await api.get('/classes?page_size=100')
    if (!classId.value) classId.value = initialClassId(classes.value)
  } catch (err) {
    error.value = err.message
  }
}

async function load() {
  error.value = null
  if (!classId.value) {
    tasks.value = []
    leaves.value = []
    return
  }
  try {
    const [taskList, leaveList] = await Promise.all([
      api.get(`/attendance-tasks?class_id=${classId.value}&page_size=100`),
      api.get(`/leave-requests?class_id=${classId.value}&page_size=100`),
    ])
    tasks.value = taskList
    leaves.value = leaveList
    if (openTaskId.value !== null) await loadRecords(openTaskId.value)
  } catch (err) {
    error.value = err.message
  }
}

async function loadRecords(taskId) {
  error.value = null
  try {
    // APIC 第 1 节：page_size 上限 100。班级名单超过 100 人时需要翻页，
    // 首版按课堂规模（含 60 人模拟负载）取第一页。
    recordsByTask.value = {
      ...recordsByTask.value,
      [taskId]: await api.get(`/attendance-tasks/${taskId}/records?page_size=100`),
    }
  } catch (err) {
    error.value = err.message
  }
}

async function selectTask(task) {
  openTaskId.value = openTaskId.value === task.id ? null : task.id
  if (openTaskId.value !== null) await loadRecords(openTaskId.value)
}

async function createTask() {
  error.value = null
  notice.value = null
  issued.value = null
  const body = {
    class_id: Number(classId.value),
    title: form.value.title,
    opens_at: localInputToUtc(form.value.opens_at),
    late_at: localInputToUtc(form.value.late_at),
    closes_at: localInputToUtc(form.value.closes_at),
  }
  try {
    const task = await api.post('/attendance-tasks', body)
    issued.value = { title: task.title, code: task.code, kind: '创建' }
    notice.value = `已发布「${task.title}」，班级当前有效名单已复制为待签到`
    await load()
  } catch (err) {
    error.value = err.message
  }
}

async function resetCode(task) {
  error.value = null
  notice.value = null
  try {
    const result = await api.post(`/attendance-tasks/${task.id}/code-resets`, {
      version: task.version,
    })
    issued.value = { title: task.title, code: result.code, kind: '重置' }
    await load()
  } catch (err) {
    error.value = err.message
    await load()
  }
}

async function settle(task) {
  error.value = null
  notice.value = null
  try {
    const result = await api.post(`/attendance-tasks/${task.id}/settlements`)
    notice.value =
      `「${task.title}」已结算：出勤 ${result.counts.present}、迟到 ${result.counts.late}、` +
      `请假 ${result.counts.leave}、缺勤 ${result.counts.absent}`
    await load()
  } catch (err) {
    error.value = err.message
    await load()
  }
}

async function review(leave, status) {
  error.value = null
  notice.value = null
  try {
    await api.patch(`/leave-requests/${leave.id}`, { version: leave.version, status })
    notice.value = status === 'approved' ? '已批准请假' : '已驳回请假'
    await load()
  } catch (err) {
    error.value = err.message
    await load()
  }
}

onMounted(async () => {
  await loadClasses()
  await load()
})
</script>

<template>
  <main class="page">
    <PageHeader icon="calendar" title="考勤与请假" description="选择班级并设定签到时段，向学生公布六位签到码。到达迟到时间会记迟到，结束后不能签到；新码只在发布或重置时显示一次。" :steps="['发起签到', '公布签到码', '审批请假与结算']" />

    <section class="card">
      <h2>选择班级</h2>
      <div class="field">
        <label for="attendance_class">班级</label>
        <select id="attendance_class" v-model="classId" @change="openTaskId = null; load()">
          <option value="" disabled>请选择班级</option>
          <option v-for="item in classes" :key="item.id" :value="item.id">
            {{ item.name }}
          </option>
        </select>
      </div>
      <p v-if="classes.length === 0" class="hint">还没有任教的班级，请联系管理员分配。</p>
    </section>

    <section class="card">
      <h2>发起签到</h2>
      <form class="attendance-create form-fields" @submit.prevent="createTask">
        <div class="field">
          <label for="task_title">标题</label>
          <input id="task_title" v-model="form.title" maxlength="100" required />
        </div>
        <div class="field">
          <label for="task_opens">开始时间（本地）</label>
          <input id="task_opens" v-model="form.opens_at" type="datetime-local" required />
        </div>
        <div class="field">
          <label for="task_late">迟到时间（本地）</label>
          <input id="task_late" v-model="form.late_at" type="datetime-local" required />
        </div>
        <div class="field">
          <label for="task_closes">结束时间（本地）</label>
          <input id="task_closes" v-model="form.closes_at" type="datetime-local" required />
        </div>
        <div class="form-actions">
          <p class="hint">发布时会把该班当前有效名单复制为「待签到」。</p>
          <button class="primary" type="submit" :disabled="!classId">发布签到</button>
        </div>
      </form>
    </section>

    <p v-if="issued" class="success issued" role="status">
      「{{ issued.title }}」{{ issued.kind }}成功，六位签到码：
      <strong data-testid="issued-code">{{ issued.code }}</strong>
      （只显示这一次，请当场告知学生）
    </p>
    <p v-if="notice" class="success">{{ notice }}</p>
    <p v-if="error" class="error" role="alert">{{ error }}</p>

    <section class="card">
      <h2>签到任务</h2>
      <div class="table-scroll" tabindex="0" role="region" aria-label="考勤数据表，可横向滚动">
<table>
        <thead>
          <tr>
            <th>标题</th>
            <th>窗口</th>
            <th>状态</th>
            <th>结算</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="task in tasks" :key="task.id">
            <td>{{ task.title }}</td>
            <td>
              {{ formatLocal(task.opens_at) }} → {{ formatLocal(task.closes_at) }}
              <br />
              <span class="hint">迟到线 {{ formatLocal(task.late_at) }}</span>
            </td>
            <td><span class="badge">{{ PHASE_LABEL[taskPhase(task)] }}</span></td>
            <td>
              <span v-if="task.settled_at" class="badge">已结算</span>
              <span v-else class="hint">未结算</span>
            </td>
            <td>
              <button class="link" type="button" @click="selectTask(task)">
                {{ openTaskId === task.id ? '收起名单' : '查看名单' }}
              </button>
              <button class="link" type="button" @click="resetCode(task)">重置签到码</button>
              <button class="link" type="button" @click="settle(task)">结算</button>
            </td>
          </tr>
        </tbody>
      </table>
</div>
      <p v-if="tasks.length === 0" class="hint">该班还没有签到任务。</p>
    </section>

    <section v-if="openTask" class="card">
      <h2>「{{ openTask.title }}」名单</h2>
      <div class="table-scroll" tabindex="0" role="region" aria-label="考勤数据表，可横向滚动">
<table>
        <thead>
          <tr>
            <th>学号</th>
            <th>姓名</th>
            <th>状态</th>
            <th>签到时间</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="record in records" :key="record.id">
            <td>{{ record.student_no }}</td>
            <td>{{ record.student_display_name }}</td>
            <td>{{ STATUS_LABEL[record.status] }}</td>
            <td>{{ formatLocal(record.signed_at) }}</td>
          </tr>
        </tbody>
      </table>
</div>
      <p v-if="records.length === 0" class="hint">名单为空。</p>

      <h3>请假申请</h3>
      <div class="table-scroll" tabindex="0" role="region" aria-label="考勤数据表，可横向滚动">
<table>
        <thead>
          <tr>
            <th>学号</th>
            <th>姓名</th>
            <th>理由</th>
            <th>状态</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="leave in taskLeaves" :key="leave.id">
            <td>{{ leave.student_no }}</td>
            <td>{{ leave.student_display_name }}</td>
            <td>{{ leave.reason }}</td>
            <td>{{ LEAVE_STATUS_LABEL[leave.status] }}</td>
            <td>
              <template v-if="leave.status === 'pending'">
                <button class="link" type="button" @click="review(leave, 'approved')">批准</button>
                <button class="link" type="button" @click="review(leave, 'rejected')">驳回</button>
              </template>
              <span v-else class="hint">{{ formatLocal(leave.reviewed_at) }}</span>
            </td>
          </tr>
        </tbody>
      </table>
</div>
      <p v-if="taskLeaves.length === 0" class="hint">该任务没有请假申请。</p>
    </section>
  </main>
</template>

<style scoped>
.attendance-create > .field:first-child { grid-column: 1 / -1; }
h2 {
  font-size: 1.05rem;
  margin: 0 0 0.75rem;
}

h3 {
  font-size: 0.95rem;
  margin: 1.5rem 0 0;
}

.issued strong {
  font-family: ui-monospace, Consolas, monospace;
  font-size: 1.15rem;
  letter-spacing: 0.2em;
}
</style>
