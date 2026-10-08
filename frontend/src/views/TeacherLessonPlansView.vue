<script setup>
/**
 * 教师备课与预习发布（SPEC-008 E023—E026）。
 *
 * 条目按数组顺序编辑，提交前统一重排 sort_order；每条恰好一个目标。
 * 发布预习会先把当前编辑内容保存，再把条目与内容摘要冻结成快照发到指定班级。
 */
import { computed, onMounted, ref } from 'vue'

import { api } from '@/api/client'
import PageHeader from '@/components/ui/PageHeader.vue'
import SectionCard from '@/components/ui/SectionCard.vue'
import StatePanel from '@/components/ui/StatePanel.vue'
import StatusBadge from '@/components/ui/StatusBadge.vue'
import { localInputToUtc, utcToLocalInput } from '@/utils/attendance'
import {
  TARGET_LABEL,
  TARGET_TYPES,
  addItem,
  move,
  previewItemLabel,
  renumber,
  removeAt,
  summarizeItems,
} from '@/utils/lesson'

const plans = ref([])
const classes = ref([])
const bank = ref({ knowledge: [], resource_version: [], question: [], experiment: [] })
const previews = ref([])
const loading = ref(true)
const listError = ref(null)
const error = ref(null)
const notice = ref(null)

const selectedId = ref(null)
const version = ref(1)
const form = ref({ title: '', planned_at: '', notes: '', items: [] })
const addTarget = ref({ type: 'knowledge', id: '' })
const publishForm = ref({ class_id: '', due_at: '' })

const isNew = computed(() => selectedId.value === null)
const availableTargets = computed(() => bank.value[addTarget.value.type] ?? [])

function labelFor(targetType, targetId) {
  const entry = (bank.value[targetType] ?? []).find((item) => item.id === targetId)
  return entry?.label ?? `#${targetId}`
}

function shortStem(text) {
  const value = text ?? ''
  return value.length > 44 ? `${value.slice(0, 44)}…` : value
}

async function loadBank() {
  const [points, resources, questions, experiments] = await Promise.all([
    api.get('/knowledge-points?page_size=100'),
    api.get('/resources?page_size=100'),
    api.get('/questions?page_size=100'),
    api.get('/experiments?page_size=100'),
  ])
  bank.value = {
    knowledge: points.map((point) => ({ id: point.id, label: point.title })),
    resource_version: resources.flatMap((resource) =>
      (resource.versions ?? []).map((version) => ({
        id: version.id,
        label: `${resource.title} v${version.version_no}`,
      })),
    ),
    question: questions.map((question) => ({ id: question.id, label: shortStem(question.stem_md) })),
    experiment: experiments.map((experiment) => ({ id: experiment.id, label: experiment.title })),
  }
}

async function loadPlans() {
  plans.value = await api.get('/lesson-plans?page_size=100')
}

async function loadPreviews() {
  if (!publishForm.value.class_id) {
    previews.value = []
    return
  }
  previews.value = await api.get(
    `/preview-assignments?class_id=${publishForm.value.class_id}&page_size=20`,
  )
}

async function load() {
  loading.value = true
  listError.value = null
  try {
    const [classList] = await Promise.all([api.get('/classes?page_size=100'), loadBank(), loadPlans()])
    classes.value = classList
    if (!publishForm.value.class_id && classList.length > 0) {
      publishForm.value.class_id = classList[0].id
      await loadPreviews()
    }
  } catch (err) {
    listError.value = err.message
  } finally {
    loading.value = false
  }
}

function resetForm() {
  selectedId.value = null
  version.value = 1
  form.value = { title: '', planned_at: '', notes: '', items: [] }
}

function edit(plan) {
  selectedId.value = plan.id
  version.value = plan.version
  form.value = {
    title: plan.title,
    planned_at: utcToLocalInput(plan.planned_at),
    notes: plan.notes ?? '',
    items: renumber(plan.items),
  }
  error.value = null
  notice.value = null
}

function onAddTarget() {
  if (!addTarget.value.id) return
  form.value.items = addItem(form.value.items, addTarget.value.type, addTarget.value.id)
  addTarget.value = { type: addTarget.value.type, id: '' }
}

function onRemove(index) {
  form.value.items = removeAt(form.value.items, index)
}

function onMove(index, delta) {
  form.value.items = move(form.value.items, index, delta)
}

async function save() {
  error.value = null
  notice.value = null
  const payload = {
    title: form.value.title,
    planned_at: localInputToUtc(form.value.planned_at),
    notes: form.value.notes,
    items: form.value.items.map((item, index) => ({
      sort_order: index + 1,
      target_type: item.target_type,
      target_id: item.target_id,
    })),
  }
  try {
    const creating = isNew.value
    let saved
    if (creating) {
      saved = await api.post('/lesson-plans', payload)
    } else {
      saved = await api.patch(`/lesson-plans/${selectedId.value}`, { version: version.value, ...payload })
    }
    await loadPlans()
    edit(saved) // edit() 会清空提示，所以提示要放在它之后
    notice.value = creating ? `已创建备课单「${saved.title}」` : `已保存备课单「${saved.title}」`
    return saved
  } catch (err) {
    error.value = err.message
    return null
  }
}

