<script setup>
/**
 * 知识点阅读页（SPEC-005 E014/E015/E017/E018/E022）。
 *
 * 正文用 renderMarkdown 输出：整段先转义、只生成白名单标签，
 * 因此原始 HTML（含 <script>）只会显示为文字。草稿对学生会返回 404。
 */
import { computed, onMounted, ref, watch } from 'vue'
import { RouterLink, useRoute } from 'vue-router'

import { api } from '@/api/client'
import { readAll } from '@/api/pagination'
import CircuitPreview from '@/components/home/CircuitPreview.vue'
import SectionCard from '@/components/ui/SectionCard.vue'
import StatePanel from '@/components/ui/StatePanel.vue'
import { renderMarkdown } from '@/utils/markdown'

const route = useRoute()
const point = ref(null)
const chapter = ref(null)
const resources = ref([])
const favorited = ref(false)
const completed = ref(false)
const error = ref(null)
const notice = ref(null)
const relatedExperiments = ref([])
const relatedError = ref('')
const loading = ref(true)
let loadRevision = 0

const bodyHtml = computed(() => renderMarkdown(point.value?.body_md ?? ''))
const knowledgeId = computed(() => Number(route.params.id))

async function load() {
  const current = ++loadRevision
  const id = knowledgeId.value
  loading.value = true
  relatedExperiments.value = []
  relatedError.value = ''
  error.value = null
  try {
    const detail = await api.get(`/knowledge-points/${id}`)
    const [favoriteList, progressList, resourceList, chapterList] = await Promise.all([
      readAll('/me/favorites'),
      readAll('/me/learning-progress'),
      readAll(`/resources?knowledge_id=${id}`),
      readAll('/chapters'),
    ])
    if (current !== loadRevision) return
    point.value = detail
    favorited.value = favoriteList.some((item) => item.id === knowledgeId.value)
    completed.value =
      progressList.find((item) => item.knowledge_id === knowledgeId.value)?.completed ?? false
    resources.value = resourceList
    chapter.value = chapterList.find((item) => item.id === point.value.chapter_id) ?? null
    try { const list = await readAll(`/experiments?knowledge_id=${id}`); if (current === loadRevision) relatedExperiments.value = list }
    catch (err) { if (current === loadRevision) relatedError.value = err.message }
  } catch (err) {
    if (current === loadRevision) { error.value = err.message; point.value = null }
  } finally {
    if (current === loadRevision) loading.value = false
  }
}

async function toggleFavorite() {
  notice.value = null
  try {
    if (favorited.value) {
      await api.delete(`/me/favorites/${knowledgeId.value}`)
      favorited.value = false
    } else {
      await api.put(`/me/favorites/${knowledgeId.value}`)
      favorited.value = true
    }
  } catch (err) {
    error.value = err.message
  }
}

async function toggleCompleted() {
  notice.value = null
  try {
    const result = await api.put('/me/learning-progress', {
      knowledge_id: knowledgeId.value,
      completed: !completed.value,
    })
    completed.value = result.completed
    notice.value = result.completed ? '已标记为完成（自报数据）' : '已取消完成标记'
  } catch (err) {
    error.value = err.message
  }
}

async function recordOpen(version) {
  try {
    await api.post(`/resource-versions/${version.id}/events`, { event_kind: 'open' })
  } catch (err) {
    error.value = err.message
  }
}

onMounted(load)

// 同一组件实例在 /student/knowledge/:id 之间跳转时不会重新挂载，
// 必须显式监听参数变化重新拉取，否则会继续显示上一个知识点的内容。
watch(() => route.params.id, (next, previous) => {
  if (next !== previous) {
    point.value = null
    notice.value = null
    load()
  }
})
</script>

