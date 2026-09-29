<script setup>
/**
 * 学生结果页（SPEC-009 E046）。
 *
 * Result 模型只带条目 ID、作答、判定与解析，不带题干与选项，因此链接方会把
 * 测评 ID 放到 query.assessment，页面再取一次题目投影用于回显；没有该参数时
 * 退化为按条目展示，不伪造题干。
 */
import { computed, onMounted, ref } from 'vue'
import { RouterLink, useRoute } from 'vue-router'

import { api } from '@/api/client'
import PageHeader from '@/components/ui/PageHeader.vue'
import SectionCard from '@/components/ui/SectionCard.vue'
import StatePanel from '@/components/ui/StatePanel.vue'
import StatusBadge from '@/components/ui/StatusBadge.vue'
import { QUESTION_TYPE_LABEL, formatScore, selectionText } from '@/utils/assessment'

const route = useRoute()
const submissionId = Number(route.params.submissionId)
const assessmentId = route.query.assessment ? Number(route.query.assessment) : null

const result = ref(null)
const items = ref([])
const loading = ref(true)
const loadError = ref(null)

const wrongCount = computed(
  () => (result.value?.items ?? []).filter((item) => item.correct === false).length,
)

function itemMeta(itemId) {
  return items.value.find((item) => item.id === itemId) ?? null
}

function stem(itemId) {
  const meta = itemMeta(itemId)
  return meta ? meta.stem_md : `条目 #${itemId}`
}

function typeLabel(itemId) {
  const meta = itemMeta(itemId)
  return meta ? QUESTION_TYPE_LABEL[meta.type] ?? meta.type : null
}

function options(itemId) {
  return itemMeta(itemId)?.options ?? []
}

async function load() {
  loading.value = true
  loadError.value = null
  try {
    result.value = await api.get(`/submissions/${submissionId}/result`)
    if (assessmentId) {
      try {
        const detail = await api.get(`/assessments/${assessmentId}`)
        items.value = detail.items ?? []
      } catch {
        items.value = [] // 题目投影取不到时按条目展示即可，不影响成绩本身
      }
    }
  } catch (err) {
    loadError.value = err.message
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<template>
  <div class="page">
    <PageHeader eyebrow="习题训练" title="作答结果">
      <template #actions>
        <RouterLink class="button button--secondary" :to="{ name: 'student-practice' }">
          返回练习列表
        </RouterLink>
      </template>
    </PageHeader>

    <StatePanel v-if="loading" kind="loading" title="正在读取结果" />
    <StatePanel v-else-if="loadError" kind="error" title="无法读取结果" :description="loadError" />

    <template v-else-if="result">
      <SectionCard>
        <div class="summary">
          <div>
            <span class="eyebrow">得分</span>
            <p class="score">{{ formatScore(result.score, result.total_score) }}</p>
          </div>
          <StatusBadge :tone="result.feedback_available ? 'success' : 'warning'">
            {{ result.feedback_available ? '反馈已公开' : '等待讲评' }}
          </StatusBadge>
          <span v-if="result.feedback_available && wrongCount > 0" class="hint">
            本次答错 {{ wrongCount }} 题，可在错题本重练。
          </span>
        </div>
        <p v-if="!result.feedback_available" class="hint">
          教师公开反馈前只显示你自己的作答，不显示对错、答案与解析。
        </p>
      </SectionCard>

      <SectionCard title="逐题回顾">
        <ol class="review">
          <li v-for="entry in result.items" :key="entry.item_id">
            <div class="review-head">
              <strong>{{ stem(entry.item_id) }}</strong>
              <span v-if="typeLabel(entry.item_id)" class="badge">{{ typeLabel(entry.item_id) }}</span>
              <StatusBadge v-if="result.feedback_available" :tone="entry.correct ? 'success' : 'danger'">
                {{ entry.correct ? '答对' : '答错' }}
                <template v-if="entry.awarded_points !== undefined">· {{ entry.awarded_points }} 分</template>
              </StatusBadge>
              <span v-else class="badge">未公开</span>
            </div>
            <p class="line">我的作答：{{ selectionText(options(entry.item_id), entry.selected) }}</p>
            <template v-if="result.feedback_available">
              <p class="line">正确答案：{{ selectionText(options(entry.item_id), entry.answer) }}</p>
              <p v-if="entry.explanation_md" class="explanation">{{ entry.explanation_md }}</p>
            </template>
          </li>
        </ol>
      </SectionCard>

      <SectionCard>
        <RouterLink class="button button--primary" :to="{ name: 'student-mistakes' }">
          去错题本重练
        </RouterLink>
      </SectionCard>
    </template>
  </div>
</template>

<style scoped>
.summary {
  display: flex;
  align-items: center;
  gap: var(--space-4);
  flex-wrap: wrap;
}

.score {
  margin: 0;
  font-size: var(--font-size-xl);
  font-weight: 800;
}

.review {
  margin: 0;
  padding-left: 1.25rem;
}

.review li {
  margin-bottom: var(--space-5);
}

.review-head {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  flex-wrap: wrap;
  margin-bottom: var(--space-2);
}

.line {
  margin: 0 0 var(--space-1);
  font-size: var(--font-size-sm);
}

.explanation {
  margin: var(--space-2) 0 0;
  padding: var(--space-3);
  border-left: 3px solid var(--color-primary);
  background: var(--color-grid-surface);
  font-size: var(--font-size-sm);
  color: var(--color-text-secondary);
}
</style>
