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
import TimingPreview from '@/components/home/TimingPreview.vue'
import SectionCard from '@/components/ui/SectionCard.vue'
import StatePanel from '@/components/ui/StatePanel.vue'
import { renderMarkdown } from '@/utils/markdown'

const route = useRoute()
const point = ref(null)
const chapter = ref(null)
const resources = ref([])
const favorited = ref(false)
const completed = ref(false)
const favoriteBusy = ref(false),
  completionBusy = ref(false)
const error = ref(null)
const notice = ref(null)
const relatedExperiments = ref([])
const relatedError = ref('')
const loading = ref(true)
const activeTab = ref('concept')
const tabs = [
  { id: 'concept', title: '概念' },
  { id: 'circuit', title: '电路结构' },
  { id: 'states', title: '状态表' },
  { id: 'timing', title: '时序图' },
  { id: 'application', title: '实验应用' },
  { id: 'practice', title: '相关习题' },
]
function tabKey(event) {
  const index = tabs.findIndex((tab) => tab.id === activeTab.value)
  const next =
    event.key === 'ArrowRight'
      ? (index + 1) % tabs.length
      : event.key === 'ArrowLeft'
        ? (index + tabs.length - 1) % tabs.length
        : event.key === 'Home'
          ? 0
          : event.key === 'End'
            ? tabs.length - 1
            : -1
  if (next < 0) return
  event.preventDefault()
  activeTab.value = tabs[next].id
  event.currentTarget.querySelectorAll('button')[next]?.focus()
}
let loadRevision = 0

const bodyHtml = computed(() => renderMarkdown(point.value?.body_md ?? ''))
const knowledgeId = computed(() => Number(route.params.id))

async function load() {
  const current = ++loadRevision
  const id = knowledgeId.value
  loading.value = true
  activeTab.value = 'concept'
  favoriteBusy.value = false
  completionBusy.value = false
  relatedExperiments.value = []
  relatedError.value = ''
  error.value = null
  try {
    const detail = await api.get(`/knowledge-points/${id}`)
    const [favoriteList, progressList, resourceList, chapterList] =
      await Promise.all([
        readAll('/me/favorites'),
        readAll('/me/learning-progress'),
        readAll(`/resources?knowledge_id=${id}`),
        readAll('/chapters'),
      ])
    if (current !== loadRevision) return
    point.value = detail
    favorited.value = favoriteList.some((item) => item.id === knowledgeId.value)
    completed.value =
      progressList.find((item) => item.knowledge_id === knowledgeId.value)
        ?.completed ?? false
    resources.value = resourceList
    chapter.value =
      chapterList.find((item) => item.id === point.value.chapter_id) ?? null
    try {
      const list = await readAll(`/experiments?knowledge_id=${id}`)
      if (current === loadRevision) relatedExperiments.value = list
    } catch (err) {
      if (current === loadRevision) relatedError.value = err.message
    }
  } catch (err) {
    if (current === loadRevision) {
      error.value = err.message
      point.value = null
    }
  } finally {
    if (current === loadRevision) loading.value = false
  }
}

async function toggleFavorite() {
  if (favoriteBusy.value) return
  const id = knowledgeId.value,
    current = loadRevision,
    wasFavorite = favorited.value
  favoriteBusy.value = true
  notice.value = null
  try {
    if (wasFavorite) {
      await api.delete(`/me/favorites/${id}`)
    } else {
      await api.put(`/me/favorites/${id}`)
    }
    if (current === loadRevision) favorited.value = !wasFavorite
  } catch (err) {
    if (current === loadRevision) error.value = err.message
  } finally {
    if (current === loadRevision) favoriteBusy.value = false
  }
}

async function toggleCompleted() {
  if (completionBusy.value) return
  const id = knowledgeId.value,
    current = loadRevision
  completionBusy.value = true
  notice.value = null
  try {
    const result = await api.put('/me/learning-progress', {
      knowledge_id: id,
      completed: !completed.value,
    })
    if (current !== loadRevision) return
    completed.value = result.completed
    notice.value = result.completed
      ? '已标记为完成（自报数据）'
      : '已取消完成标记'
  } catch (err) {
    if (current === loadRevision) error.value = err.message
  } finally {
    if (current === loadRevision) completionBusy.value = false
  }
}

