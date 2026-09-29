<script setup>
/**
 * 教师实验统计（SPEC-014，E058）。
 *
 * 只统计本人任教班级的当前有效在册学生：跨班由后端按 404 拒绝，
 * JSON 与 CSV 走同一权限校验。默认窗口为最近 30 天，可按日期与实验筛选。
 * 页面不展示学习时长——实验记录里没有这种数据，不虚构。
 */
import { computed, onMounted, ref } from 'vue'

import { API_BASE, api } from '@/api/client'
import PageHeader from '@/components/ui/PageHeader.vue'
import SectionCard from '@/components/ui/SectionCard.vue'
import StatePanel from '@/components/ui/StatePanel.vue'
import {
  SUMMARY_HINT,
  formatCount,
  formatRate,
  statsPath,
  toUtcStamp,
} from '@/utils/experimentStats'

const classes = ref([])
const classId = ref('')
const experiments = ref([])
const experimentId = ref('')
const fromLocal = ref('')
const toLocal = ref('')
const data = ref(null)
const loading = ref(false)
const error = ref(null)
const listError = ref(null)
let latestRequest = 0

const filters = computed(() => ({
  classId: classId.value,
  from: toUtcStamp(fromLocal.value),
  to: toUtcStamp(toLocal.value),
  experimentId: experimentId.value,
}))

const csvHref = computed(() => {
  const window = data.value?.window
  return `${API_BASE}${statsPath({
    ...filters.value,
    from: window?.from ?? filters.value.from,
    to: window?.to ?? filters.value.to,
    format: 'csv',
  })}`
})

const summaryTiles = computed(() => {
  if (!data.value) return []
  return [
    { key: 'published_count', label: '已发布实验', value: formatCount(data.value.published_count) },
    { key: 'participants', label: '参与人数', value: formatCount(data.value.participants) },
    { key: 'passed_students', label: '通过人数', value: formatCount(data.value.passed_students) },
    { key: 'pass_rate', label: '总通过率', value: formatRate(data.value.pass_rate) },
    { key: 'attempt_count', label: '尝试次数', value: formatCount(data.value.attempt_count) },
  ]
})

async function loadClasses() {
  classes.value = await api.get('/classes?page_size=100')
  if (!classId.value && classes.value.length > 0) classId.value = classes.value[0].id
}

async function loadExperiments() {
  experiments.value = await api.get('/experiments?page_size=100')
}

async function loadStats() {
  const requestId = ++latestRequest
  if (!classId.value) {
    data.value = null
    loading.value = false
    return
  }
  loading.value = true
  error.value = null
  data.value = null
  try {
    const response = await api.get(statsPath(filters.value))
    if (requestId === latestRequest) data.value = response
  } catch (err) {
    if (requestId === latestRequest) error.value = err.message
  } finally {
    if (requestId === latestRequest) loading.value = false
  }
}

function resetWindow() {
  fromLocal.value = ''
  toLocal.value = ''
  return loadStats()
}

onMounted(async () => {
  try {
    await Promise.all([loadClasses(), loadExperiments()])
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
      title="实验统计"
      description="按班级、时间窗口与实验查看参与人数、通过人数、尝试次数与通过率。统计只包含本班当前有效在册学生。"
    />

    <p v-if="error" class="error" role="alert">{{ error }}</p>

    <SectionCard title="筛选条件">
      <StatePanel v-if="listError" kind="error" title="加载班级失败" :description="listError" />
      <div class="filters">
        <div class="field">
          <label for="es_class">班级</label>
          <select id="es_class" v-model="classId" @change="loadStats">
            <option value="" disabled>请选择班级</option>
            <option v-for="item in classes" :key="item.id" :value="item.id">{{ item.name }}</option>
          </select>
        </div>
        <div class="field">
          <label for="es_experiment">实验</label>
          <select id="es_experiment" v-model="experimentId" @change="loadStats">
            <option value="">全部实验</option>
            <option v-for="item in experiments" :key="item.id" :value="item.id">
              {{ item.title }}
            </option>
          </select>
        </div>
        <div class="field">
          <label for="es_from">起始（本地时间，可空）</label>
          <input id="es_from" v-model="fromLocal" type="datetime-local" @change="loadStats" />
        </div>
        <div class="field">
          <label for="es_to">截止（本地时间，可空）</label>
          <input id="es_to" v-model="toLocal" type="datetime-local" @change="loadStats" />
        </div>
      </div>
      <div class="actions">
        <button class="button button--secondary" type="button" @click="resetWindow">
          最近 30 天
        </button>
        <a v-if="classId && data && !loading" class="button button--secondary" :href="csvHref">导出 CSV</a>
      </div>
      <p v-if="classes.length === 0" class="hint">还没有任教的班级，请联系管理员分配。</p>
      <p class="hint">{{ SUMMARY_HINT }}</p>
    </SectionCard>

    <SectionCard title="统计结果">
      <StatePanel v-if="loading" kind="loading" title="正在统计实验数据" />
      <StatePanel
        v-else-if="!data"
        title="请选择班级"
        description="选择班级后即可查看该班的实验参与与通过情况。"
      />
      <template v-else>
        <ul class="tiles">
          <li v-for="tile in summaryTiles" :key="tile.key" class="tile">
            <span class="tile__label">{{ tile.label }}</span>
            <span class="tile__value">{{ tile.value }}</span>
          </li>
        </ul>
        <p class="hint">
          统计窗口：{{ data.window.from }} → {{ data.window.to }}（UTC，右开区间）
        </p>

        <StatePanel
          v-if="data.experiments.length === 0"
          title="该筛选下没有已发布实验"
          description="先发布实验，学生的尝试才会进入统计。"
        />
        <div v-else class="table-scroll">
          <table>
            <thead>
              <tr>
                <th>实验</th>
                <th>参与人数</th>
                <th>通过人数</th>
                <th>尝试次数</th>
                <th>通过率</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in data.experiments" :key="row.experiment_id">
                <td>{{ row.title }}</td>
                <td>{{ formatCount(row.participants) }}</td>
                <td>{{ formatCount(row.passed_students) }}</td>
                <td>{{ formatCount(row.attempt_count) }}</td>
                <td>{{ formatRate(row.pass_rate) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </template>
    </SectionCard>
  </div>
</template>

<style scoped>
.filters {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(12rem, 1fr));
  gap: 0 var(--space-4);
}

.actions {
  display: flex;
  gap: var(--space-3);
  align-items: center;
  margin-top: var(--space-3);
}

.tiles {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(8rem, 1fr));
  gap: var(--space-3);
  list-style: none;
  padding: 0;
  margin: 0 0 var(--space-4);
}

.tile {
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  padding: var(--space-3);
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.tile__label {
  color: var(--color-text-secondary);
  font-size: var(--font-size-xs);
}

.tile__value {
  font-size: var(--font-size-lg);
  font-weight: 600;
}
</style>
