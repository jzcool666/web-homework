<script setup>
/**
 * 教师题库管理（SPEC-009 E035、E036）。
 *
 * 创建与编辑共用一个表单：`editing` 为 null 时是新建，否则是修改。
 * 修改必须带 version，服务端仍然只能本人改；其他教师只能读已发布共享题。
 */
import { computed, onMounted, ref } from 'vue'

import { api } from '@/api/client'
import PageHeader from '@/components/ui/PageHeader.vue'
import SectionCard from '@/components/ui/SectionCard.vue'
import StatePanel from '@/components/ui/StatePanel.vue'
import StatusBadge from '@/components/ui/StatusBadge.vue'
import {
  DIFFICULTY_LABEL,
  QUESTION_TYPE_LABEL,
  defaultOptions,
  nextOptionKey,
  normalizeAnswer,
  toggleSelection,
} from '@/utils/assessment'

const questions = ref([])
const points = ref([])
const loading = ref(false)
const listError = ref(null)
const error = ref(null)
const notice = ref(null)

const filter = ref({ type: '', difficulty: '', knowledge_id: '', q: '' })
const editing = ref(null)
const form = ref(blankForm())

function blankForm() {
  return {
    type: 'single',
    stem_md: '',
    options: defaultOptions('single'),
    answer: [],
    explanation_md: '',
    difficulty: 1,
    knowledge_ids: [],
    published: true,
  }
}

const editingVersion = ref(1)
const editingLabel = computed(() => (editing.value === null ? '新建题目' : `修改题目 #${editing.value}`))

function knowledgeNames(ids) {
  const map = new Map(points.value.map((point) => [point.id, point.title]))
  return (ids ?? []).map((id) => map.get(id) ?? `#${id}`).join('、')
}

function onTypeChange() {
  form.value.options = defaultOptions(form.value.type)
  form.value.answer = []
}

function addOption() {
  const keys = form.value.options.map((option) => option.key)
  form.value.options.push({ key: nextOptionKey(keys), label: '' })
}

function removeOption(index) {
  form.value.options.splice(index, 1)
  form.value.answer = normalizeAnswer(
    form.value.type,
    form.value.answer,
    form.value.options.map((option) => option.key),
  )
}

function toggleAnswer(key) {
  form.value.answer = toggleSelection(form.value.answer, key, form.value.type === 'multiple')
}

function toggleKnowledge(id) {
  const current = form.value.knowledge_ids
  if (current.includes(id)) {
    form.value.knowledge_ids = current.filter((item) => item !== id)
  } else if (current.length < 3) {
    form.value.knowledge_ids = [...current, id]
  }
}

async function run(action) {
  error.value = null
  notice.value = null
  try {
    await action()
  } catch (err) {
    error.value = err.message
  }
}

async function loadQuestions() {
  loading.value = true
  listError.value = null
  try {
    const params = new URLSearchParams({ page_size: '100' })
    if (filter.value.type) params.set('type', filter.value.type)
    if (filter.value.difficulty) params.set('difficulty', filter.value.difficulty)
    if (filter.value.knowledge_id) params.set('knowledge_id', filter.value.knowledge_id)
    if (filter.value.q) params.set('q', filter.value.q)
    questions.value = await api.get(`/questions?${params.toString()}`)
  } catch (err) {
    listError.value = err.message
  } finally {
    loading.value = false
  }
}

async function loadPoints() {
  points.value = await api.get('/knowledge-points?page_size=100')
}

function startCreate() {
  editing.value = null
  form.value = blankForm()
}

function startEdit(question) {
  editing.value = question.id
  form.value = {
    type: question.type,
    stem_md: question.stem_md,
    options: question.options.map((option) => ({ ...option })),
    answer: [...question.answer],
    explanation_md: question.explanation_md,
    difficulty: question.difficulty,
    knowledge_ids: [...question.knowledge_ids],
    published: question.published,
  }
}

async function submitForm() {
  await run(async () => {
    const payload = {
      type: form.value.type,
      stem_md: form.value.stem_md,
      options: form.value.options,
      answer: form.value.answer,
      explanation_md: form.value.explanation_md,
      difficulty: Number(form.value.difficulty),
      knowledge_ids: form.value.knowledge_ids,
      published: form.value.published,
    }
    if (editing.value === null) {
      const created = await api.post('/questions', payload)
      notice.value = `已创建题目 #${created.id}`
    } else {
      await api.patch(`/questions/${editing.value}`, { version: editingVersion.value, ...payload })
      notice.value = `已保存题目 #${editing.value}`
    }
    startCreate()
    await loadQuestions()
  })
}

