<script setup>
/**
 * 教师问答语料管理（SPEC-007 E059/E060）。
 *
 * 语料是检索的来源：每条问答挂在一个知识点上，只有已发布条目会进入索引。
 * 修改必须带 version；没有物理删除，停用靠「撤回为草稿」。
 */
import { computed, onMounted, ref } from 'vue'

import PageHeader from '@/components/ui/PageHeader.vue'
import SectionCard from '@/components/ui/SectionCard.vue'
import StatePanel from '@/components/ui/StatePanel.vue'
import StatusBadge from '@/components/ui/StatusBadge.vue'
import { api } from '@/api/client'

const entries = ref([])
const points = ref([])
const loading = ref(true)
const listError = ref(null)
const error = ref(null)
const notice = ref(null)
const busy = ref(false)
const editing = ref(null)
const form = ref(blankForm())

function blankForm() {
  return { knowledge_id: '', question: '', answer_md: '', source_url: '', published: true }
}

const editingLabel = computed(() => (editing.value === null ? '新建问答条目' : `修改条目 #${editing.value.id}`))

const pointTitles = computed(() => new Map(points.value.map((point) => [point.id, point.title])))

function pointTitle(id) {
  return pointTitles.value.get(id) ?? `知识点 #${id}`
}

async function load() {
  loading.value = true
  listError.value = null
  try {
    const [entryList, pointList] = await Promise.all([
      api.get('/qa-entries?page_size=100'),
      api.get('/knowledge-points?page_size=100'),
    ])
    entries.value = entryList
    points.value = pointList
    if (!form.value.knowledge_id && pointList.length) {
      form.value.knowledge_id = String(pointList[0].id)
    }
  } catch (err) {
    listError.value = err.message
  } finally {
    loading.value = false
  }
}

function startCreate() {
  editing.value = null
  error.value = null
  notice.value = null
  form.value = blankForm()
  if (points.value.length) form.value.knowledge_id = String(points.value[0].id)
}

function startEdit(entry) {
  editing.value = entry
  error.value = null
  notice.value = null
  form.value = {
    knowledge_id: String(entry.knowledge_id),
    question: entry.question,
    answer_md: entry.answer_md,
    source_url: entry.source_url ?? '',
    published: entry.published,
  }
}

async function save() {
  if (busy.value) return
  busy.value = true
  error.value = null
  notice.value = null
  const payload = {
    knowledge_id: Number(form.value.knowledge_id),
    question: form.value.question,
    answer_md: form.value.answer_md,
    source_url: form.value.source_url || null,
    published: form.value.published,
  }
  try {
    let message
    if (editing.value === null) {
      await api.post('/qa-entries', payload)
      message = '已新增问答条目，下一次检索会重建语料索引'
    } else {
      await api.patch(`/qa-entries/${editing.value.id}`, {
        version: editing.value.version,
        ...payload,
      })
      message = `已更新条目 #${editing.value.id}`
    }
    // startCreate 会清空提示，所以成功提示必须在重置表单之后再写，
    // 否则提示在同一个 tick 里被清掉，用户永远看不到保存结果。
    startCreate()
    notice.value = message
    await load()
  } catch (err) {
    error.value = err.message
    await load()
  } finally {
    busy.value = false
  }
}

async function togglePublished(entry) {
  error.value = null
  notice.value = null
  try {
    await api.patch(`/qa-entries/${entry.id}`, {
      version: entry.version,
      published: !entry.published,
    })
    notice.value = entry.published ? '已撤回为草稿，索引下次查询更新' : '已发布，索引下次查询更新'
    await load()
  } catch (err) {
    error.value = err.message
    await load()
  }
}

onMounted(load)
</script>

