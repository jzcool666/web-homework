<script setup>
/**
 * 测评详情：发布、进度、提前结束、公开反馈、讲评与投屏（SPEC-010）。
 *
 * 统计来自 E057，只含聚合值，不含学生身份；投屏模式进一步只显示聚合面板，
 * 不显示逐题答案，便于教师控制公开节奏。
 */
import { computed, onMounted, ref } from 'vue'
import { RouterLink, useRoute } from 'vue-router'

import { API_BASE, api } from '@/api/client'
import QuestionPicker from '@/components/QuestionPicker.vue'
import PageHeader from '@/components/ui/PageHeader.vue'
import SectionCard from '@/components/ui/SectionCard.vue'
import StatePanel from '@/components/ui/StatePanel.vue'
import StatusBadge from '@/components/ui/StatusBadge.vue'
import {
  ASSESSMENT_STATE_LABEL,
  KIND_LABEL,
  QUESTION_TYPE_LABEL,
  bucketWidth,
  formatRate,
  selectionText,
} from '@/utils/assessment'
import { localInputToUtc, utcToLocalInput } from '@/utils/attendance'

const route = useRoute()
const assessmentId = Number(route.params.id)

const assessment = ref(null)
const bank = ref([])
const stats = ref(null)
const editing = ref(false)
const draftItems = ref([])
const publishForm = ref({ starts_at: '', ends_at: '' })
const loading = ref(true)
const loadError = ref(null)
const listError = ref(null)
const error = ref(null)
const notice = ref(null)
const projecting = ref(false)

const items = computed(() => assessment.value?.items ?? [])
const isDraft = computed(() => assessment.value?.state === 'draft')
const isPublished = computed(() => assessment.value?.state === 'published')
const canRelease = computed(() => {
  const value = assessment.value
  if (!value || value.feedback_released) return false
  if (value.state === 'closed') return true
  return value.ends_at !== null && value.ends_at <= new Date().toISOString().replace(/\.\d{3}Z$/, 'Z')
})

const classId = computed(() => assessment.value?.class_id)
const csvHref = computed(
  () => `${API_BASE}/analytics/assessment?class_id=${classId.value}&assessment_id=${assessmentId}&format=csv`,
)
const overall = computed(() => stats.value?.assessments?.[0] ?? null)

function stateTone(state) {
  if (state === 'open') return 'success'
  if (state === 'upcoming') return 'warning'
  return 'neutral'
}

function itemStats(itemId) {
  return stats.value?.items?.find((row) => row.item_id === itemId) ?? null
}

function optionCount(itemId, key) {
  return itemStats(itemId)?.option_counts?.[key] ?? 0
}

function correctText(itemId) {
  const item = items.value.find((row) => row.id === itemId)
  if (!item?.answer) return '—'
  return selectionText(item.options, item.answer)
}

function labelOf(itemId, key) {
  const item = items.value.find((row) => row.id === itemId)
  return item?.options?.find((option) => option.key === key)?.label ?? key
}

async function run(action) {
  error.value = null
  notice.value = null
  try {
    await action()
    await load()
  } catch (err) {
    error.value = err.message
    await load().catch(() => {})
  }
}

async function load() {
  const detail = await api.get(`/assessments/${assessmentId}`)
  assessment.value = detail
  draftItems.value = detail.items.map((item) => ({ question_id: item.question_id, points: item.points }))
  if (detail.state === 'draft') {
    editing.value = true
  }
  if (detail.class_id) {
    try {
      stats.value = await api.get(
        `/analytics/assessment?class_id=${detail.class_id}&assessment_id=${assessmentId}`,
      )
    } catch (err) {
      stats.value = null
      listError.value = err.message
    }
  }
}

async function loadBank() {
  bank.value = await api.get('/questions?page_size=100')
}

async function publish() {
  await run(async () => {
    const starts = localInputToUtc(publishForm.value.starts_at)
    const ends = localInputToUtc(publishForm.value.ends_at)
    const updated = await api.post(`/assessments/${assessmentId}/publication`, {
      version: assessment.value.version,
      starts_at: starts,
      ends_at: ends,
    })
    notice.value = `已发布「${updated.title}」，名单与题目快照已冻结`
  })
}

async function saveItems() {
  await run(async () => {
    const updated = await api.patch(`/assessments/${assessmentId}`, {
      version: assessment.value.version,
      items: draftItems.value,
    })
    notice.value = `草稿已更新，共 ${updated.items.length} 题、${updated.total_score} 分`
    editing.value = false
  })
}

async function closeNow() {
  await run(async () => {
    const updated = await api.post(`/assessments/${assessmentId}/closure`, {
      version: assessment.value.version,
    })
    notice.value = `已结束，截止时间记为 ${updated.ends_at}`
  })
}

async function release() {
  await run(async () => {
    await api.post(`/assessments/${assessmentId}/feedback-release`, {
      version: assessment.value.version,
    })
    notice.value = '已公开反馈，学生现在可以看到分数、答案与解析'
  })
}

