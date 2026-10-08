<script setup>
/**
 * 教师内容管理（SPEC-005 E011—E020）。
 *
 * 只展示「本人可编辑」的能力：后端按 owner_id 判定，非本人的内容会返回 403。
 * 资源版本只追加：界面上不提供覆盖或删除旧版本的入口。
 */
import { computed, onMounted, ref } from 'vue'

import { api } from '@/api/client'
import PageHeader from '@/components/ui/PageHeader.vue'
import { useAuthStore } from '@/stores/auth'
import { renderMarkdown } from '@/utils/markdown'

const auth = useAuthStore()

const chapters = ref([])
const points = ref([])
const resources = ref([])
const error = ref(null)
const notice = ref(null)

const chapterForm = ref({ title: '', sort_order: 0, published: false })
const pointForm = ref({ chapter_id: '', title: '', body_md: '', source_url: '', sort_order: 0, published: false })
const resourceForm = ref({ title: '', category: 'slides', knowledge_id: '', published: false })

const filterChapterId = ref('')
const uploadTarget = ref({})
const uploadFile = ref({})
const uploadNote = ref({})

function pickFile(resourceId, event) {
  uploadFile.value = { ...uploadFile.value, [resourceId]: event.target.files?.[0] ?? null }
}

function setNote(resourceId, value) {
  uploadNote.value = { ...uploadNote.value, [resourceId]: value }
}

function setTarget(resourceId, value) {
  uploadTarget.value = { ...uploadTarget.value, [resourceId]: value }
}

const visiblePoints = computed(() => {
  if (!filterChapterId.value) return points.value
  return points.value.filter((point) => point.chapter_id === Number(filterChapterId.value))
})

function chapterTitle(chapterId) {
  const chapter = chapters.value.find((item) => item.id === chapterId)
  return chapter ? chapter.title : `章节 ${chapterId}`
}

/** 只有本人创建的内容才可写；他人的已发布内容只读（可引用，不可改）。 */
function isMine(item) {
  return auth.user !== null && item.owner_id === auth.user.id
}

async function run(action) {
  error.value = null
  notice.value = null
  try {
    await action()
  } catch (err) {
    error.value = err.message
    await load()
  }
}

async function load() {
  const [chapterList, pointList, resourceList] = await Promise.all([
    api.get('/chapters?page_size=100'),
    api.get('/knowledge-points?page_size=100'),
    api.get('/resources?page_size=100'),
  ])
  chapters.value = chapterList
  points.value = pointList
  resources.value = resourceList
  if (!pointForm.value.chapter_id && chapterList.length) {
    pointForm.value.chapter_id = chapterList[0].id
  }
}

async function createChapter() {
  await run(async () => {
    await api.post('/chapters', {
      title: chapterForm.value.title,
      sort_order: Number(chapterForm.value.sort_order) || 0,
      published: chapterForm.value.published,
    })
    notice.value = `已创建章节 ${chapterForm.value.title}`
    chapterForm.value = { title: '', sort_order: 0, published: false }
    await load()
  })
}

async function toggleChapter(chapter) {
  await run(async () => {
    await api.patch(`/chapters/${chapter.id}`, {
      version: chapter.version,
      published: !chapter.published,
    })
    await load()
  })
}

async function createPoint() {
  await run(async () => {
    await api.post('/knowledge-points', {
      chapter_id: Number(pointForm.value.chapter_id),
      title: pointForm.value.title,
      body_md: pointForm.value.body_md,
      source_url: pointForm.value.source_url || null,
      sort_order: Number(pointForm.value.sort_order) || 0,
      published: pointForm.value.published,
    })
    notice.value = `已创建知识点 ${pointForm.value.title}`
    pointForm.value = {
      chapter_id: pointForm.value.chapter_id,
      title: '',
      body_md: '',
      source_url: '',
      sort_order: 0,
      published: false,
    }
    await load()
  })
}

