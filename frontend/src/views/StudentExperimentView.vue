<script setup>
/**
 * 逐拍预测与提交结果（SPEC-013 E050/E051）。
 *
 * 学生只提交 predictions 与 request_key：输入序列由服务器固定，标准状态由服务器
 * 重算，响应里的 passed/first_error_index/expected 直接用于展示，前端不自行判分。
 *
 * request_key 的用法：开始一次提交时生成一次；成功或收到业务错误后作废，下一次
 * 提交换新 key；只有网络类失败时保留同一个 key，使重试按 SPEC-013 第 4 节第 4 条
 * 幂等返回原结果，而不是重复计一次尝试。
 */
import { computed, ref, watch } from 'vue'
import { RouterLink, useRoute } from 'vue-router'

import AppIcon from '@/components/ui/AppIcon.vue'
import PageHeader from '@/components/ui/PageHeader.vue'
import SectionCard from '@/components/ui/SectionCard.vue'
import StatePanel from '@/components/ui/StatePanel.vue'
import StatusBadge from '@/components/ui/StatusBadge.vue'
import { ApiError, api } from '@/api/client'
import { formatBits, modelLabel } from '@/utils/demo'
import {
  attemptSummary,
  checkpointLabel,
  inputsText,
  predictionRange,
  resultSummary,
  resultTone,
  wrongIndexes,
} from '@/utils/attempt'

const route = useRoute()
const experiment = ref(null)
const history = ref([])
const answers = ref([])
const result = ref(null)
const state = ref('loading')
const loadError = ref('')
const error = ref(null)
const submitting = ref(false)
const pendingKey = ref(null)

const experimentId = computed(() => Number(route.params.id))
const simulatorType = computed(() => experiment.value?.simulator_type ?? 'd')
const checkpoints = computed(() => experiment.value?.checkpoints ?? [])
const range = computed(() => predictionRange(simulatorType.value))
const wrong = computed(() =>
  result.value ? wrongIndexes(result.value.expected, result.value.actual) : new Set(),
)

function emptyAnswers(count) {
  return Array.from({ length: count }, () => '')
}

async function load() {
  state.value = 'loading'
  result.value = null
  error.value = null
  pendingKey.value = null
  try {
    experiment.value = await api.get(`/experiments/${experimentId.value}`)
    history.value = await api.get(
      `/me/experiment-attempts?experiment_id=${experimentId.value}&page_size=100`,
    )
    answers.value = emptyAnswers(checkpoints.value.length)
    state.value = 'ready'
  } catch (err) {
    loadError.value = err.message
    state.value = 'error'
  }
}

function setAnswer(index, value) {
  pendingKey.value = null
  const next = [...answers.value]
  next[index] = value
  answers.value = next
}

function answerPayload() {
  return answers.value.map((value) => (value === '' ? null : Number(value)))
}

async function submit() {
  const values = answerPayload()
  if (values.some((value) => value === null || Number.isNaN(value))) {
    error.value = '请为每一拍填写一个状态值'
    return
  }
  submitting.value = true
  error.value = null
  // 同一份提交重试时复用 key（幂等）；换内容时下面会作废
  if (pendingKey.value === null) pendingKey.value = crypto.randomUUID()
  try {
    result.value = await api.post(`/experiments/${experimentId.value}/attempts`, {
      experiment_version: experiment.value.version,
      predictions: values,
      request_key: pendingKey.value,
    })
    pendingKey.value = null
    try {
      history.value = await api.get(
        `/me/experiment-attempts?experiment_id=${experimentId.value}&page_size=100`,
      )
    } catch {
      error.value = '提交已保存，记录列表暂时无法更新，请稍后刷新页面。'
    }
  } catch (err) {
    error.value = err.message
    // 业务错误（版本过期、字段错误、key 冲突）说明这次内容已作废，需要新 key；
    // 网络类失败保留 key，重试时服务器会返回同一条记录
    if (err instanceof ApiError) {
      pendingKey.value = null
      if (err.code === 'VERSION_CONFLICT') {
        await load()
        error.value = err.message
      }
    }
  } finally {
    submitting.value = false
  }
}

