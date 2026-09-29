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
import { renderMarkdown } from '@/utils/markdown'

const route = useRoute()
const point = ref(null)
const chapter = ref(null)
const resources = ref([])
const favorited = ref(false)
const completed = ref(false)
const error = ref(null)
const notice = ref(null)

const bodyHtml = computed(() => renderMarkdown(point.value?.body_md ?? ''))
const knowledgeId = computed(() => Number(route.params.id))

async function load() {
  error.value = null
  try {
    point.value = await api.get(`/knowledge-points/${knowledgeId.value}`)
    const [favoriteList, progressList, resourceList, chapterList] = await Promise.all([
      api.get('/me/favorites?page_size=100'),
      api.get('/me/learning-progress?page_size=100'),
      api.get(`/resources?knowledge_id=${knowledgeId.value}&page_size=100`),
      api.get('/chapters?page_size=100'),
    ])
    favorited.value = favoriteList.some((item) => item.id === knowledgeId.value)
    completed.value =
      progressList.find((item) => item.knowledge_id === knowledgeId.value)?.completed ?? false
    resources.value = resourceList
    chapter.value = chapterList.find((item) => item.id === point.value.chapter_id) ?? null
  } catch (err) {
    error.value = err.message
    point.value = null
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
    <p>
      <RouterLink :to="{ name: 'student-learning' }">← 返回学习与收藏</RouterLink>
    </p>

    <p v-if="error" class="error" role="alert">{{ error }}</p>
    <p v-if="notice" class="success">{{ notice }}</p>

    <article v-if="point">
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
button.secondary {
  padding: 0.45rem 1rem;
  margin-left: 0.4rem;
  border: 1px solid #bdc1c6;
  border-radius: 0.25rem;
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