async function recordOpen(version) {
  try {
    await api.post(`/resource-versions/${version.id}/events`, {
      event_kind: 'open',
    })
  } catch (err) {
    error.value = err.message
  }
}

onMounted(load)

// 同一组件实例在 /student/knowledge/:id 之间跳转时不会重新挂载，
// 必须显式监听参数变化重新拉取，否则会继续显示上一个知识点的内容。
watch(
  () => route.params.id,
  (next, previous) => {
    if (next !== previous) {
      point.value = null
      notice.value = null
      load()
    }
  },
)
</script>
<template>
  <div class="page knowledge-page">
    <nav class="breadcrumb" aria-label="面包屑">
      <RouterLink :to="{ name: 'student-learning' }">课程学习</RouterLink
      ><span>/</span><span>{{ chapter?.title ?? '课程' }}</span
      ><span>/</span><span>{{ point?.title ?? '知识点' }}</span>
    </nav>
    <StatePanel v-if="loading" kind="loading" title="正在读取知识点" />
    <p v-if="error" class="error" role="alert">{{ error }}</p>
    <p v-if="notice" class="success" role="status">{{ notice }}</p>
    <template v-if="point && !loading">
      <header class="knowledge-heading">
        <div>
          <h1>{{ point.title }}</h1>
          <p class="hint">
            {{ chapter?.title ?? '数字逻辑' }} · 从电路结构理解每一次状态变化
          </p>
        </div>
        <div class="overview-actions">
          <button
            class="button button--secondary"
            type="button"
            :aria-pressed="favorited"
            :disabled="favoriteBusy"
            @click="toggleFavorite"
          >
            {{ favorited ? '★ 已收藏' : '☆ 收藏' }}</button
          ><button
            class="button button--secondary"
            type="button"
            :aria-pressed="completed"
            :disabled="completionBusy"
            @click="toggleCompleted"
          >
            {{ completed ? '✓ 已完成' : '标记完成' }}
          </button>
        </div>
      </header>
      <nav
        class="tabs"
        role="tablist"
        aria-label="知识点内容"
        @keydown="tabKey"
      >
        <button
          v-for="tab in tabs"
          :id="`knowledge-tab-${tab.id}`"
          :key="tab.id"
          role="tab"
          type="button"
          :aria-selected="activeTab === tab.id"
          :aria-controls="`knowledge-panel-${tab.id}`"
          :tabindex="activeTab === tab.id ? 0 : -1"
          @click="activeTab = tab.id"
        >
          {{ tab.title }}
        </button>
      </nav>
      <p v-if="relatedError" class="error" role="alert">
        相关实验读取失败：{{ relatedError }}
      </p>
      <section
        v-show="activeTab === 'concept'"
        id="knowledge-panel-concept"
        class="knowledge-concept"
        role="tabpanel"
        aria-labelledby="knowledge-tab-concept"
      >
        <SectionCard title="电路结构" class="concept-structure"><div class="concept-columns">
          <div><template v-if="relatedExperiments.length"
            ><CircuitPreview :kind="relatedExperiments[0].simulator_type" />
            <p class="hint">
              {{ relatedExperiments[0].title }} · 根据关联实验模型绘制
            </p></template
          ><StatePanel
            v-else
            title="暂无关联电路"
            description="当前知识点没有关联实验，先阅读右侧课程内容。"
        /></div>
        <article><h3>工作原理</h3><section class="markdown" v-html="bodyHtml"></section>
          <p v-if="!point.body_md" class="hint">暂无正文内容。</p>
          <p v-if="point.source_url" class="hint">
            来源：<a
              :href="point.source_url"
              target="_blank"
              rel="noopener noreferrer"
              >原始资料 ↗</a
            >
          </p></article></div></SectionCard>
      </section>
      <section
        v-show="activeTab === 'circuit'"
        id="knowledge-panel-circuit"
        role="tabpanel"
        aria-labelledby="knowledge-tab-circuit"
      >
        <SectionCard title="关联实验电路"
          ><div v-if="relatedExperiments.length" class="knowledge-experiments">
            <article
              v-for="experiment in relatedExperiments"
              :key="experiment.id"
            >
              <CircuitPreview :kind="experiment.simulator_type" />
              <h3>{{ experiment.title }}</h3>
              <p class="hint">
                概念框图用于识别模型与引脚；具体条件在实验页查看。
              </p>
              <RouterLink
                class="button button--secondary"
                :to="{
                  name: 'student-experiment',
                  params: { id: experiment.id },
                }"
                >查看实验条件</RouterLink
              >
            </article>
          </div>
          <StatePanel v-else title="暂无关联电路"
        /></SectionCard>
      </section>
      <section
        v-show="activeTab === 'states'"
        id="knowledge-panel-states"
        role="tabpanel"
        aria-labelledby="knowledge-tab-states"
      >
        <SectionCard title="输入与状态预测"
          ><p class="hint">
            这里列出关联实验的有效上升沿输入；标准状态在实验提交后提供。
          </p>
          <div
            v-for="experiment in relatedExperiments"
            :key="experiment.id"
            class="knowledge-state"
          >
            <h3>{{ experiment.title }}</h3>
            <div class="table-scroll">
              <table>
                <thead>
                  <tr>
                    <th>拍</th>
                    <th>输入</th>
                    <th>输出 Q</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="row in experiment.checkpoints" :key="row.index">
                    <td>{{ row.index + 1 }}</td>
                    <td class="mono">
                      {{
                        Object.entries(row.inputs ?? {})
                          .map(
                            ([key, value]) => `${key.toUpperCase()}=${value}`,
                          )
                          .join(' · ')
                      }}
                    </td>
                    <td>待预测</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
          <p v-if="!relatedExperiments.length" class="hint">
            当前没有可供预测的关联实验。
          </p></SectionCard
        >
      </section>
      <section
        v-show="activeTab === 'timing'"
        id="knowledge-panel-timing"
        role="tabpanel"
        aria-labelledby="knowledge-tab-timing"
      >
        <SectionCard title="输入时序采样"
          ><div
            v-for="experiment in relatedExperiments"
            :key="experiment.id"
            class="knowledge-state"
          >
            <h3>{{ experiment.title }}</h3>
            <TimingPreview
              :kind="experiment.simulator_type"
              :checkpoints="experiment.checkpoints ?? []"
              :events="experiment.input_sequence ?? null"
            />
          </div>
          <p v-if="!relatedExperiments.length" class="hint">
            暂无关联实验的输入采样。
          </p></SectionCard
        >
      </section>
      <section
        v-show="activeTab === 'application'"
        id="knowledge-panel-application"
        role="tabpanel"
        aria-labelledby="knowledge-tab-application"
      >
        <SectionCard title="实验应用"
          ><article
            v-for="experiment in relatedExperiments"
            :key="experiment.id"
            class="knowledge-state"
          >
            <h3>{{ experiment.title }}</h3>
            <pre class="application-steps">{{ experiment.steps_md }}</pre>
            <RouterLink
              class="button button--primary"
              :to="{
                name: 'student-experiment',
                params: { id: experiment.id },
              }"
              >进入实验预测 →</RouterLink
            >
          </article>
          <p v-if="!relatedExperiments.length" class="hint">
            暂无关联实验应用。
          </p></SectionCard
        >
      </section>
      <section
        v-show="activeTab === 'practice'"
        id="knowledge-panel-practice"
        role="tabpanel"
        aria-labelledby="knowledge-tab-practice"
      >
        <SectionCard title="练习这个知识点"
          ><p class="hint">
            按当前知识点生成自练，保存答案并在提交后查看判分与解析。
          </p>
          <RouterLink
            class="button button--primary"
            :to="{
              name: 'student-practice',
              query: { knowledge_id: knowledgeId },
            }"
            >开始习题训练 →</RouterLink
          ></SectionCard
        >
      </section>
      <div class="ref-grid knowledge-bottom">
        <SectionCard title="时序波形与实验"
          ><template v-if="relatedExperiments.length"
            ><h3>{{ relatedExperiments[0].title }}</h3>
            <TimingPreview
              :kind="relatedExperiments[0].simulator_type"
              :checkpoints="relatedExperiments[0].checkpoints ?? []"
              :events="relatedExperiments[0].input_sequence ?? null"
            /><RouterLink
              class="button button--secondary"
              :to="{
                name: 'student-experiment',
                params: { id: relatedExperiments[0].id },
              }"
              >预测输出状态 →</RouterLink
            ></template
          >
          <p v-else class="hint">
            学完概念后，可以先到习题训练巩固。
          </p></SectionCard
        >
        <SectionCard title="相关资源"
          ><ul v-if="resources.length" class="resource-list">
            <li v-for="resource in resources" :key="resource.id">
              <span class="resource-icon">▤</span>
              <div>
                <strong>{{ resource.title }}</strong
                ><small>{{ resource.category }}</small>
                <div
                  v-for="version in resource.versions"
                  :key="version.id"
                  class="resource-version"
                >
                  <span>版本 {{ version.version_no }}</span
                  ><a
                    v-if="version.kind === 'file'"
                    :href="`/api/v1/resource-versions/${version.id}/download`"
                    @click="recordOpen(version)"
                    >{{ version.original_name }} ↓</a
                  ><a
                    v-else
                    :href="version.external_url"
                    target="_blank"
                    rel="noopener noreferrer"
                    @click="recordOpen(version)"
                    >打开外链 ↗</a
                  >
                </div>
              </div>
            </li>
          </ul>
          <p v-else class="hint">教师尚未发布关联资源。</p></SectionCard
        >
      </div>
    </template>
  </div>
