<script setup>
import { computed, onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'
import PageHeader from '@/components/ui/PageHeader.vue'
import StatePanel from '@/components/ui/StatePanel.vue'
import StatusBadge from '@/components/ui/StatusBadge.vue'
import StudentExperimentView from './StudentExperimentView.vue'
import { readAll } from '@/api/pagination'
import { modelLabel } from '@/utils/demo'
const experiments = ref([]),
  attempts = ref([]),
  state = ref('loading'),
  loadError = ref(''),
  filter = ref('all'),
  selectedId = ref(null),
  attemptsError = ref('')
const kinds = [
  { id: 'all', title: '全部' },
  { id: 'd', title: 'D 触发器' },
  { id: 'jk', title: 'JK 触发器' },
  { id: 'counter', title: '计数器' },
  { id: 'shift', title: '寄存器' },
]
const filtered = computed(() =>
  experiments.value.filter(
    (row) => filter.value === 'all' || row.simulator_type === filter.value,
  ),
)
const lastByExperiment = computed(() => {
  const map = new Map()
  for (const attempt of attempts.value)
    if (!map.has(attempt.experiment_id)) map.set(attempt.experiment_id, attempt)
  return map
})
function changeFilter(kind) {
  filter.value = kind
  if (!filtered.value.some((row) => row.id === selectedId.value))
    selectedId.value = filtered.value[0]?.id ?? null
}
async function refreshAttempts() {
  try {
    attempts.value = await readAll('/me/experiment-attempts')
    attemptsError.value = ''
  } catch (err) {
    attemptsError.value = err.message
  }
}
async function load() {
  state.value = 'loading'
  try {
    experiments.value = await readAll('/experiments')
    await refreshAttempts()
    selectedId.value = experiments.value[0]?.id ?? null
    state.value = 'ready'
  } catch (err) {
    loadError.value = err.message
    state.value = 'error'
  }
}
onMounted(load)
</script>
<template>
  <div class="experiments-page">
    <PageHeader
      title="实验中心"
      description="从电路结构到逐拍预测，观察输入，验证你的状态分析。"
      ><template #actions
        ><RouterLink
          class="button button--secondary"
          :to="{ name: 'student-attempts' }"
          >我的实验记录</RouterLink
        ></template
      ></PageHeader
    >
    <nav class="filter-pills" aria-label="实验类型">
      <button
        v-for="kind in kinds"
        :key="kind.id"
        type="button"
        :aria-pressed="filter === kind.id"
        @click="changeFilter(kind.id)"
      >
        {{ kind.title }}
      </button>
    </nav>
    <StatePanel
      v-if="state === 'loading'"
      kind="loading"
      title="正在读取实验列表"
    /><StatePanel
      v-else-if="state === 'error'"
      kind="error"
      title="实验列表无法读取"
      :description="loadError"
    /><StatePanel
      v-else-if="!filtered.length"
      title="当前类型暂无实验"
      description="教师发布相应实验后会出现在这里。"
    />
    <template v-else
      ><p v-if="attemptsError" class="error" role="alert">
        实验记录暂不可用：{{ attemptsError }}
      </p>
      <div class="ref-workspace">
        <aside class="workspace-nav">
          <h2>
            实验列表 <small>{{ filtered.length }}</small>
          </h2>
          <button
            v-for="experiment in filtered"
            :key="experiment.id"
            type="button"
            :aria-current="selectedId === experiment.id ? 'true' : undefined"
            @click="selectedId = experiment.id"
          >
            <div>
              <strong>{{ experiment.title }}</strong
              ><small
                >{{ modelLabel(experiment.simulator_type) }} ·
                {{ experiment.checkpoints.length }} 拍</small
              >
            </div>
            <StatusBadge
              :tone="
                lastByExperiment.get(experiment.id)?.passed
                  ? 'success'
                  : lastByExperiment.has(experiment.id)
                    ? 'warning'
                    : 'neutral'
              "
              >{{
                attemptsError
                  ? '未知'
                  : lastByExperiment.get(experiment.id)?.passed
                    ? '上次通过'
                    : lastByExperiment.has(experiment.id)
                      ? '待巩固'
                      : '未做'
              }}</StatusBadge
            >
          </button>
        </aside>
        <div class="experiment-workbench">
          <KeepAlive :max="8"
            ><StudentExperimentView
              v-if="selectedId"
              :key="selectedId"
              :experiment-key="selectedId"
              embedded
              @submitted="refreshAttempts"
          /></KeepAlive>
        </div></div
    ></template>
  </div>
</template>
<style scoped>
.experiments-page {
  width: 100%;
}
.workspace-nav {
  position: sticky;
  top: calc(var(--topbar-height) + 16px);
  max-height: calc(100vh - var(--topbar-height) - 40px);
  overflow-y: auto;
}
.workspace-nav h2 {
  display: flex;
  justify-content: space-between;
}
.workspace-nav h2 small {
  color: var(--color-text-secondary);
  font-weight: 400;
}
.workspace-nav :deep(.status-badge) {
  padding: 3px 5px;
  white-space: nowrap;
  font-size: 9px;
}
.experiment-workbench :deep(.page-header) {
  background: white;
  padding: 16px 18px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  margin-bottom: 14px;
}
.experiment-workbench :deep(.page-header h1) {
  font-size: 18px;
}
.experiment-workbench :deep(.page-header p) {
  font-size: 11px;
}
@media (max-width: 850px) {
  .workspace-nav {
    position: static;
    max-height: 210px;
  }
}
</style>
