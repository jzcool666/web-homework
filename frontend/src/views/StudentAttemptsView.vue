<script setup>
/**
 * 本人实验记录（SPEC-013 E051）。
 *
 * 只读取 `GET /me/experiment-attempts`：服务器按学生过滤，页面没有任何跨用户入口。
 * 记录里的 passed / first_error_index / expected 都是提交当时的快照，实验事后被
 * 编辑也不会改变这里的历史。
 */
import { computed, onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'

import PageHeader from '@/components/ui/PageHeader.vue'
import SectionCard from '@/components/ui/SectionCard.vue'
import StatePanel from '@/components/ui/StatePanel.vue'
import StatusBadge from '@/components/ui/StatusBadge.vue'
import { api } from '@/api/client'
import { formatBits, modelLabel } from '@/utils/demo'
import { resultSummary, resultTone } from '@/utils/attempt'

const attempts = ref([])
const experiments = ref([])
const state = ref('loading')
const loadError = ref('')

const titles = computed(() => {
  const map = new Map()
  for (const experiment of experiments.value) map.set(experiment.id, experiment)
  return map
})

const passedCount = computed(() => attempts.value.filter((item) => item.passed).length)

function experimentOf(attempt) {
  return titles.value.get(attempt.experiment_id) ?? null
}

function titleOf(attempt) {
  return experimentOf(attempt)?.title ?? `实验 #${attempt.experiment_id}`
}

function simulatorOf(attempt) {
  return experimentOf(attempt)?.simulator_type ?? 'counter'
}

async function load() {
  state.value = 'loading'
  try {
    const [attemptList, experimentList] = await Promise.all([
      api.get('/me/experiment-attempts?page_size=100'),
      api.get('/experiments?page_size=100'),
    ])
    attempts.value = attemptList
    experiments.value = experimentList
    state.value = 'ready'
  } catch (err) {
    loadError.value = err.message
    state.value = 'error'
  }
}

onMounted(load)
</script>

<template>
  <div class="attempts-page">
    <PageHeader
      eyebrow="学习空间"
      title="我的实验记录"
      description="这里只有你本人的提交记录，按提交时间倒序排列。"
    >
      <template #actions>
        <RouterLink class="button button--secondary" :to="{ name: 'student-experiments' }">返回实验中心</RouterLink>
      </template>
    </PageHeader>

    <StatePanel v-if="state === 'loading'" kind="loading" title="正在读取实验记录" />
    <StatePanel v-else-if="state === 'error'" kind="error" title="实验记录无法读取" :description="loadError" />
    <StatePanel
      v-else-if="attempts.length === 0"
      title="还没有实验记录"
      description="在实验中心完成一次逐拍预测后，这里会显示你的提交与结果。"
    />

    <template v-else>
      <SectionCard :title="`共 ${attempts.length} 次提交，通过 ${passedCount} 次`">
        <div class="table-scroll">
          <table>
            <thead>
              <tr>
                <th scope="col">结果</th><th scope="col">实验</th><th scope="col">模型</th>
                <th scope="col">拍数</th><th scope="col">首拍预测</th><th scope="col">实验版本</th>
                <th scope="col">操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="attempt in attempts" :key="attempt.id">
                <td>
                  <StatusBadge :tone="resultTone(attempt)">
                    {{ attempt.passed ? '通过' : resultSummary(attempt) }}
                  </StatusBadge>
                </td>
                <td>{{ titleOf(attempt) }}</td>
                <td>{{ modelLabel(simulatorOf(attempt)) }}</td>
                <td class="mono">{{ attempt.actual.length }}</td>
                <td class="mono">{{ formatBits(attempt.actual[0] ?? 0, simulatorOf(attempt)) }}</td>
                <td class="mono">{{ attempt.experiment_version }}</td>
                <td>
                  <RouterLink :to="{ name: 'student-experiment', params: { id: attempt.experiment_id } }">
                    再做一次
                  </RouterLink>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </SectionCard>

      <SectionCard title="最近一次的逐拍对照">
        <div class="table-scroll">
          <table>
            <thead>
              <tr><th scope="col">拍</th><th scope="col">你填的</th><th scope="col">正确答案</th><th scope="col">说明</th></tr>
            </thead>
            <tbody>
              <tr v-for="(line, index) in attempts[0].explanations" :key="index">
                <td>{{ index + 1 }}</td>
                <td class="mono">{{ formatBits(attempts[0].actual[index] ?? 0, simulatorOf(attempts[0])) }}</td>
                <td class="mono">{{ formatBits(attempts[0].expected[index] ?? 0, simulatorOf(attempts[0])) }}</td>
                <td class="explain">{{ line }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </SectionCard>
    </template>
  </div>
</template>

<style scoped>
.attempts-page { width: 100%; }
.attempts-page .section-card { margin-bottom: var(--space-4); }
.table-scroll { overflow-x: auto; }
.table-scroll table { min-width: 40rem; }
.mono { font-family: var(--font-mono); }
.explain { color: var(--color-text-secondary); font-size: var(--font-size-xs); }
</style>