</template>
<style scoped>
.knowledge-page {
  display: grid;
  gap: 16px;
  max-width: none;
}
.concept-columns { display: grid; grid-template-columns: minmax(210px, 1fr) minmax(0, 1.1fr); gap: 28px; align-items: center; }
.concept-columns > div { min-width: 0; }
.concept-columns > article h3 { font-size: 14px; }
.concept-columns .markdown { font-size: 12px; }
.concept-columns .markdown :deep(p) { margin-block: 8px; }
.concept-columns .markdown :deep(th), .concept-columns .markdown :deep(td) { padding: 7px 11px; font-size: 12px; }
.concept-columns :deep(.circuit-preview) { max-width: 260px; padding: 20px; }
@media (max-width: 620px) { .concept-columns { grid-template-columns: 1fr; gap: 16px; } }
.breadcrumb {
  margin: 0;
  font-size: 11px;
}
.knowledge-heading {
  display: flex;
  justify-content: space-between;
  gap: 12px;
}
.knowledge-heading h1 {
  margin-bottom: 7px;
  font-size: 25px;
}
.knowledge-heading p {
  margin-bottom: 0;
}
.knowledge-heading .overview-actions {
  margin-top: 0;
  align-items: flex-start;
}
.knowledge-page .circuit-preview {
  max-width: 260px;
  margin: 12px auto;
}
.knowledge-experiments {
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
}
.knowledge-experiments h3 {
  margin-top: 12px;
}
.knowledge-state + .knowledge-state {
  border-top: 1px solid var(--color-border);
  padding-top: 15px;
  margin-top: 15px;
}
.application-steps {
  white-space: pre-wrap;
  font: inherit;
  color: var(--color-text-secondary);
}
.mono {
  font-family: var(--font-mono);
}
.knowledge-bottom .button {
  margin-top: 12px;
}
.resource-list {
  padding: 0;
  list-style: none;
  margin: 0;
}
.resource-list li {
  display: flex;
  gap: 12px;
  padding: 12px 0;
  border-bottom: 1px solid var(--color-border);
}
.resource-list li > div {
  flex: 1;
  min-width: 0;
}
.resource-icon {
  display: grid;
  place-items: center;
  align-self: start;
  flex: none;
  width: 30px;
  height: 33px;
  color: var(--color-primary);
  background: var(--color-primary-soft);
  border-radius: 6px;
}
.resource-list strong {
  font-size: 12px;
}
.resource-list small {
  display: block;
  color: var(--color-text-secondary);
  font-size: 10px;
}
.resource-version {
  display: flex;
  flex-wrap: wrap;
  justify-content: space-between;
  gap: 8px;
  font-size: 11px;
  margin-top: 6px;
  color: var(--color-text-secondary);
}
.resource-version a {
  overflow-wrap: anywhere;
}
.markdown {
  font-size: 13px;
  line-height: 1.9;
  overflow-wrap: anywhere;
}
.markdown :deep(h1),
.markdown :deep(h2),
.markdown :deep(h3) {
  font-size: 15px;
  margin: 12px 0 6px;
}
.markdown :deep(pre) {
  overflow-x: auto;
  padding: 10px;
  background: #f5f8ff;
  border-radius: 8px;
}
.markdown :deep(code) {
  font-family: var(--font-mono);
}
.markdown :deep(table) {
  display: block;
  overflow-x: auto;
}
@media (max-width: 620px) {
  .knowledge-heading {
    flex-direction: column;
  }
}
</style>