<template>
  <div class="qa-page">
    <PageHeader icon="book" :steps="['维护问答', '核对来源', '发布进入检索']"
      eyebrow="教师空间"
      title="课程问答语料"
      description="维护课程检索问答的来源条目。只有已发布条目会进入检索索引；撤回后下一次查询就不再返回。"
    />

    <StatePanel v-if="loading" kind="loading" title="正在读取问答语料" />
    <StatePanel v-else-if="listError" kind="error" title="问答语料无法读取" :description="listError" />

    <template v-else>
      <SectionCard :title="editingLabel">
        <form class="entry-form" @submit.prevent="save">
          <div class="row">
            <div class="field">
              <label for="qa_point">知识点</label>
              <select id="qa_point" v-model="form.knowledge_id" required>
                <option v-for="point in points" :key="point.id" :value="point.id">
                  {{ point.title }}
                </option>
              </select>
            </div>
            <div class="field grow">
              <label for="qa_question">问题（≤200 字）</label>
              <input id="qa_question" v-model="form.question" maxlength="200" required />
            </div>
          </div>
          <div class="field">
            <label for="qa_answer">回答（Markdown）</label>
            <textarea id="qa_answer" v-model="form.answer_md" rows="5" required></textarea>
          </div>
          <div class="row">
            <div class="field grow">
              <label for="qa_source">来源链接（http/https，可空）</label>
              <input id="qa_source" v-model="form.source_url" />
            </div>
            <div class="field check">
              <label><input v-model="form.published" type="checkbox" /> 直接发布</label>
            </div>
          </div>
          <div class="actions">
            <button class="button button--primary" type="submit" :disabled="busy">
              {{ editing === null ? '新增条目' : '保存修改' }}
            </button>
            <button v-if="editing !== null" class="button button--secondary" type="button" @click="startCreate">
              取消编辑
            </button>
          </div>
        </form>
        <p v-if="notice" class="notice">{{ notice }}</p>
        <p v-if="error" class="error" role="alert">{{ error }}</p>
      </SectionCard>

      <SectionCard :title="`问答条目（${entries.length}）`">
        <div v-if="entries.length === 0" class="empty">
          还没有问答语料。可以先执行 <code>flask --app app:create_app seed-qa --owner-login &lt;教师登录名&gt;</code>。
        </div>
        <div v-else class="table-scroll">
          <table>
            <thead>
              <tr>
                <th scope="col">ID</th>
                <th scope="col">知识点</th>
                <th scope="col">问题</th>
                <th scope="col">状态</th>
                <th scope="col">来源</th>
                <th scope="col">操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="entry in entries" :key="entry.id">
                <td>{{ entry.id }}</td>
                <td>{{ pointTitle(entry.knowledge_id) }}</td>
                <td class="question">{{ entry.question }}</td>
                <td>
                  <StatusBadge :tone="entry.published ? 'success' : 'neutral'">
                    {{ entry.published ? '已发布' : '草稿' }}
                  </StatusBadge>
                </td>
                <td>
                  <a
                    v-if="entry.source_url"
                    :href="entry.source_url"
                    target="_blank"
                    rel="noopener noreferrer"
                  >来源</a>
                  <span v-else>—</span>
                </td>
                <td class="row-actions">
                  <button class="link" type="button" @click="startEdit(entry)">编辑</button>
                  <button class="link" type="button" @click="togglePublished(entry)">
                    {{ entry.published ? '撤回为草稿' : '发布' }}
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </SectionCard>
    </template>
  </div>
</template>

<style scoped>
.qa-page { width: 100%; }
.qa-page .section-card { margin-bottom: var(--space-4); }
.entry-form { display: grid; gap: var(--space-3); }
.row { display: flex; gap: var(--space-3); flex-wrap: wrap; align-items: flex-end; }
.field { display: flex; flex-direction: column; gap: var(--space-1); }
.field.grow { flex: 1 1 16rem; }
.field select,
.field input,
.field textarea { padding: var(--space-2) var(--space-3); border: 1px solid var(--color-border); border-radius: var(--radius-sm); font: inherit; }
.field.check label { display: flex; align-items: center; gap: var(--space-2); font-size: var(--font-size-sm); }
.actions { display: flex; gap: var(--space-3); flex-wrap: wrap; }
.table-scroll { overflow-x: auto; }
table { min-width: 44rem; }
.question { max-width: 22rem; }
.row-actions { white-space: nowrap; }
.notice { color: var(--color-success); }
.error { color: var(--color-danger); }
.empty { color: var(--color-text-secondary); }
code { font-family: var(--font-mono); font-size: var(--font-size-xs); }
</style>