async function copyPlan(plan) {
  error.value = null
  notice.value = null
  try {
    const copy = await api.post(`/lesson-plans/${plan.id}/copies`, { title: `${plan.title}（副本）` })
    notice.value = `已复制为「${copy.title}」，只复制条目引用，不复制内容与文件`
    await loadPlans()
    edit(copy)
  } catch (err) {
    error.value = err.message
  }
}

async function publish() {
  error.value = null
  notice.value = null
  if (!publishForm.value.class_id) {
    error.value = '请先选择要发布的班级'
    return
  }
  const saved = await save()
  if (!saved) return
  try {
    const preview = await api.post('/preview-assignments', {
      class_id: Number(publishForm.value.class_id),
      plan_id: saved.id,
      due_at: localInputToUtc(publishForm.value.due_at),
    })
    notice.value = `已发布预习（${preview.items.length} 项），快照已冻结`
    await loadPreviews()
  } catch (err) {
    error.value = err.message
  }
}

onMounted(load)
</script>

<template>
  <div class="page">
    <PageHeader icon="calendar" :steps="['编排内容', '保存备课', '发布预习']"
      eyebrow="备课"
      title="备课与预习"
      description="备课单按顺序引用知识点、资源版本、题目与实验；发布到班级后条目与内容摘要冻结为不可变快照，题目只向学生显示题干。"
    />

    <p v-if="notice" class="success">{{ notice }}</p>
    <p v-if="error" class="error" role="alert">{{ error }}</p>

    <div class="layout">
      <SectionCard title="我的备课单">
        <StatePanel v-if="loading" kind="loading" title="正在读取备课单" />
        <StatePanel v-else-if="listError" kind="error" title="备课单加载失败" :description="listError" />
        <template v-else>
          <button class="button button--secondary" type="button" @click="resetForm">新建备课单</button>
          <StatePanel
            v-if="plans.length === 0"
            title="还没有备课单"
            description="新建一份备课单，把本周要讲的知识点、资料、题目与实验排好顺序。"
          />
          <ul v-else class="plans">
            <li v-for="plan in plans" :key="plan.id" :class="{ 'plans__item--active': plan.id === selectedId }">
              <div class="plans__head">
                <strong>{{ plan.title }}</strong>
                <StatusBadge tone="neutral">v{{ plan.version }}</StatusBadge>
              </div>
              <p class="hint">{{ summarizeItems(plan.items).join(' · ') || '暂无条目' }}</p>
              <div class="plans__actions">
                <button class="link" type="button" @click="edit(plan)">编辑</button>
                <button class="link" type="button" @click="copyPlan(plan)">复制</button>
              </div>
            </li>
          </ul>
        </template>
      </SectionCard>

      <SectionCard :title="isNew ? '新建备课单' : `编辑备课单 #${selectedId}`">
        <div class="grid">
          <div class="field">
            <label for="l_title">标题</label>
            <input id="l_title" v-model="form.title" maxlength="100" required />
          </div>
          <div class="field">
            <label for="l_planned">计划上课时间（本地，可空）</label>
            <input id="l_planned" v-model="form.planned_at" type="datetime-local" />
          </div>
        </div>
        <div class="field">
          <label for="l_notes">备注（≤5000）</label>
          <textarea id="l_notes" v-model="form.notes" rows="3" maxlength="5000"></textarea>
        </div>

        <fieldset class="items">
          <legend>备课条目（顺序即讲授顺序）</legend>
          <ol v-if="form.items.length" class="items__list">
            <li v-for="(item, index) in form.items" :key="`${item.target_type}:${item.target_id}`">
              <span class="items__order">{{ index + 1 }}</span>
              <span class="badge">{{ TARGET_LABEL[item.target_type] ?? item.target_type }}</span>
              <span class="items__label">{{ labelFor(item.target_type, item.target_id) }}</span>
              <button class="link" type="button" :disabled="index === 0" @click="onMove(index, -1)">上移</button>
              <button
                class="link"
                type="button"
                :disabled="index === form.items.length - 1"
                @click="onMove(index, 1)"
              >
                下移
              </button>
              <button class="link" type="button" @click="onRemove(index)">删除</button>
            </li>
          </ol>
          <p v-else class="hint">还没有条目，从下面添加。</p>

          <div class="items__add filter-bar">
            <div class="field">
              <label for="l_type">目标类型</label>
              <select id="l_type" v-model="addTarget.type">
                <option v-for="type in TARGET_TYPES" :key="type" :value="type">
                  {{ TARGET_LABEL[type] }}
                </option>
              </select>
            </div>
            <div class="field">
              <label for="l_target">选择内容（仅列出已发布或本人草稿）</label>
              <select id="l_target" v-model="addTarget.id">
                <option value="" disabled>请选择</option>
                <option v-for="entry in availableTargets" :key="entry.id" :value="entry.id">
                  {{ entry.label }}
                </option>
              </select>
            </div>
            <div class="filter-actions"><button class="button button--secondary" type="button" @click="onAddTarget">添加条目</button></div>
          </div>
        </fieldset>

        <div class="form-actions">
          <button class="primary" type="button" @click="save">
            {{ isNew ? '创建备课单' : '保存修改' }}
          </button>
          <button v-if="!isNew" class="button button--secondary" type="button" @click="resetForm">
            取消编辑
          </button>
        </div>
      </SectionCard>
    </div>

    <SectionCard title="发布预习到班级">
      <div class="publish form-fields">
        <div class="field">
          <label for="l_class">班级</label>
          <select id="l_class" v-model="publishForm.class_id" @change="loadPreviews">
            <option value="" disabled>请选择班级</option>
            <option v-for="item in classes" :key="item.id" :value="item.id">{{ item.name }}</option>
          </select>
        </div>
        <div class="field">
          <label for="l_due">截止时间（本地，可空）</label>
          <input id="l_due" v-model="publishForm.due_at" type="datetime-local" />
        </div>
        <div class="form-actions"><button class="primary" type="button" :disabled="!form.title" @click="publish">保存并发布</button></div>
      </div>
      <p class="hint">
        发布前会先保存当前编辑内容；发布后条目与内容摘要冻结，之后改备课单不会改变已发布的预习。
      </p>

      <StatePanel
        v-if="previews.length === 0"
        title="该班还没有预习"
        description="发布后学生首页会出现预习待办。"
      />
      <ul v-else class="published">
        <li v-for="preview in previews" :key="preview.id">
          <div class="published__head">
            <strong>{{ preview.plan_title || `预习 #${preview.id}` }}</strong>
            <StatusBadge tone="neutral">{{ preview.due_at ?? '无期限' }}</StatusBadge>
          </div>
          <p class="published__items">
            <span v-for="item in preview.items" :key="item.sort_order">
              {{ previewItemLabel(item) }}
            </span>
          </p>
        </li>
      </ul>
    </SectionCard>
  </div>