async function togglePublished(question) {
  await run(async () => {
    await api.patch(`/questions/${question.id}`, {
      version: question.version,
      published: !question.published,
    })
    await loadQuestions()
  })
}

onMounted(() => {
  Promise.all([loadPoints(), loadQuestions()]).catch((err) => {
    listError.value = err.message
  })
})

// 编辑时记住当前 version，提交时带上
function rememberVersion(question) {
  editingVersion.value = question.version
  startEdit(question)
}
</script>

<template>
  <div class="page">
    <PageHeader icon="check" :steps="['编辑题目', '核对答案', '发布共享']"
      eyebrow="题库"
      title="题库管理"
      description="单选、多选与判断题。选项 key 唯一，单选一个答案，多选至少两个正确项；每题 1—3 个知识点。已发布题目在全校教师间共享，只有本人能修改。"
    />

    <p v-if="notice" class="success">{{ notice }}</p>
    <p v-if="error" class="error" role="alert">{{ error }}</p>

    <SectionCard :title="editingLabel">
      <form class="question-form" @submit.prevent="submitForm">
        <div class="grid">
          <div class="field">
            <label for="q_type">题型</label>
            <select id="q_type" v-model="form.type" @change="onTypeChange">
              <option value="single">单选题</option>
              <option value="multiple">多选题</option>
              <option value="boolean">判断题</option>
            </select>
          </div>
          <div class="field">
            <label for="q_difficulty">难度</label>
            <select id="q_difficulty" v-model.number="form.difficulty">
              <option :value="1">基础</option>
              <option :value="2">进阶</option>
              <option :value="3">挑战</option>
            </select>
          </div>
          <div class="field check">
            <label>
              <input v-model="form.published" type="checkbox" />
              发布到共享题库
            </label>
          </div>
        </div>

        <div class="field">
          <label for="q_stem">题干</label>
          <textarea id="q_stem" v-model="form.stem_md" rows="3" maxlength="10000" required></textarea>
        </div>

        <fieldset class="options">
          <legend>选项与答案（点选正确项）</legend>
          <div v-for="(option, index) in form.options" :key="index" class="option-row">
            <label class="option-pick">
              <input
                :type="form.type === 'multiple' ? 'checkbox' : 'radio'"
                :name="'answer'"
                :checked="form.answer.includes(option.key)"
                @change="toggleAnswer(option.key)"
              />
              <span class="option-key">{{ option.key }}</span>
            </label>
            <input
              v-model="option.label"
              :placeholder="`选项 ${option.key} 的内容`"
              :readonly="form.type === 'boolean'"
              required
            />
            <button
              v-if="form.type !== 'boolean'"
              class="link"
              type="button"
              @click="removeOption(index)"
            >
              删除
            </button>
          </div>
          <button v-if="form.type !== 'boolean'" class="link" type="button" @click="addOption">
            添加选项
          </button>
          <p class="hint">
            当前正确答案：{{ form.answer.length ? form.answer.join('、') : '尚未选择' }}
          </p>
        </fieldset>

        <div class="field">
          <label for="q_explanation">解析</label>
          <textarea id="q_explanation" v-model="form.explanation_md" rows="2" maxlength="10000" required></textarea>
        </div>

        <fieldset class="knowledge">
          <legend>知识点（1—3 个）</legend>
          <label v-for="point in points" :key="point.id" class="knowledge-item">
            <input
              type="checkbox"
              :checked="form.knowledge_ids.includes(point.id)"
              @change="toggleKnowledge(point.id)"
            />
            {{ point.title }}
          </label>
          <p v-if="points.length === 0" class="hint">还没有知识点，请先在「课程内容」中创建。</p>
        </fieldset>

        <div class="actions">
          <button class="primary" type="submit">
            {{ editing === null ? '创建题目' : '保存修改' }}
          </button>
          <button v-if="editing !== null" class="button button--secondary" type="button" @click="startCreate">
            取消修改
          </button>
        </div>
      </form>
    </SectionCard>

    <SectionCard title="题目列表">
      <div class="filters">
        <div class="field">
          <label for="f_type">题型</label>
          <select id="f_type" v-model="filter.type" @change="loadQuestions">
            <option value="">全部</option>
            <option value="single">单选题</option>
            <option value="multiple">多选题</option>
            <option value="boolean">判断题</option>
          </select>
        </div>
        <div class="field">
          <label for="f_difficulty">难度</label>
          <select id="f_difficulty" v-model="filter.difficulty" @change="loadQuestions">
            <option value="">全部</option>
            <option value="1">基础</option>
            <option value="2">进阶</option>
            <option value="3">挑战</option>
          </select>
        </div>
        <div class="field">
          <label for="f_knowledge">知识点</label>
          <select id="f_knowledge" v-model="filter.knowledge_id" @change="loadQuestions">
            <option value="">全部</option>
            <option v-for="point in points" :key="point.id" :value="point.id">
              {{ point.title }}
            </option>
          </select>
        </div>
        <div class="field">
          <label for="f_q">题干关键词</label>
          <input id="f_q" v-model="filter.q" maxlength="100" @keyup.enter="loadQuestions" />
        </div>
        <button class="button button--secondary" type="button" @click="loadQuestions">筛选</button>
      </div>

      <StatePanel v-if="loading" kind="loading" title="正在读取题目" />
      <StatePanel v-else-if="listError" kind="error" title="题目列表加载失败" :description="listError" />
      <StatePanel
        v-else-if="questions.length === 0"
        title="暂无题目"
        description="用上方表单创建第一道题，发布后会进入共享题库。"
      />
      <div v-else class="table-scroll">
        <table>
          <thead>
            <tr>
              <th>ID</th>
              <th>题型</th>
              <th>题干</th>
              <th>答案</th>
              <th>难度</th>
              <th>知识点</th>
              <th>状态</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="question in questions" :key="question.id">
              <td>{{ question.id }}</td>
              <td>{{ QUESTION_TYPE_LABEL[question.type] }}</td>
              <td class="stem">{{ question.stem_md }}</td>
              <td>{{ question.answer.join('、') }}</td>
              <td>{{ DIFFICULTY_LABEL[question.difficulty] }}</td>
              <td>{{ knowledgeNames(question.knowledge_ids) }}</td>
              <td>
                <StatusBadge :tone="question.published ? 'success' : 'warning'">
                  {{ question.published ? '已发布' : '草稿' }}
                </StatusBadge>
              </td>
              <td class="row-actions">
                <button class="link" type="button" @click="rememberVersion(question)">编辑</button>
                <button class="link" type="button" @click="togglePublished(question)">
                  {{ question.published ? '撤回' : '发布' }}
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </SectionCard>
  </div>