async function togglePoint(point) {
  await run(async () => {
    await api.patch(`/knowledge-points/${point.id}`, {
      version: point.version,
      published: !point.published,
    })
    await load()
  })
}

async function createResource() {
  await run(async () => {
    await api.post('/resources', {
      title: resourceForm.value.title,
      category: resourceForm.value.category,
      knowledge_id: resourceForm.value.knowledge_id ? Number(resourceForm.value.knowledge_id) : null,
      published: resourceForm.value.published,
    })
    notice.value = `已创建资源 ${resourceForm.value.title}`
    resourceForm.value = { title: '', category: 'slides', knowledge_id: '', published: false }
    await load()
  })
}

async function toggleResource(resource) {
  await run(async () => {
    await api.patch(`/resources/${resource.id}`, {
      version: resource.version,
      published: !resource.published,
    })
    await load()
  })
}

/** 追加文件版本：multipart 上传，磁盘名由服务端随机生成。 */
async function uploadFileVersion(resource) {
  const file = uploadFile.value[resource.id]
  if (!file) {
    error.value = '请先选择要上传的文件'
    return
  }
  await run(async () => {
    const form = new FormData()
    form.append('file', file)
    form.append('note', uploadNote.value[resource.id] ?? '')
    const version = await api.postForm(`/resources/${resource.id}/versions`, form)
    notice.value = `已追加 ${resource.title} 的版本 v${version.version_no}`
    uploadFile.value = { ...uploadFile.value, [resource.id]: null }
    uploadNote.value = { ...uploadNote.value, [resource.id]: '' }
    await load()
  })
}

async function addLinkVersion(resource) {
  await run(async () => {
    const version = await api.post(`/resources/${resource.id}/versions`, {
      external_url: uploadTarget.value[resource.id] ?? '',
      note: uploadNote.value[resource.id] ?? '',
    })
    notice.value = `已追加 ${resource.title} 的外链版本 v${version.version_no}`
    uploadTarget.value = { ...uploadTarget.value, [resource.id]: '' }
    await load()
  })
}

onMounted(() => {
  load().catch((err) => {
    error.value = err.message
  })
})
</script>

<template>
  <main class="page wide">
    <PageHeader icon="book" title="课程内容管理" description="按章节整理知识点和资料。已发布内容供课程学习与备课使用；本人内容可编辑，资料历史版本保留。" :steps="['整理章节', '编写知识点', '添加资料与发布']" />

    <p v-if="notice" class="success">{{ notice }}</p>
    <p v-if="error" class="error" role="alert">{{ error }}</p>

    <section class="card">
      <h2>章节</h2>
      <form class="form-fields" @submit.prevent="createChapter">
        <div class="field">
          <label for="chapter_title">标题</label>
          <input id="chapter_title" v-model="chapterForm.title" maxlength="100" required />
        </div>
        <div class="field small">
          <label for="chapter_order">排序</label>
          <input id="chapter_order" v-model.number="chapterForm.sort_order" type="number" min="0" />
        </div>
        <div class="field check">
          <label>
            <input v-model="chapterForm.published" type="checkbox" />
            直接发布
          </label>
        </div>
        <div class="form-actions"><button class="primary" type="submit">新建章节</button></div>
      </form>

      <div class="table-scroll" tabindex="0" role="region" aria-label="课程内容数据表，可横向滚动">
<table>
        <thead>
          <tr>
            <th>ID</th>
            <th>标题</th>
            <th>排序</th>
            <th>状态</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="chapter in chapters" :key="chapter.id">
            <td>{{ chapter.id }}</td>
            <td>{{ chapter.title }}</td>
            <td>{{ chapter.sort_order }}</td>
            <td>
              <span class="badge" :class="{ off: !chapter.published }">
                {{ chapter.published ? '已发布' : '草稿' }}
              </span>
            </td>
            <td>
              <button v-if="isMine(chapter)" class="link" type="button" @click="toggleChapter(chapter)">
                {{ chapter.published ? '撤回为草稿' : '发布' }}
              </button>
              <span v-else class="hint">他人创建，只读</span>
            </td>
          </tr>
        </tbody>
      </table>
