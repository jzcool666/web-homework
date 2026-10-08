<script setup>
import { initialClassId } from '@/utils/overview'
/**
 * 约束智能组卷（SPEC-011，E062）。
 *
 * 教师选班级、题量、每难度配额与知识点下限量后生成 Assessment 草稿；
 * 求解状态、覆盖与所选题号由服务器返回。无解（422 INFEASIBLE_PAPER）与
 * 超时（503 SOLVER_TIMEOUT）分开提示，不把超时当作题库无解。
 */
import { computed, onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'

import { api } from '@/api/client'
import PageHeader from '@/components/ui/PageHeader.vue'
import SectionCard from '@/components/ui/SectionCard.vue'
import StatePanel from '@/components/ui/StatePanel.vue'
import StatusBadge from '@/components/ui/StatusBadge.vue'

const classes = ref([])
const classId = ref('')
const knowledgePoints = ref([])
const loading = ref(false)
const error = ref(null)
const notice = ref(null)
const result = ref(null)
const constraints = ref([])

const kindOptions = [
  { value: 'quiz', label: '随堂测' },
  { value: 'homework', label: '作业' },
  { value: 'exam', label: '考试' },
]

const form = ref({
  kind: 'quiz',
  title: '',
  count: 10,
  difficulty_counts: { easy: 4, medium: 4, hard: 2 },
  knowledge_minimums: [],
  seed: 1,
})

const difficultySum = computed(
  () =>
    Number(form.value.difficulty_counts.easy || 0) +
    Number(form.value.difficulty_counts.medium || 0) +
    Number(form.value.difficulty_counts.hard || 0),
)

const sumMatches = computed(() => difficultySum.value === Number(form.value.count))

const selectedKnowledgeIds = computed(() =>
  form.value.knowledge_minimums.map((row) => Number(row.knowledge_id)),
)

function knowledgeTitle(id) {
  return knowledgePoints.value.find((point) => point.id === Number(id))?.title ?? `#${id}`
}

function addMinimum() {
  const used = new Set(selectedKnowledgeIds.value)
  const next = knowledgePoints.value.find((point) => !used.has(point.id))
  if (!next) return
  form.value.knowledge_minimums.push({ knowledge_id: next.id, min_count: 1 })
}

function removeMinimum(index) {
  form.value.knowledge_minimums.splice(index, 1)
}

async function loadClasses() {
  classes.value = await api.get('/classes?page_size=100')
  if (!classId.value) classId.value = initialClassId(classes.value)
}

async function loadKnowledgePoints() {
  knowledgePoints.value = await api.get('/knowledge-points?published=true&page_size=100')
}

async function generate() {
  error.value = null
  notice.value = null
  result.value = null
  constraints.value = []
  if (!sumMatches.value) {
    error.value = `难度配额之和 ${difficultySum.value} 必须等于题量 ${form.value.count}`
    return
  }
  loading.value = true
  try {
    result.value = await api.post('/paper-generations', {
      class_id: Number(classId.value),
      title: form.value.title,
      kind: form.value.kind,
      count: Number(form.value.count),
      difficulty_counts: {
        easy: Number(form.value.difficulty_counts.easy || 0),
        medium: Number(form.value.difficulty_counts.medium || 0),
        hard: Number(form.value.difficulty_counts.hard || 0),
      },
      knowledge_minimums: form.value.knowledge_minimums.map((row) => ({
        knowledge_id: Number(row.knowledge_id),
        min_count: Number(row.min_count),
      })),
      seed: Number(form.value.seed),
    })
    notice.value = `已生成草稿 #${result.value.assessment_id}，共 ${result.value.selected_ids.length} 题`
  } catch (err) {
    if (err.code === 'INFEASIBLE_PAPER') {
      constraints.value = err.details?.constraints ?? []
      error.value = '题库无法满足当前条件（已证明无解），请调整难度配额或知识点下限量'
    } else if (err.code === 'SOLVER_TIMEOUT') {
      error.value = '组卷求解超时（题库未必无解），请稍后重试或放宽约束'
    } else {
      error.value = err.message
    }
  } finally {
    loading.value = false
  }
}

function solverTone(status) {
  return status === 'optimal' ? 'success' : 'warning'
}

onMounted(async () => {
  try {
    await Promise.all([loadClasses(), loadKnowledgePoints()])
  } catch (err) {
    error.value = err.message
  }
})
</script>

<template>
  <div class="page">
    <PageHeader icon="spark" :steps="['设置条件', '查看组卷结果', '采用后发布']"
      eyebrow="智能工具"
      title="约束智能组卷"
      description="在已发布题库（最多 500 题）中按题量、难度配额与知识点下限量选题，参考本班历史首答提升针对性；相同种子与题库必然得到同一结果。生成的是草稿，需在测评页确认后发布。"
    />

    <p v-if="notice" class="success">{{ notice }}</p>
    <p v-if="error" class="error" role="alert">{{ error }}</p>
    <ul v-if="constraints.length > 0" class="constraints">
      <li v-for="(item, index) in constraints" :key="index">
        <template v-if="item.kind === 'difficulty'">
          难度 {{ item.difficulty }}：需要 {{ item.required }} 题，题库仅 {{ item.available }} 题
        </template>
        <template v-else-if="item.kind === 'knowledge'">
          知识点 {{ knowledgeTitle(item.knowledge_id) }}：需要覆盖 {{ item.required }} 题，题库仅 {{ item.available }} 题
        </template>
        <template v-else>{{ item.message }}</template>
      </li>
    </ul>

    <SectionCard title="组卷条件">
      <form class="generate-form" @submit.prevent="generate">
        <div class="form-fields">
        <div class="field">
          <label for="g_class">班级</label>
          <select id="g_class" v-model="classId" required>
            <option value="" disabled>请选择班级</option>
            <option v-for="item in classes" :key="item.id" :value="item.id">{{ item.name }}</option>
          </select>
        </div>
        <div class="field">
          <label for="g_kind">类型</label>
          <select id="g_kind" v-model="form.kind">
            <option v-for="option in kindOptions" :key="option.value" :value="option.value">
              {{ option.label }}
            </option>
          </select>
        </div>
        <div class="field">
          <label for="g_title">标题</label>
          <input id="g_title" v-model="form.title" maxlength="100" required />
        </div>
        <div class="field">
          <label for="g_count">题量（1—30）</label>
          <input id="g_count" v-model.number="form.count" type="number" min="1" max="30" required />
        </div>
        <div class="field">
          <label for="g_easy">基础题</label>
          <input id="g_easy" v-model.number="form.difficulty_counts.easy" type="number" min="0" />
        </div>
        <div class="field">
          <label for="g_medium">进阶题</label>
          <input id="g_medium" v-model.number="form.difficulty_counts.medium" type="number" min="0" />
        </div>
        <div class="field">
          <label for="g_hard">挑战题</label>
          <input id="g_hard" v-model.number="form.difficulty_counts.hard" type="number" min="0" />
        </div>
        <div class="field">
          <label for="g_seed">随机种子</label>
          <input id="g_seed" v-model.number="form.seed" type="number" required />
        </div>
        </div>
      <p class="hint" :class="{ 'hint-error': !sumMatches }">
        难度配额之和 {{ difficultySum }} / 题量 {{ form.count }}
        <template v-if="!sumMatches">（必须相等）</template>
      </p>

      <div class="minimums">
        <div class="minimums-head">
          <span>知识点下限量（最多 18 个）</span>
          <button class="button button--secondary" type="button" @click="addMinimum" :disabled="knowledgePoints.length === 0">
            添加
          </button>
        </div>
        <p v-if="form.knowledge_minimums.length === 0" class="hint">
          未设置时只约束题量与难度配额。
        </p>
        <div
          v-for="(row, index) in form.knowledge_minimums"
          :key="index"
          class="minimum-row"
        >
          <select v-model.number="row.knowledge_id">
            <option
              v-for="point in knowledgePoints"
              :key="point.id"
              :value="point.id"
              :disabled="selectedKnowledgeIds.includes(point.id) && point.id !== row.knowledge_id"
            >
              {{ point.title }}
            </option>
          </select>
          <input v-model.number="row.min_count" type="number" min="1" aria-label="最少覆盖题数" />
          <button class="button button--secondary" type="button" @click="removeMinimum(index)">移除</button>
        </div>
      </div>
      <div class="form-actions">
        <button class="primary" type="submit" :disabled="!classId || loading">
          {{ loading ? '正在求解…' : '生成草稿' }}
        </button>
      </div>
      </form>
    </SectionCard>

    <SectionCard v-if="result" title="生成结果">
      <div class="summary">
        <StatusBadge :tone="solverTone(result.solver_status)">
          {{ result.solver_status === 'optimal' ? '已证明最优' : '限时可行解' }}
        </StatusBadge>
        <span>种子 {{ result.seed }}</span>
        <span>题量 {{ result.selected_ids.length }}</span>
        <span>
          难度 基础{{ result.difficulty_counts.easy }} / 进阶{{ result.difficulty_counts.medium }} /
          挑战{{ result.difficulty_counts.hard }}
        </span>
        <RouterLink :to="{ name: 'teacher-assessment', params: { id: result.assessment_id } }">
          查看草稿 #{{ result.assessment_id }}
        </RouterLink>
      </div>

      <table v-if="result.coverage.length > 0" class="coverage">
        <thead>
          <tr>
            <th>知识点</th>
            <th>下限量</th>
            <th>实际覆盖</th>
            <th>满足</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in result.coverage" :key="row.knowledge_id">
            <td>{{ knowledgeTitle(row.knowledge_id) }}</td>
            <td>{{ row.min_count }}</td>
            <td>{{ row.selected_count }}</td>
            <td>
              <StatusBadge :tone="row.satisfied ? 'success' : 'warning'">
                {{ row.satisfied ? '是' : '否' }}
              </StatusBadge>
            </td>
          </tr>
        </tbody>
      </table>

      <p class="selected">所选题号：{{ result.selected_ids.join('、') }}</p>
      <p class="hint">
        草稿可在测评页调整题目与分值后发布；相同题库版本、历史分布与种子会得到同一选题。
      </p>
    </SectionCard>

    <StatePanel
      v-else-if="loading"
      kind="loading"
      title="正在求解"
      description="在已发布题库中按约束选题（限时 2 秒）"
    />
  </div>
</template>

<style scoped>
.generate-form { display: grid; grid-template-columns: minmax(0, 1fr); gap: 16px; }


.constraints {
  margin: 0 0 var(--space-3);
  padding-left: 1.2rem;
  color: var(--color-danger, #b3261e);
}

.minimums {
  margin-top: var(--space-4);
  border-top: 1px solid var(--color-border, #d8dbe0);
  padding-top: var(--space-3);
}

.minimums-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: var(--space-2);
}

.minimum-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 6rem auto;
  gap: var(--space-2);
  margin-bottom: var(--space-2);
  align-items: center;
}

.summary {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-3);
  align-items: center;
  margin-bottom: var(--space-3);
}

.coverage {
  margin-bottom: var(--space-3);
}

.hint-error {
  color: var(--color-danger, #b3261e);
}

.selected {
  font-family: var(--font-mono);
  font-size: var(--font-size-xs);
  word-break: break-all;
}
@media (max-width: 520px) {
  .minimum-row { grid-template-columns: minmax(0, 1fr) 5rem; }
  .minimum-row button { grid-column: 1 / -1; justify-self: end; }
}
</style>