<template>
  <main class="page">
    <nav class="breadcrumb" aria-label="面包屑"><RouterLink :to="{ name: 'student-learning' }">数字逻辑</RouterLink><span aria-hidden="true">/</span><span>{{ chapter?.title ?? '课程' }}</span><span aria-hidden="true">/</span><span>{{ point?.title ?? '知识点' }}</span></nav>
    <StatePanel v-if="loading" kind="loading" title="正在读取知识点" />
    <p>
      <RouterLink :to="{ name: 'student-learning' }">← 返回学习与收藏</RouterLink>
    </p>

    <p v-if="error" class="error" role="alert">{{ error }}</p>
    <p v-if="notice" class="success">{{ notice }}</p>

    <article v-if="point" class="knowledge-content">
      <p class="hint">
        <template v-if="chapter">{{ chapter.title }} · </template>知识点 #{{ point.id }}
      </p>
      <h1>{{ point.title }}</h1>

      <p>
        <button class="primary" type="button" @click="toggleFavorite">
          {{ favorited ? '取消收藏' : '收藏' }}
        </button>
        <button class="secondary" type="button" @click="toggleCompleted">
          {{ completed ? '取消完成标记' : '标记为已完成' }}
        </button>
        <span class="badge" :class="{ on: completed }">
          {{ completed ? '已完成' : '未完成' }}
        </span>
      </p>

      <!-- bodyHtml 只由 renderMarkdown 生成：输入已整体转义，标签来自白名单 -->
      <section class="markdown" v-html="bodyHtml"></section>
      <SectionCard title="相关实验与练习">
        <p v-if="relatedError" class="error" role="alert">相关实验读取失败：{{ relatedError }}</p>
        <div v-else-if="relatedExperiments.length" class="knowledge-experiments"><article v-for="experiment in relatedExperiments" :key="experiment.id"><CircuitPreview :kind="experiment.simulator_type" /><h3>{{ experiment.title }}</h3><RouterLink class="button button--secondary" :to="{ name: 'student-experiment', params: { id: experiment.id } }">进入实验预测</RouterLink></article></div>
        <p v-else class="hint">当前知识点暂无关联实验。</p>
        <RouterLink class="button button--primary" :to="{ name: 'student-practice', query: { knowledge_id: knowledgeId } }">练习这个知识点</RouterLink>
      </SectionCard>

      <p v-if="point.source_url">
        来源：
        <a :href="point.source_url" target="_blank" rel="noopener noreferrer">
          {{ point.source_url }}
        </a>
      </p>

      <section v-if="resources.length" class="card">
        <h2>相关资源</h2>
        <ul class="resource-list">
          <li v-for="resource in resources" :key="resource.id">
            <strong>{{ resource.title }}</strong>
            <span class="badge">{{ resource.category }}</span>
            <template v-for="version in resource.versions" :key="version.id">
              <span class="version">
                v{{ version.version_no }}
                <template v-if="version.kind === 'file'">
                  <a
                    :href="`/api/v1/resource-versions/${version.id}/download`"
                    @click="recordOpen(version)"
                  >
                    {{ version.original_name }}
                  </a>
                </template>
                <template v-else>
                  <a
                    :href="version.external_url"
                    target="_blank"
                    rel="noopener noreferrer"
                    @click="recordOpen(version)"
                  >
                    打开外链
                  </a>
                </template>
              </span>
            </template>
          </li>
        </ul>
      </section>
    </article>
  </main>
</template>

<style scoped>
.knowledge-content { padding: var(--space-6); background: var(--color-bg-card); border: 1px solid var(--color-border); border-radius: var(--radius-md); box-shadow: var(--shadow-card); }
.knowledge-content > .markdown { max-width: 75ch; margin-block: var(--space-5); }
.knowledge-content > .section-card { margin-block: var(--space-5); box-shadow: none; }
@media (max-width: 620px) { .knowledge-content { padding: var(--space-4); } }
button.secondary {
  padding: 0.45rem 1rem;
  margin-left: 0.4rem;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  color: var(--color-primary);
  background: #fff;
  cursor: pointer;
}

.badge.on {
  color: #1e7a3c;
  border-color: #a8d5b5;
  margin-left: 0.4rem;
}

.resource-list {
  list-style: none;
  padding: 0;
  margin: 0.5rem 0 0;
}

.resource-list li {
  padding: 0.4rem 0;
  border-bottom: 1px solid #e8eaed;
  display: flex;
  gap: 0.5rem;
  flex-wrap: wrap;
  align-items: center;
}

.version {
  font-size: 0.88rem;
  color: #5f6368;
}

.markdown :deep(h1),
.markdown :deep(h2),
.markdown :deep(h3) {
  font-size: 1.05rem;
  margin: 1.1rem 0 0.4rem;
}

.markdown :deep(table) {
  font-size: 0.9rem;
}

.markdown :deep(code) {
  background: #f1f3f4;
  padding: 0.05rem 0.3rem;
  border-radius: 0.2rem;
  font-family: Consolas, "Courier New", monospace;
}

.markdown :deep(pre) {
  background: #f1f3f4;
  padding: 0.75rem;
  border-radius: 0.4rem;
  overflow-x: auto;
}

.markdown :deep(blockquote) {
  margin: 0.5rem 0;
  padding-left: 0.75rem;
  border-left: 3px solid #dadce0;
  color: #5f6368;
}
</style>
