<script setup>
/**
 * 学生学习与收藏（SPEC-005 E013/E016/E017/E018/E022）。
 *
 * 只显示服务器返回的已发布内容；收藏与进度都是幂等的 PUT/DELETE。
 * 打开资源时显式 POST 一次事件，服务器按「同人+同版本+同种类+UTC 日」去重。
 */
import { computed, onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'

import { api } from '@/api/client'

const chapters = ref([])
const points = ref([])
const resources = ref([])
const favorites = ref(new Set())
const completed = ref(new Map())
const error = ref(null)
const notice = ref(null)

const grouped = computed(() =>
  chapters.value.map((chapter) => ({
    chapter,
    items: points.value.filter((point) => point.chapter_id === chapter.id),
  })),
)

function isFavorite(pointId) {
  return favorites.value.has(pointId)
}

function isCompleted(pointId) {
  return completed.value.get(pointId) === true
}

async function load() {
  error.value = null
  try {
    const [chapterList, pointList, resourceList, favoriteList, progressList] = await Promise.all([
      api.get('/chapters?page_size=100'),
      api.get('/knowledge-points?page_size=100'),
      api.get('/resources?page_size=100'),
      api.get('/me/favorites?page_size=100'),
      api.get('/me/learning-progress?page_size=100'),
    ])
    chapters.value = chapterList
    points.value = pointList
    resources.value = resourceList
    favorites.value = new Set(favoriteList.map((item) => item.id))
    completed.value = new Map(progressList.map((item) => [item.knowledge_id, item.completed]))
  } catch (err) {
    error.value = err.message
  }
}

async function toggleFavorite(point) {
  error.value = null
  notice.value = null
  const next = !isFavorite(point.id)
  try {
    if (next) {
      await api.put(`/me/favorites/${point.id}`)
    } else {
      await api.delete(`/me/favorites/${point.id}`)
    }
    const updated = new Set(favorites.value)
    if (next) updated.add(point.id)
    else updated.delete(point.id)
    favorites.value = updated
  } catch (err) {
    error.value = err.message
  }
}

async function toggleCompleted(point) {
  error.value = null
  notice.value = null
  const next = !isCompleted(point.id)
  try {
    const result = await api.put('/me/learning-progress', {
      knowledge_id: point.id,
      completed: next,
    })
    const updated = new Map(completed.value)
    updated.set(point.id, result.completed)
    completed.value = updated
    notice.value = result.completed ? '已标记为完成（自报数据）' : '已取消完成标记'
  } catch (err) {
    error.value = err.message
  }
}

/** 打开资源时记录一次访问事件；服务器按 UTC 日去重，recorded=false 属正常重复。 */
async function recordOpen(version) {
  try {
    const result = await api.post(`/resource-versions/${version.id}/events`, { event_kind: 'open' })
    if (result.recorded) notice.value = '已记录本次访问'
  } catch (err) {
    error.value = err.message
  }
}

onMounted(load)
</script>

<template>
  <main class="page">
    <h1>学习与收藏</h1>
    <p class="hint">
      完成标记是学生自报的学习记录，不代表掌握程度。资源访问按 UTC 日去重统计。
    </p>

    <p v-if="notice" class="success">{{ notice }}</p>
    <p v-if="error" class="error" role="alert">{{ error }}</p>

    <section v-for="group in grouped" :key="group.chapter.id" class="card">
      <h2>{{ group.chapter.title }}</h2>
      <p v-if="group.items.length === 0" class="hint">本章还没有已发布的知识点。</p>
      <ul class="knowledge">
        <li v-for="point in group.items" :key="point.id">
          <RouterLink :to="{ name: 'student-knowledge', params: { id: point.id } }">
            {{ point.title }}
          </RouterLink>
          <span class="badge" :class="{ on: isCompleted(point.id) }">
            {{ isCompleted(point.id) ? '已完成' : '未完成' }}
          </span>
          <button class="link" type="button" @click="toggleFavorite(point)">
            {{ isFavorite(point.id) ? '取消收藏' : '收藏' }}
          </button>
          <button class="link" type="button" @click="toggleCompleted(point)">
            {{ isCompleted(point.id) ? '取消完成' : '标记完成' }}
          </button>
        </li>
      </ul>
    </section>

    <section class="card">
      <h2>教学资源</h2>
      <p v-if="resources.length === 0" class="hint">还没有已发布的资源。</p>
      <ul class="knowledge">
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

    <section v-if="chapters.length === 0 && !error" class="card">
      <p class="hint">暂时没有可学习的课程内容，请等待教师发布。</p>
    </section>
  </main>
</template>

<style scoped>
.knowledge {
  list-style: none;
  padding: 0;
  margin: 0.5rem 0 0;
}

.knowledge li {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-wrap: wrap;
  padding: 0.4rem 0;
  border-bottom: 1px solid #e8eaed;
}

.knowledge a {
  color: #1a73e8;
  text-decoration: none;
}

.badge.on {
  color: #1e7a3c;
  border-color: #a8d5b5;
}

.version {
  font-size: 0.88rem;
  color: #5f6368;
}
</style>