function reset() {
  result.value = null
  error.value = null
  pendingKey.value = null
  answers.value = emptyAnswers(checkpoints.value.length)
}

watch(experimentId, load, { immediate: true })
</script>

<template>
  <div class="experiment-page">
    <StatePanel v-if="state === 'loading'" kind="loading" title="正在读取实验" />
    <StatePanel v-else-if="state === 'error'" kind="error" title="实验无法读取" :description="loadError" />

    <template v-else>
      <PageHeader
        :eyebrow="modelLabel(simulatorType)"
        :title="experiment.title"
        description="输入序列由服务器固定；逐拍填写每个有效上升沿之后的 Q，提交后由服务器判分。"
      >
        <template #actions>
          <RouterLink class="button button--secondary" :to="{ name: 'student-experiments' }">返回实验中心</RouterLink>
        </template>
      </PageHeader>

      <SectionCard title="实验条件">
        <dl class="conditions">
          <div><dt>初态 Q</dt><dd class="mono">{{ formatBits(experiment.config.initial_q ?? 0, simulatorType) }}</dd></div>
          <div v-if="experiment.config.modulus"><dt>模数</dt><dd class="mono">{{ experiment.config.modulus }}</dd></div>
          <div><dt>检查点数</dt><dd class="mono">{{ checkpoints.length }} 拍</dd></div>
          <div><dt>实验版本</dt><dd class="mono">{{ experiment.version }}</dd></div>
        </dl>
        <pre class="steps">{{ experiment.steps_md }}</pre>
      </SectionCard>

      <SectionCard title="固定输入序列">
        <div class="table-scroll">
          <table>
            <thead>
              <tr><th scope="col">序号</th><th scope="col">操作</th><th scope="col">输入</th></tr>
            </thead>
            <tbody>
              <tr v-for="(event, index) in experiment.input_sequence" :key="index">
                <td>{{ index + 1 }}</td>
                <td>{{ event.op === 'set' ? '设置输入' : event.op === 'toggle_clock' ? '切换时钟' : '复位到初态' }}</td>
                <td class="mono">{{ inputsText(event.inputs) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </SectionCard>

      <SectionCard title="逐拍预测">
        <p class="hint">
          下面每次时钟上升沿各算一拍；请填写那一拍之后 Q 的十进制值
          （{{ simulatorType === 'd' || simulatorType === 'jk' ? '0 或 1' : '0—15' }}）。
        </p>
        <ol class="predictions">
          <li v-for="checkpoint in checkpoints" :key="checkpoint.index">
            <span class="predictions__label">{{ checkpointLabel(checkpoint.index) }}</span>
            <span class="predictions__inputs mono">{{ inputsText(checkpoint.inputs) }}</span>
            <input
              type="number"
              :min="range.min"
              :max="range.max"
              :value="answers[checkpoint.index]"
              :aria-label="checkpointLabel(checkpoint.index)"
              :data-checkpoint="checkpoint.index"
              @input="setAnswer(checkpoint.index, $event.target.value)"
            />
          </li>
        </ol>

        <p v-if="error" class="error" role="alert">{{ error }}</p>

        <div class="actions">
          <button class="button button--primary" type="button" :disabled="submitting || result !== null" @click="submit">
            <AppIcon name="check" :size="17" /> {{ submitting ? '提交中…' : '提交预测' }}
          </button>
          <button class="button button--secondary" type="button" :disabled="submitting" @click="reset">重新作答</button>
        </div>
      </SectionCard>

      <SectionCard v-if="result" title="提交结果">
        <p class="result-head">
          <StatusBadge :tone="resultTone(result)">{{ result.passed ? '通过' : '未通过' }}</StatusBadge>
          <strong>{{ resultSummary(result) }}</strong>
          <span class="hint">实验版本 {{ result.experiment_version }} · 共 {{ result.actual.length }} 拍</span>
        </p>

        <div class="table-scroll">
          <table>
            <thead>
              <tr>
                <th scope="col">拍</th><th scope="col">该拍输入</th><th scope="col">你填的</th>
                <th scope="col">正确答案</th><th scope="col">说明</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="checkpoint in checkpoints" :key="`r-${checkpoint.index}`">
                <td>{{ checkpointLabel(checkpoint.index) }}</td>
                <td class="mono">{{ inputsText(checkpoint.inputs) }}</td>
                <td class="mono">{{ formatBits(result.actual[checkpoint.index] ?? 0, result.simulator_type ?? simulatorType) }}</td>
                <td class="mono">{{ formatBits(result.expected[checkpoint.index] ?? 0, result.simulator_type ?? simulatorType) }}</td>
                <td>
                  <StatusBadge v-if="wrong.has(checkpoint.index)" tone="danger">错误</StatusBadge>
                  <StatusBadge v-else tone="success">正确</StatusBadge>
                  <span class="explain">{{ result.explanations[checkpoint.index] }}</span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <div class="actions">
          <button class="button button--primary" type="button" @click="reset">再做一次</button>
          <RouterLink class="button button--secondary" :to="{ name: 'student-attempts' }">查看全部记录</RouterLink>
        </div>
      </SectionCard>

      <SectionCard :title="`本实验记录（${history.length} 次）`">
        <div v-if="history.length === 0" class="empty">还没有提交过这个实验。</div>
        <ul v-else class="history-list">
          <li v-for="attempt in history" :key="attempt.id">
            <StatusBadge :tone="resultTone(attempt)">{{ attempt.passed ? '通过' : resultSummary(attempt) }}</StatusBadge>
            <span>{{ attemptSummary(attempt, attempt.simulator_type ?? simulatorType) }}</span>
            <span class="mono hint">版本 {{ attempt.experiment_version }}</span>
          </li>
        </ul>
      </SectionCard>
    </template>
  </div>
</template>

<style scoped>
.experiment-page { width: 100%; }
.experiment-page .section-card { margin-bottom: var(--space-4); }
.conditions { display: flex; gap: var(--space-5); flex-wrap: wrap; margin: 0 0 var(--space-3); }
.conditions div { display: grid; gap: 2px; }
.conditions dt { font-size: var(--font-size-xs); color: var(--color-text-secondary); }
.conditions dd { margin: 0; font-weight: 700; }
.mono { font-family: var(--font-mono); }
.steps { margin: 0; white-space: pre-wrap; font: inherit; font-size: var(--font-size-sm); }
.table-scroll { overflow-x: auto; }
.table-scroll table { min-width: 32rem; }
.predictions { list-style: none; padding: 0; margin: 0 0 var(--space-3); display: grid; gap: var(--space-2); }
.predictions li { display: flex; align-items: center; gap: var(--space-3); }
.predictions__label { min-width: 5rem; font-weight: 700; }
.predictions__inputs { min-width: 9rem; color: var(--color-text-secondary); font-size: var(--font-size-sm); }
.predictions input { width: 6rem; padding: var(--space-2); border: 1px solid var(--color-border); border-radius: var(--radius-sm); font-family: var(--font-mono); }
.actions { display: flex; gap: var(--space-3); flex-wrap: wrap; margin-top: var(--space-3); }
.result-head { display: flex; align-items: center; gap: var(--space-3); flex-wrap: wrap; }
.explain { display: block; margin-top: 2px; color: var(--color-text-secondary); font-size: var(--font-size-xs); }
.history-list { list-style: none; padding: 0; margin: 0; display: grid; gap: var(--space-2); }
.history-list li { display: flex; align-items: center; gap: var(--space-3); padding: var(--space-2) 0; border-bottom: 1px solid var(--color-border); font-size: var(--font-size-sm); }
.history-list li:last-child { border-bottom: 0; }
.empty { color: var(--color-text-secondary); }
.error { color: var(--color-danger); }
</style>
