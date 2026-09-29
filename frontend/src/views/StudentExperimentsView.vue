<script setup>
/**
 * 学生实验中心（SPEC-013 E048 读取 + E051 本人记录）。
 *
 * 只列出已发布实验，并显示每个实验的检查点数与我上次的结果；
 * 是否通过完全取服务器返回的 passed，不在前端重算。
 */
import { computed, onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'

import AppIcon from '@/components/ui/AppIcon.vue'
import PageHeader from '@/components/ui/PageHeader.vue'
import SectionCard from '@/components/ui/SectionCard.vue'
import StatePanel from '@/components/ui/StatePanel.vue'
import StatusBadge from '@/components/ui/StatusBadge.vue'
import { api } from '@/api/client'
import { modelLabel } from '@/utils/demo'
import { resultSummary, resultTone } from '@/utils/attempt'

const experiments = ref([])
const attempts = ref([])
const state = ref('loading')
const loadError = ref('')

const lastByExperiment = computed(() => {
  const map = new Map()
  for (const attempt of attempts.value) {
    // 历史按创建时间倒序返回，第一次遇到的就是最近一次
    if (!map.has(attempt.experiment_id)) map.set(attempt.experiment_id, attempt)
  }
  return map
})

function lastOf(experimentId) {
  return lastByExperiment.value.get(experimentId) ?? null
}

async function load() {
  state.value = 'loading'
  try {
    const [experimentList, attemptList] = await Promise.all([
      api.get('/experiments?page_size=100'),
      api.get('/me/experiment-attempts?page_size=100'),
    ])
    experiments.value = experimentList
    attempts.value = attemptList
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
      eyebrow="学习空间"
      title="实验中心"
      description="每个实验的输入序列由服务器固定。你只需要预测每个有效上升沿之后的 Q，提交后立即看到逐拍对照。"
    >
      <template #actions>
        <RouterLink class="button button--secondary" :to="{ name: 'student-attempts' }">我的实验记录</RouterLink>
      </template>
    </PageHeader>

    <StatePanel v-if="state === 'loading'" kind="loading" title="正在读取实验列表" />
    <StatePanel v-else-if="state === 'error'" kind="error" title="实验列表无法读取" :description="loadError" />
    <StatePanel
      v-else-if="experiments.length === 0"
      title="当前没有可做的实验"
      description="教师的实验发布后会出现在这里。"
    />

    <template v-else>
      <SectionCard title="可做的实验">
        <div class="experiment-list">
          <div v-for="experiment in experiments" :key="experiment.id" class="experiment-row">
            <span class="experiment-row__icon"><AppIcon name="flask" /></span>
            <div class="experiment-row__body">
              <strong>{{ experiment.title }}</strong>
              <small>
                {{ modelLabel(experiment.simulator_type) }} ·
                需要预测 {{ experiment.checkpoints.length }} 拍
                <template v-if="lastOf(experiment.id)">
                  · 上次：{{ resultSummary(lastOf(experiment.id)) }}
                </template>
                <template v-else>· 还没有记录</template>
              </small>
            </div>
            <StatusBadge v-if="lastOf(experiment.id)" :tone="resultTone(lastOf(experiment.id))">
              {{ lastOf(experiment.id).passed ? '已通过' : '未通过' }}
            </StatusBadge>
            <StatusBadge v-else>未做</StatusBadge>
            <RouterLink
              class="button button--primary"
              :to="{ name: 'student-experiment', params: { id: experiment.id } }"
            >
              进入预测
            </RouterLink>
          </div>
        </div>
      </SectionCard>

      <SectionCard title="最近记录">
        <div v-if="attempts.length === 0" class="empty">还没有提交过实验预测。</div>
        <ul v-else class="attempt-list">
          <li v-for="attempt in attempts.slice(0, 5)" :key="attempt.id">
            <StatusBadge :tone="resultTone(attempt)">{{ attempt.passed ? '通过' : resultSummary(attempt) }}</StatusBadge>
            <span>共 {{ attempt.actual.length }} 拍</span>
            <span class="mono">实验版本 {{ attempt.experiment_version }}</span>
          </li>
        </ul>
      </SectionCard>
    </template>
  </div>
</template>

<style scoped>
.experiments-page { width: 100%; }
.experiments-page .section-card { margin-bottom: var(--space-4); }
.experiment-list { display: grid; gap: var(--space-3); }
.experiment-row { display: flex; align-items: center; gap: var(--space-3); flex-wrap: wrap; padding: var(--space-3); border: 1px solid var(--color-border); border-radius: var(--radius-sm); }
.experiment-row__icon { display: grid; place-items: center; width: 2.6rem; height: 2.6rem; border-radius: var(--radius-sm); color: var(--color-primary); background: var(--color-primary-soft); }
.experiment-row__body { display: grid; gap: 2px; margin-right: auto; }
.experiment-row__body small { color: var(--color-text-secondary); font-size: var(--font-size-xs); }
.attempt-list { list-style: none; padding: 0; margin: 0; display: grid; gap: var(--space-2); }
.attempt-list li { display: flex; align-items: center; gap: var(--space-3); padding: var(--space-2) 0; border-bottom: 1px solid var(--color-border); font-size: var(--font-size-sm); }
.attempt-list li:last-child { border-bottom: 0; }
.mono { font-family: var(--font-mono); color: var(--color-text-secondary); }
.empty { color: var(--color-text-secondary); }
</style>
