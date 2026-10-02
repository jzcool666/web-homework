<script setup>
/**
 * 教师学情分析：出勤与风险因素统计（SPEC-003 E055）。
 *
 * 只统计本人任教班级；跨班由后端按 404 拒绝。窗口按任务 opens_at 选择，
 * 且只纳入已结算任务。出勤率与相关系数各自标注口径；没有分母时显示「无分母」
 * 而不是 0%，相关系数未计算时显示原因而不是 0。
 */
import { computed, onMounted, ref } from 'vue'

import { API_BASE, api } from '@/api/client'
import PageHeader from '@/components/ui/PageHeader.vue'
import SectionCard from '@/components/ui/SectionCard.vue'
import StatePanel from '@/components/ui/StatePanel.vue'
import StatusBadge from '@/components/ui/StatusBadge.vue'
import {
  ATTENDANCE_WINDOW_NOTE,
  CORRELATION_NOTE,
  COUNT_LABELS,
  attendanceQuery,
  attendanceRateText,
  correlationText,
  defaultAttendanceWindow,
} from '@/utils/attendanceStats'

const classes = ref([])
const classId = ref('')
const window = ref(defaultAttendanceWindow())
const stats = ref(null)
const loading = ref(false)
const listError = ref(null)

const query = computed(() =>
  attendanceQuery({
    classId: classId.value,
    from: window.value.from,
    to: window.value.to,
  }),
)
const csvHref = computed(() => `${API_BASE}/analytics/attendance?${query.value}&format=csv`)

const students = computed(() => stats.value?.students ?? [])
const counts = computed(
  () => stats.value?.counts ?? { present: 0, late: 0, leave: 0, absent: 0 },
)

function rateTone(rate) {
  if (rate === null || rate === undefined) return 'neutral'
  if (rate >= 0.8) return 'success'
  if (rate >= 0.5) return 'warning'
  return 'danger'
}

function studentLabel(row) {
  if (row.display_name) {
    return row.student_no ? `${row.display_name}（${row.student_no}）` : row.display_name
  }
  return `#${row.student_id}`
}

async function loadClasses() {
  classes.value = await api.get('/classes?page_size=100')
  if (!classId.value && classes.value.length > 0) classId.value = classes.value[0].id
}

async function loadStats() {
  if (!classId.value) {
    stats.value = null
    return
  }
  loading.value = true
  listError.value = null
  try {
    stats.value = await api.get(`/analytics/attendance?${query.value}`)
  } catch (err) {
    listError.value = err.message
    stats.value = null
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  try {
    await loadClasses()
    await loadStats()
  } catch (err) {
    listError.value = err.message
  }
})
</script>

<template>
  <div class="page">
    <PageHeader
      eyebrow="学情"
      title="出勤统计"
      description="按班级与时间窗口查看出勤分布、学生明细和出勤与成绩的相关分析。窗口按任务开始时间选择，进行中的任务不计入。"
    />

    <SectionCard title="筛选">
      <div class="filters">
        <div class="field">
          <label for="at_class">班级</label>
          <select id="at_class" v-model="classId" @change="loadStats">
            <option value="" disabled>请选择班级</option>
            <option v-for="item in classes" :key="item.id" :value="item.id">{{ item.name }}</option>
          </select>
        </div>
        <div class="field">
          <label for="at_from">窗口起（UTC）</label>
          <input id="at_from" v-model="window.from" type="date" @change="loadStats" />
        </div>
        <div class="field">
          <label for="at_to">窗口止（UTC，不含）</label>
          <input id="at_to" v-model="window.to" type="date" @change="loadStats" />
        </div>
        <button class="button button--secondary" type="button" @click="loadStats">刷新</button>
        <a class="button button--secondary" :href="csvHref">导出 CSV</a>
      </div>
      <p class="hint">{{ ATTENDANCE_WINDOW_NOTE }}</p>
      <p v-if="stats" class="hint">
        当前窗口 {{ stats.window.from }} → {{ stats.window.to }}，已结算任务
        {{ stats.settled_tasks }} 个
      </p>
      <p v-if="classes.length === 0" class="hint">还没有任教的班级，请联系管理员分配。</p>
    </SectionCard>

    <p v-if="listError" class="error" role="alert">{{ listError }}</p>
    <StatePanel v-if="loading" kind="loading" title="正在统计" />

    <template v-else-if="stats">
      <SectionCard title="出勤分布">
        <div class="summary">
          <span>已结算任务：<strong>{{ stats.settled_tasks }}</strong></span>
          <span v-for="(label, key) in COUNT_LABELS" :key="key">
            {{ label }}：<strong>{{ counts[key] }}</strong>
          </span>
          <StatusBadge :tone="rateTone(stats.attendance_rate)">
            出勤率 {{ attendanceRateText(stats.attendance_rate) }}
          </StatusBadge>
        </div>
        <StatePanel
          v-if="stats.settled_tasks === 0"
          title="该窗口内没有已结算的考勤任务"
          description="考勤任务结束后才会结算并进入统计，进行中的任务不参与。"
        />
      </SectionCard>

      <SectionCard title="学生明细">
        <StatePanel
          v-if="students.length === 0"
          title="该窗口内没有考勤记录"
          description="发布考勤任务并结算后，这里会显示每名学生的出勤情况。"
        />
        <div v-else class="table-scroll">
          <table>
            <thead>
              <tr>
                <th>学生</th>
                <th v-for="(label, key) in COUNT_LABELS" :key="key">{{ label }}</th>
                <th>出勤率</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in students" :key="row.student_id">
                <td>{{ studentLabel(row) }}</td>
                <td v-for="(label, key) in COUNT_LABELS" :key="key">{{ row.counts[key] }}</td>
                <td>
                  <StatusBadge :tone="rateTone(row.attendance_rate)">
                    {{ attendanceRateText(row.attendance_rate) }}
                  </StatusBadge>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </SectionCard>

      <SectionCard title="出勤与成绩的相关分析">
        <p class="basis">{{ CORRELATION_NOTE }}</p>
        <div class="summary">
          <span>相关系数：<strong>{{ correlationText(stats.correlation) }}</strong></span>
          <span>共同样本：<strong>{{ stats.correlation.n }}</strong></span>
        </div>
        <p v-if="stats.correlation.reason" class="hint">{{ stats.correlation.reason }}</p>
      </SectionCard>
    </template>
  </div>
</template>

<style scoped>
.filters {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(11rem, 1fr));
  gap: 0 var(--space-4);
  align-items: end;
  margin-bottom: var(--space-3);
}

.filters button,
.filters a {
  justify-self: start;
}

.basis {
  margin: 0 0 var(--space-3);
  padding: var(--space-3) var(--space-4);
  border-left: 3px solid var(--color-primary);
  background: var(--color-grid-surface);
  color: var(--color-text-secondary);
  font-size: var(--font-size-sm);
}

.summary {
  display: flex;
  align-items: center;
  gap: var(--space-4);
  flex-wrap: wrap;
}
</style>