</template>

<style scoped>
.question-form .grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 0 var(--space-4);
}

.field.check {
  align-self: end;
}

.field.check label {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

textarea {
  width: 100%;
  padding: 0.55rem 0.75rem;
  border: 1px solid #cbd5e5;
  border-radius: var(--radius-sm);
  font: inherit;
  color: var(--color-text-primary);
}

.options,
.knowledge {
  margin: 0 0 var(--space-4);
  padding: var(--space-4);
  border: 1px dashed #c6d4ee;
  border-radius: var(--radius-sm);
}

.options legend,
.knowledge legend {
  padding-inline: var(--space-2);
  font-size: var(--font-size-sm);
  font-weight: 700;
  color: var(--color-text-secondary);
}

.option-row {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  margin-bottom: var(--space-2);
}

.option-pick {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  flex: none;
}

.option-key {
  font-family: var(--font-mono);
  font-weight: 700;
}

.option-row input[type='text'],
.option-row > input:not([type]) {
  flex: 1;
}

.option-row input:not([type='checkbox']):not([type='radio']) {
  flex: 1;
  min-height: 2.4rem;
  padding: 0.45rem 0.6rem;
  border: 1px solid #cbd5e5;
  border-radius: var(--radius-sm);
}

.knowledge-item {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  margin: 0 var(--space-4) var(--space-2) 0;
  font-size: var(--font-size-sm);
}

.actions {
  display: flex;
  gap: var(--space-3);
}

.filters {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(11rem, 1fr));
  gap: 0 var(--space-4);
  align-items: end;
  margin-bottom: var(--space-4);
}

.stem {
  max-width: 22rem;
}

.row-actions {
  white-space: nowrap;
}

@media (max-width: 700px) {
  .question-form .grid {
    grid-template-columns: 1fr;
  }
}
</style>