</template>

<style scoped>
.layout {
  display: grid;
  grid-template-columns: minmax(15rem, 1fr) minmax(0, 2fr);
  gap: var(--space-4);
  align-items: start;
}

.grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(12rem, 1fr));
  gap: 0 var(--space-4);
}

textarea,
.publish select,
.items__add select {
  width: 100%;
  padding: 0.55rem 0.75rem;
  border: 1px solid #cbd5e5;
  border-radius: var(--radius-sm);
  font: inherit;
  color: var(--color-text-primary);
}

.plans {
  margin: var(--space-3) 0 0;
  padding: 0;
  list-style: none;
}

.plans li {
  padding: var(--space-3);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  margin-bottom: var(--space-2);
}

.plans__item--active {
  border-color: var(--color-primary);
  background: var(--color-primary-soft);
}

.plans__head {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  flex-wrap: wrap;
}

.plans__actions {
  display: flex;
  gap: var(--space-2);
}

.items {
  margin: 0 0 var(--space-4);
  padding: var(--space-4);
  border: 1px dashed #c6d4ee;
  border-radius: var(--radius-sm);
}

.items legend {
  padding-inline: var(--space-2);
  font-size: var(--font-size-sm);
  font-weight: 700;
  color: var(--color-text-secondary);
}

.items__list {
  margin: 0 0 var(--space-3);
  padding: 0;
  list-style: none;
}

.items__list li {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  flex-wrap: wrap;
  padding: var(--space-2) 0;
  border-bottom: 1px solid var(--color-border);
}

.items__order {
  width: 1.5rem;
  font-family: var(--font-mono);
  font-weight: 700;
  color: var(--color-primary);
}

.items__label {
  flex: 1 1 12rem;
  overflow-wrap: anywhere;
}




.published {
  margin: 0;
  padding: 0;
  list-style: none;
}

.published li {
  padding: var(--space-3) 0;
  border-bottom: 1px solid var(--color-border);
}

.published__head {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  flex-wrap: wrap;
  margin-bottom: var(--space-2);
}

.published__items {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2) var(--space-4);
  margin: 0;
  color: var(--color-text-secondary);
  font-size: var(--font-size-sm);
}

@media (max-width: 850px) {
  .layout {
    grid-template-columns: 1fr;
  }
}
</style>