async function refreshStats() {
  error.value = null
  try {
    stats.value = await api.get(
      `/analytics/assessment?class_id=${classId.value}&assessment_id=${assessmentId}`,
    )
    notice.value = '统计已刷新'
  } catch (err) {
    error.value = err.message
  }
}

async function toggleProjection() {
  projecting.value = !projecting.value
  if (projecting.value) {
    await refreshStats().catch(() => {})
  }
}

onMounted(async () => {
  try {
    await load()
    await loadBank()
    if (assessment.value?.state === 'draft') {
      const now = new Date()
      publishForm.value = {
        starts_at: utcToLocalInput(new Date(now.getTime() - 60000).toISOString()),
        ends_at: utcToLocalInput(new Date(now.getTime() + 30 * 60000).toISOString()),
      }
      editing.value = true
    }
  } catch (err) {
    loadError.value = err.message
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div class="page">
    <PageHeader
      eyebrow="测评"
      :title="assessment ? assessment.title : '测评详情'"
      :description="assessment ? `${KIND_LABEL[assessment.kind] ?? assessment.kind} · 总分 ${assessment.total_score}` : ''"
    >
      <template v-if="!projecting" #actions>
        <RouterLink class="button button--secondary" :to="{ name: 'teacher-assessments' }">
          返回测评列表
        </RouterLink>
      </template>
    </PageHeader>

    <StatePanel v-if="loading" kind="loading" title="正在读取测评" />
    <StatePanel v-else-if="loadError" kind="error" title="无法读取测评" :description="loadError" />

    <template v-else-if="assessment">
      <p v-if="notice" class="success">{{ notice }}</p>
      <p v-if="error" class="error" role="alert">{{ error }}</p>

      <SectionCard v-if="!projecting" title="状态与操作">
        <div class="state-row">
          <StatusBadge :tone="stateTone(assessment.effective_state)">
            {{ ASSESSMENT_STATE_LABEL[assessment.effective_state] ?? assessment.effective_state }}
          </StatusBadge>
          <StatusBadge :tone="assessment.feedback_released ? 'success' : 'warning'">
            反馈{{ assessment.feedback_released ? '已公开' : '未公开' }}
          </StatusBadge>
          <span class="hint">{{ assessment.starts_at ?? '—' }} → {{ assessment.ends_at ?? '—' }}</span>
          <span class="hint">版本 v{{ assessment.version }}</span>
        </div>

        <form v-if="isDraft" class="publish-form" @submit.prevent="publish">
          <div class="field">
            <label for="p_starts">开始时间（本地）</label>
            <input id="p_starts" v-model="publishForm.starts_at" type="datetime-local" required />
          </div>
          <div class="field">
            <label for="p_ends">结束时间（本地）</label>
            <input id="p_ends" v-model="publishForm.ends_at" type="datetime-local" required />
          </div>
          <button class="primary" type="submit">发布并冻结</button>
        </form>

        <div class="actions">
          <button v-if="isPublished" class="button button--secondary" type="button" @click="closeNow">
            提前结束
          </button>
          <button v-if="canRelease" class="button button--secondary" type="button" @click="release">
            公开反馈
          </button>
          <button class="button button--secondary" type="button" @click="refreshStats">刷新统计</button>
          <a class="button button--secondary" :href="csvHref">导出 CSV</a>
          <button v-if="isDraft" class="link" type="button" @click="editing = !editing">
            {{ editing ? '收起选题' : '修改选题' }}
          </button>
          <button class="link" type="button" @click="toggleProjection">
            {{ projecting ? '退出投屏' : '投屏统计' }}
          </button>
        </div>
        <p class="hint">
          结束不等于公开：提前结束或自然截止后学生仍看不到分数与答案，直到点击「公开反馈」。
        </p>
      </SectionCard>

      <SectionCard v-if="isDraft && editing" title="草稿选题">
        <QuestionPicker v-model="draftItems" :questions="bank" />
        <button class="primary" type="button" @click="saveItems">保存草稿</button>
      </SectionCard>

      <SectionCard v-if="projecting" title="投屏统计（匿名聚合）">
        <button class="button button--secondary" type="button" @click="toggleProjection">退出投屏</button>
        <div v-if="overall" class="projection">
          <div class="projection__cell">
            <span class="eyebrow">已提交</span>
            <strong>{{ overall.submitted_count }} / {{ overall.roster_count }}</strong>
          </div>
          <div class="projection__cell">
            <span class="eyebrow">提交率</span>
            <strong>{{ formatRate(overall.submission_rate) }}</strong>
          </div>
          <div class="projection__cell">
            <span class="eyebrow">平均分</span>
            <strong>{{ overall.mean_percent === null ? '—' : `${overall.mean_percent}%` }}</strong>
          </div>
          <div class="projection__cell">
            <span class="eyebrow">白卷</span>
            <strong>{{ overall.blank_count }}</strong>
          </div>
        </div>
        <ul class="buckets">
          <li v-for="bucket in stats?.score_buckets ?? []" :key="bucket.range">
            <span class="bucket__label">{{ bucket.range }}</span>
            <span class="bucket__bar" :style="{ width: `${bucketWidth(bucket.count, stats?.score_buckets)}%` }"></span>
            <span class="bucket__count">{{ bucket.count }}</span>
          </li>
        </ul>
        <p class="hint">投屏只显示聚合结果，不含任何学生身份。</p>
      </SectionCard>

      <SectionCard v-if="!projecting" title="作答进度">
        <StatePanel v-if="listError" kind="error" title="统计加载失败" :description="listError" />
        <StatePanel
          v-else-if="!overall"
          title="暂无统计"
          description="发布后学生开始作答，这里会显示提交进度。"
        />
        <template v-else>
          <div class="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>名单人数</th>
                  <th>已提交</th>
                  <th>白卷</th>
                  <th>提交率</th>
                  <th>平均分</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td>{{ overall.roster_count }}</td>
                  <td>{{ overall.submitted_count }}</td>
                  <td>{{ overall.blank_count }}</td>
                  <td>{{ formatRate(overall.submission_rate) }}</td>
                  <td>{{ overall.mean_percent === null ? '—' : `${overall.mean_percent}%` }}</td>
                </tr>
              </tbody>
            </table>
          </div>
          <p class="hint">
            提交率分母为发布时固定的名单；未开始的学生不计入已提交，仍留在名单里。
          </p>
        </template>
      </SectionCard>

      <SectionCard v-if="!projecting" title="讲评与逐题统计">
        <p class="hint">
          逐题正确率分母是已提交人数（含漏答）；选项各计一次，漏答单列。
        </p>
        <ol class="review">
          <li v-for="item in items" :key="item.id">
            <div class="review__head">
              <strong>{{ item.position }}. {{ item.stem_md }}</strong>
              <span class="badge">{{ QUESTION_TYPE_LABEL[item.type] ?? item.type }}</span>
              <span class="hint">{{ item.points }} 分</span>
            </div>
            <ul class="review__options">
              <li v-for="option in item.options" :key="option.key">
                <span class="option-key">{{ option.key }}</span>
                <span class="option-label">{{ option.label }}</span>
                <span class="option-count">{{ optionCount(item.id, option.key) }} 人选</span>
              </li>
            </ul>
            <div class="review__stats">
              <span>正确率 {{ formatRate(itemStats(item.id)?.correct_rate) }}</span>
              <span>机会 {{ itemStats(item.id)?.answered_count ?? '—' }}</span>
              <span>正确 {{ itemStats(item.id)?.correct_count ?? '—' }}</span>
              <span>漏答 {{ itemStats(item.id)?.unanswered_count ?? '—' }}</span>
              <span>
                参考答案 {{ assessment.feedback_released ? correctText(item.id) : '（公开反馈后显示）' }}
              </span>
            </div>
          </li>
        </ol>
        <p v-if="items.length === 0" class="hint">该测评还没有题目。</p>
      </SectionCard>
    </template>
  </div>
</template>

<style scoped>
.state-row {
  display: flex;
  align-items: center;
  gap: var(--space-4);
  flex-wrap: wrap;
  margin-bottom: var(--space-4);
}

.publish-form {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(12rem, 1fr));
  gap: 0 var(--space-4);
  align-items: end;
  margin-bottom: var(--space-4);
}

.publish-form button {
  justify-self: start;
}

.actions {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  flex-wrap: wrap;
  margin-bottom: var(--space-2);
}

.projection {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(9rem, 1fr));
  gap: var(--space-4);
  margin-bottom: var(--space-5);
}

.projection__cell {
  padding: var(--space-4);
  border-radius: var(--radius-sm);
  background: var(--color-primary-soft);
}

.projection__cell strong {
  display: block;
  font-size: var(--font-size-xl);
}

.buckets {
  margin: 0;
  padding: 0;
  list-style: none;
}

.buckets li {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  margin-bottom: var(--space-2);
}

.bucket__label {
  width: 6rem;
  font-family: var(--font-mono);
  font-size: var(--font-size-sm);
}

.bucket__bar {
  height: 0.85rem;
  border-radius: 99px;
  background: var(--color-primary);
  min-width: 2px;
  transition: width 0.2s ease;
}

.bucket__count {
  font-weight: 700;
}

.review {
  margin: 0;
  padding-left: 1.25rem;
}

.review li {
  margin-bottom: var(--space-5);
}

.review__head {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  flex-wrap: wrap;
  margin-bottom: var(--space-2);
}

.review__options {
  margin: 0 0 var(--space-2);
  padding-left: var(--space-4);
  list-style: none;
}

.review__options li {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  margin-bottom: var(--space-1);
}

.option-key {
  font-family: var(--font-mono);
  font-weight: 700;
  color: var(--color-primary);
}

.option-label {
  flex: 1;
}

.option-count {
  color: var(--color-text-secondary);
  font-size: var(--font-size-sm);
}

.review__stats {
  display: flex;
  gap: var(--space-4);
  flex-wrap: wrap;
  font-size: var(--font-size-sm);
  color: var(--color-text-secondary);
}
</style>