</div>
    </section>

    <section class="card">
      <h2>知识点</h2>
      <form class="stack" @submit.prevent="createPoint">
        <div class="filter-bar">
          <div class="field">
            <label for="point_chapter">所属章节</label>
            <select id="point_chapter" v-model="pointForm.chapter_id" required>
              <option v-for="chapter in chapters" :key="chapter.id" :value="chapter.id">
                {{ chapter.title }}
              </option>
            </select>
          </div>
          <div class="field">
            <label for="point_title">标题</label>
            <input id="point_title" v-model="pointForm.title" maxlength="100" required />
          </div>
          <div class="field small">
            <label for="point_order">排序</label>
            <input id="point_order" v-model.number="pointForm.sort_order" type="number" min="0" />
          </div>
        </div>
        <div class="field">
          <label for="point_body">正文 Markdown</label>
          <textarea id="point_body" v-model="pointForm.body_md" rows="6" maxlength="20000" required></textarea>
        </div>
        <div class="filter-bar">
          <div class="field">
            <label for="point_source">来源链接（http/https，可空）</label>
            <input id="point_source" v-model="pointForm.source_url" />
          </div>
          <div class="field check">
            <label>
              <input v-model="pointForm.published" type="checkbox" />
              直接发布
            </label>
          </div>
        </div>
        <div class="form-actions"><button class="primary" type="submit">新建知识点</button></div>
      </form>

      <p class="hint">
        预览：渲染时会转义原始 HTML，正文里的 &lt;script&gt; 只会显示为文字。
      </p>
      <div class="preview" v-html="renderMarkdown(pointForm.body_md)"></div>

      <div class="filter-bar">
        <div class="field">
          <label for="filter_chapter">按章节筛选</label>
          <select id="filter_chapter" v-model="filterChapterId">
            <option value="">全部</option>
            <option v-for="chapter in chapters" :key="chapter.id" :value="chapter.id">
              {{ chapter.title }}
            </option>
          </select>
        </div>
      </div>

      <div class="table-scroll" tabindex="0" role="region" aria-label="课程内容数据表，可横向滚动">
<table>
        <thead>
          <tr>
            <th>ID</th>
            <th>章节</th>
            <th>标题</th>
            <th>状态</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="point in visiblePoints" :key="point.id">
            <td>{{ point.id }}</td>
            <td>{{ chapterTitle(point.chapter_id) }}</td>
            <td>{{ point.title }}</td>
            <td>
              <span class="badge" :class="{ off: !point.published }">
                {{ point.published ? '已发布' : '草稿' }}
              </span>
            </td>
            <td>
              <button v-if="isMine(point)" class="link" type="button" @click="togglePoint(point)">
                {{ point.published ? '撤回为草稿' : '发布' }}
              </button>
              <span v-else class="hint">他人创建，只读</span>
            </td>
          </tr>
        </tbody>
      </table>
