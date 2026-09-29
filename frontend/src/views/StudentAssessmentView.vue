<script setup>
/**
 * 学生作答（SPEC-009 E043—E045）。
 *
 * 题目来自服务器投影：不含答案与解析，前端隐藏不是保护手段。
 * 保存与最终提交分两步：先等保存回执，再提交判分；保存失败就停止提交。
 */
import { computed, onMounted, ref } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'

import { api } from '@/api/client'
import PageHeader from '@/components/ui/PageHeader.vue'
import SectionCard from '@/components/ui/SectionCard.vue'
import StatePanel from '@/components/ui/StatePanel.vue'
import StatusBadge from '@/components/ui/StatusBadge.vue'
import {
  ASSESSMENT_STATE_LABEL,
  QUESTION_TYPE_LABEL,
  selectedFor,
  toggleSelection,
  unansweredCount,
} from '@/utils/assessment'

const route = useRoute()
const router = useRouter()
const assessmentId = Number(route.params.id)

const assessment = ref(null)
const submission = ref(null)
const answers = ref({})
const saving = ref(false)
const submitting = ref(false)
const loading = ref(true)
const loadError = ref(null)
const error = ref(null)
const notice = ref(null)
const lastSavedAt = ref(null)

const items = computed(() => assessment.value?.items ?? [])
const missing = computed(() => unansweredCount(items.value, payloadAnswers()))
const closed = computed(() => assessment.value?.effective_state === 'closed')

function payloadAnswers() {
  return Object.entries(answers.value).map(([itemId, selected]) => ({
    item_id: Number(itemId),
    selected,
  }))
}

function selected(itemId) {
  return answers.value[itemId] ?? []
}

function choose(item, key) {
  answers.value = {
    ...answers.value,
    [item.id]: toggleSelection(selected(item.id), key, item.type === 'multiple'),
  }
}

async function load() {
  loading.value = true
  loadError.value = null
  try {
    const detail = await api.get(`/assessments/${assessmentId}`)
    assessment.value = detail
    if (detail.effective_state === 'upcoming') return
    // E043 是幂等的：已开始过就返回原草稿（含已保存答案）。
    // 已提交、或测评已结束（草稿会被读取时的幂等最终化接管）都转到结果页。
    const started = await api.post(`/assessments/${assessmentId}/submissions`, {})
    if (started.status === 'submitted' || detail.effective_state === 'closed') {
      await router.replace({
        name: 'student-result',
        params: { submissionId: started.id },
        query: { assessment: assessmentId },
      })
      return
    }
    submission.value = started
    const restored = {}
    for (const entry of started.answers) {
      restored[entry.item_id] = entry.selected
    }
    answers.value = restored
    lastSavedAt.value = started.answers.length ? started.saved_at : null
  } catch (err) {
    loadError.value = err.message
  } finally {
    loading.value = false
  }
}

async function save() {
  saving.value = true
  error.value = null
  notice.value = null
  try {
    submission.value = await api.put(`/submissions/${submission.value.id}/answers`, {
      version: submission.value.version,
      answers: payloadAnswers(),
    })
    lastSavedAt.value = submission.value.saved_at
    notice.value = `已保存（${submission.value.saved_at}）`
    return true
  } catch (err) {
    error.value = `保存失败：${err.message}。未提交，请重试。`
    return false
  } finally {
    saving.value = false
  }
}

async function submit() {
  error.value = null
  notice.value = null
  submitting.value = true
  try {
    const saved = await save()
    if (!saved) return
    await api.post(`/submissions/${submission.value.id}/finalization`, {
      version: submission.value.version,
    })
    await router.push({
      name: 'student-result',
      params: { submissionId: submission.value.id },
      query: { assessment: assessmentId },
    })
  } catch (err) {
    error.value = err.message
  } finally {
    submitting.value = false
  }
}

onMounted(load)
</script>

<template>
  <div class="page">
    <PageHeader
      eyebrow="习题训练"
      title="作答"
      :description="assessment ? assessment.title : '正在读取测评'"
    >
      <template #actions>
        <RouterLink class="button button--secondary" :to="{ name: 'student-practice' }">
          返回练习列表
        </RouterLink>
      </template>
    </PageHeader>

    <StatePanel v-if="loading" kind="loading" title="正在读取题目" />
    <StatePanel v-else-if="loadError" kind="error" title="无法开始作答" :description="loadError" />

    <template v-else-if="assessment">
      <p v-if="notice" class="success">{{ notice }}</p>
      <p v-if="error" class="error" role="alert">{{ error }}</p>

      <SectionCard>
        <div class="meta">
          <span>{{ items.length }} 题 · 总分 {{ assessment.total_score }}</span>
          <StatusBadge :tone="closed ? 'neutral' : 'success'">
            {{ ASSESSMENT_STATE_LABEL[assessment.effective_state] ?? assessment.effective_state }}
          </StatusBadge>
          <span v-if="assessment.ends_at" class="hint">截止 {{ assessment.ends_at }}</span>
          <span class="hint">未作答 {{ missing }} 题</span>
        </div>

        <StatePanel
          v-if="assessment.effective_state === 'upcoming'"
          title="测评尚未开始"
          description="开始时间之前只显示活动概要，题目在开始后才下发。"
        />
        <StatePanel
          v-else-if="closed"
          title="测评已结束"
          description="已结束的测评不能继续作答；若已保存过草稿，服务端会按最后一次保存判分。"
        />

        <ol v-else class="questions">
          <li v-for="item in items" :key="item.id">
            <div class="question-head">
              <strong>{{ item.position }}. {{ item.stem_md }}</strong>
              <span class="badge">{{ QUESTION_TYPE_LABEL[item.type] ?? item.type }}</span>
              <span class="hint">{{ item.points }} 分</span>
            </div>
            <div class="options">
              <label v-for="option in item.options" :key="option.key" class="option">
                <input
                  :type="item.type === 'multiple' ? 'checkbox' : 'radio'"
                  :name="`item-${item.id}`"
                  :checked="selected(item.id).includes(option.key)"
                  @change="choose(item, option.key)"
                />
                <span class="option-key">{{ option.key }}</span>
                <span>{{ option.label }}</span>
              </label>
            </div>
          </li>
        </ol>

        <div v-if="!closed && assessment.effective_state !== 'upcoming'" class="actions">
          <button class="button button--secondary" type="button" :disabled="saving || submitting" @click="save">
            {{ saving ? '保存中…' : '保存草稿' }}
          </button>
          <button class="primary" type="button" :disabled="saving || submitting" @click="submit">
            {{ submitting ? '提交中…' : '提交并判分' }}
          </button>
          <span v-if="lastSavedAt" class="hint">最后保存 {{ lastSavedAt }}</span>
        </div>
      </SectionCard>
    </template>
  </div>
</template>

<style scoped>
.meta {
  display: flex;
  align-items: center;
  gap: var(--space-4);
  flex-wrap: wrap;
  margin-bottom: var(--space-4);
}

.questions {
  margin: 0;
  padding-left: 1.25rem;
}

.questions li {
  margin-bottom: var(--space-6);
}

.question-head {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  flex-wrap: wrap;
  margin-bottom: var(--space-2);
}

.options {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.option {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-2) var(--space-3);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  cursor: pointer;
}

.option-key {
  font-family: var(--font-mono);
  font-weight: 700;
  color: var(--color-primary);
}

.actions {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  margin-top: var(--space-4);
}
</style>
