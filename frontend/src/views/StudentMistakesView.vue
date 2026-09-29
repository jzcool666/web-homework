<script setup>
/**
 * 学生错题本（SPEC-009 E047）。
 *
 * 接口只返回题目 ID、最近答错时间、最近一次已公开的判定、知识点与是否可重练，
 * 不含题干与答案，因此未公开反馈的题目不会在这里泄露。重练会把选中的题目
 * 作为 mistake_question_ids 交给自练接口。
 */
import { computed, onMounted, ref } from 'vue'
import { RouterLink, useRouter } from 'vue-router'

import { api } from '@/api/client'
import PageHeader from '@/components/ui/PageHeader.vue'
import SectionCard from '@/components/ui/SectionCard.vue'
import StatePanel from '@/components/ui/StatePanel.vue'
import StatusBadge from '@/components/ui/StatusBadge.vue'

const router = useRouter()
const mistakes = ref([])
const points = ref([])
const selected = ref([])
const filter = ref({ knowledge_id: '', resolved: '' })
const loading = ref(false)
const listError = ref(null)
const error = ref(null)
const notice = ref(null)

const reviewable = computed(() => mistakes.value.filter((row) => row.review_available))
const selectedReviewable = computed(() =>
  selected.value.filter((id) => reviewable.value.some((row) => row.question_id === id)),
)
const allSelected = computed(
  () =>
    reviewable.value.length > 0 &&
    selectedReviewable.value.length === reviewable.value.length,
)

function knowledgeNames(ids) {
  const map = new Map(points.value.map((point) => [point.id, point.title]))
  return (ids ?? []).map((id) => map.get(id) ?? `#${id}`).join('、') || '—'
}

function toggle(row) {
  const current = selected.value
  selected.value = current.includes(row.question_id)
    ? current.filter((id) => id !== row.question_id)
    : [...current, row.question_id]
}

function toggleAll() {
  selected.value = allSelected.value
    ? []
    : reviewable.value.map((row) => row.question_id)
}

async function load() {
  loading.value = true
  listError.value = null
  try {
    const params = new URLSearchParams({ page_size: '100' })
    if (filter.value.knowledge_id) params.set('knowledge_id', filter.value.knowledge_id)
    if (filter.value.resolved) params.set('resolved', filter.value.resolved)
    const [rows, pointList] = await Promise.all([
      api.get(`/me/mistakes?${params.toString()}`),
      points.value.length ? Promise.resolve(points.value) : api.get('/knowledge-points?page_size=100'),
    ])
    mistakes.value = rows
    points.value = pointList
    selected.value = []
  } catch (err) {
    listError.value = err.message
  } finally {
    loading.value = false
  }
}

async function retrySelected() {
  error.value = null
  notice.value = null
  if (selectedReviewable.value.length === 0) {
    error.value = '请先勾选可重练的错题'
    return
  }
  try {
    const practice = await api.post('/practice-sessions', {
      mistake_question_ids: selectedReviewable.value,
      count: selectedReviewable.value.length,
    })
    await router.push({ name: 'student-assessment', params: { id: practice.id } })
  } catch (err) {
    error.value = err.message
  }
}

onMounted(load)
</script>

<template>
  <div class="page">
    <PageHeader
      eyebrow="学习与练习"
      title="错题本"
      description="按题目记录最近一次已公开反馈的判定与最早答错时间。重练答对只会把状态改为已纠正，不会改变首答统计，历史错误仍然可查。"
    >
      <template #actions>
        <RouterLink class="button button--secondary" :to="{ name: 'student-practice' }">
          返回习题训练
        </RouterLink>
      </template>
    </PageHeader>

    <p v-if="notice" class="success">{{ notice }}</p>
    <p v-if="error" class="error" role="alert">{{ error }}</p>

    <SectionCard title="错题列表">
      <div class="filters">
        <div class="field">
          <label for="m_knowledge">知识点</label>
          <select id="m_knowledge" v-model="filter.knowledge_id" @change="load">
            <option value="">全部</option>
            <option v-for="point in points" :key="point.id" :value="point.id">
              {{ point.title }}
            </option>
          </select>
        </div>
        <div class="field">
          <label for="m_resolved">纠正状态</label>
          <select id="m_resolved" v-model="filter.resolved" @change="load">
            <option value="">全部</option>
            <option value="false">未纠正</option>
            <option value="true">已纠正</option>
          </select>
        </div>
        <button class="primary" type="button" @click="retrySelected">
          重练选中错题（{{ selectedReviewable.length }}）
        </button>
      </div>

      <StatePanel v-if="loading" kind="loading" title="正在读取错题" />
      <StatePanel v-else-if="listError" kind="error" title="错题加载失败" :description="listError" />
      <StatePanel
        v-else-if="mistakes.length === 0"
        title="暂无错题"
        description="提交过的题目在教师公开反馈后会出现在这里。"
      />
      <div v-else class="table-scroll">
        <table>
          <thead>
            <tr>
              <th>
                <input
                  type="checkbox"
                  :checked="allSelected"
                  aria-label="全选可重练错题"
                  @change="toggleAll"
                />
              </th>
              <th>题目</th>
              <th>知识点</th>
              <th>最近状态</th>
              <th>最近答错时间</th>
              <th>可重练</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in mistakes" :key="row.question_id">
              <td>
                <input
                  v-if="row.review_available"
                  type="checkbox"
                  :checked="selected.includes(row.question_id)"
                  :aria-label="`选择题目 ${row.question_id}`"
                  @change="toggle(row)"
                />
                <span v-else class="hint">—</span>
              </td>
              <td>#{{ row.question_id }}</td>
              <td>{{ knowledgeNames(row.knowledge_ids) }}</td>
              <td>
                <StatusBadge :tone="row.latest_correct ? 'success' : 'danger'">
                  {{ row.latest_correct ? '已纠正' : '未纠正' }}
                </StatusBadge>
              </td>
              <td>{{ row.last_wrong_at ?? '—' }}</td>
              <td>
                <StatusBadge :tone="row.review_available ? 'success' : 'warning'">
                  {{ row.review_available ? '可重练' : '题目不可用' }}
                </StatusBadge>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </SectionCard>
  </div>
</template>

<style scoped>
.filters {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(11rem, 1fr));
  gap: 0 var(--space-4);
  align-items: end;
  margin-bottom: var(--space-4);
}

.filters button {
  justify-self: start;
}
</style>