</div>
    </section>

    <section class="card">
      <h2>教学资源</h2>
      <form class="form-fields" @submit.prevent="createResource">
        <div class="field">
          <label for="resource_title">标题</label>
          <input id="resource_title" v-model="resourceForm.title" maxlength="100" required />
        </div>
        <div class="field">
          <label for="resource_category">类别</label>
          <select id="resource_category" v-model="resourceForm.category">
            <option value="slides">slides</option>
            <option value="guide">guide</option>
            <option value="reference">reference</option>
            <option value="video">video</option>
          </select>
        </div>
        <div class="field">
          <label for="resource_knowledge">关联知识点（可空）</label>
          <select id="resource_knowledge" v-model="resourceForm.knowledge_id">
            <option value="">不关联</option>
            <option v-for="point in points" :key="point.id" :value="point.id">{{ point.title }}</option>
          </select>
        </div>
        <div class="field check">
          <label>
            <input v-model="resourceForm.published" type="checkbox" />
            直接发布
          </label>
        </div>
        <div class="form-actions"><button class="primary" type="submit">新建资源</button></div>
      </form>

      <article v-for="resource in resources" :key="resource.id" class="resource">
        <header>
          <strong>{{ resource.title }}</strong>
          <span class="badge">{{ resource.category }}</span>
          <span class="badge" :class="{ off: !resource.published }">
            {{ resource.published ? '已发布' : '草稿' }}
          </span>
          <button v-if="isMine(resource)" class="link" type="button" @click="toggleResource(resource)">
            {{ resource.published ? '撤回为草稿' : '发布' }}
          </button>
          <span v-else class="hint">他人创建，只读</span>
        </header>

        <ul class="versions">
          <li v-for="version in resource.versions" :key="version.id">
            v{{ version.version_no }} ·
            <template v-if="version.kind === 'file'">
              <a :href="`/api/v1/resource-versions/${version.id}/download`">{{ version.original_name }}</a>
              （{{ version.mime }}，{{ version.size_bytes }} 字节）
            </template>
            <template v-else>
              外链
              <a :href="version.external_url" target="_blank" rel="noopener noreferrer">
                {{ version.external_url }}
              </a>
            </template>
            <span v-if="version.note">· {{ version.note }}</span>
          </li>
          <li v-if="resource.versions.length === 0" class="hint">还没有版本。</li>
        </ul>

        <div v-if="isMine(resource)" class="filter-bar">
          <div class="field">
            <label :for="`file_${resource.id}`">追加文件版本（PDF/PPTX/PNG/JPEG，≤20 MiB）</label>
            <input
              :id="`file_${resource.id}`"
              type="file"
              accept=".pdf,.pptx,.png,.jpg,.jpeg"
              @change="pickFile(resource.id, $event)"
            />
          </div>
          <div class="field">
            <label :for="`note_${resource.id}`">备注</label>
            <input
              :id="`note_${resource.id}`"
              :value="uploadNote[resource.id] ?? ''"
              maxlength="200"
              @input="setNote(resource.id, $event.target.value)"
            />
          </div>
          <div class="filter-actions"><button class="primary" type="button" @click="uploadFileVersion(resource)">上传新版本</button></div>
        </div>

        <div v-if="isMine(resource)" class="filter-bar">
          <div class="field">
            <label :for="`link_${resource.id}`">或追加外链版本（http/https）</label>
            <input
              :id="`link_${resource.id}`"
              :value="uploadTarget[resource.id] ?? ''"
              @input="setTarget(resource.id, $event.target.value)"
            />
          </div>
          <div class="filter-actions"><button class="link" type="button" @click="addLinkVersion(resource)">追加外链</button></div>
        </div>
      </article>
    </section>
  </main>
</template>

<style scoped>
.page.wide {
  max-width: 68rem;
}



.field.small input {
  width: 5.5rem;
}

.field.check {
  align-self: center;
}

.field.check label {
  display: flex;
  align-items: center;
  gap: 0.35rem;
}

textarea {
  padding: 0.45rem 0.6rem;
  border: 1px solid #bdc1c6;
  border-radius: 0.25rem;
  font: inherit;
}

.preview {
  margin: 0.5rem 0 1rem;
  padding: 0.75rem 1rem;
  border: 1px dashed #dadce0;
  border-radius: 0.5rem;
  background: #fafafa;
}

.resource {
  margin-top: 1rem;
  padding-top: 0.75rem;
  border-top: 1px solid #e8eaed;
}

.resource header {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.versions {
  margin: 0.5rem 0;
  padding-left: 1.1rem;
  font-size: 0.9rem;
}

.versions a {
  word-break: break-all;
}
</style>
