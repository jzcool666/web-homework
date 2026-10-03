<script setup>
/**
 * 时序逻辑知识图谱（SPEC-016 E066/E067/E068，只读投影）。
 *
 * 服务器实时计算图并按权限过滤（只含已发布知识点）；本页只做查询与展示：
 * 章节/根节点/深度查子图，指定两端查先修路径。有环时后端不返回拓扑序，
 * 页面显式提示而不是显示一个看似可用的顺序。
 */
import { computed, onMounted, ref } from 'vue'

import { api } from '@/api/client'
import KnowledgeGraphChart from '@/components/KnowledgeGraphChart.vue'
import PageHeader from '@/components/ui/PageHeader.vue'
import SectionCard from '@/components/ui/SectionCard.vue'
import StatePanel from '@/components/ui/StatePanel.vue'
import { graphNotice, nodeLabel, pathSteps, summarize } from '@/utils/knowledgeGraph'

const chapters = ref([])
const points = ref([])
const graph = ref(null)
const path = ref(null)
const topology = ref(null)

const chapterId = ref('')
const rootId = ref('')
const depth = ref(1)
const fromId = ref('')
const toId = ref('')

const loading = ref(false)
const error = ref(null)
const pathError = ref(null)
const pathLoading = ref(false)

const stats = computed(() => (graph.value ? summarize(graph.value) : null))
const notice = computed(() => graphNotice(graph.value))
const highlightEdges = computed(() => path.value?.edges ?? [])

function query(path, params) {
  const search = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value !== '' && value !== null && value !== undefined) search.set(key, value)
  }
  const suffix = search.toString()
  return suffix ? `${path}?${suffix}` : path
}

async function loadGraph() {
  loading.value = true
  error.value = null
  try {
    graph.value = await api.get(
      query('/knowledge-graph', {
        chapter_id: chapterId.value,
        root_id: rootId.value,
        depth: rootId.value === '' ? '' : depth.value,
      }),
    )
    topology.value = null
  } catch (err) {
    graph.value = null
    error.value = err.message
  } finally {
    loading.value = false
  }
}

async function loadTopology() {
  error.value = null
  try {
    topology.value = await api.get(
      query('/knowledge-graph/topological', { chapter_id: chapterId.value }),
    )
  } catch (err) {
    topology.value = null
    error.value = err.message
  }
}

async function loadPath() {
  pathLoading.value = true
  pathError.value = null
  try {
    path.value = await api.get(
      query('/knowledge-graph/path', { from: fromId.value, to: toId.value }),
    )
  } catch (err) {
    path.value = null
    pathError.value = err.message
  } finally {
    pathLoading.value = false
  }
}

function resetPath() {
  path.value = null
  pathError.value = null
}

onMounted(async () => {
  try {
    const [chapterList, pointList] = await Promise.all([
      api.get('/chapters?page_size=100'),
      api.get('/knowledge-points?published=true&page_size=100'),
    ])
    chapters.value = chapterList
    points.value = pointList
    await loadGraph()
  } catch (err) {
    error.value = err.message
  }
})
</script>

<template>
  <div class="page">
    <PageHeader icon="network" :steps="['选择知识范围', '查看先修方向', '查询学习路径']"
      eyebrow="智能工具"
      title="知识图谱"
      description="时序逻辑知识点的先修关系（先修 → 后继）。图由课程内容实时计算，只包含已发布知识点；本页是只读投影，先修关系仍由课程内容管理维护。"
    />

    <p v-if="error" class="error" role="alert">{{ error }}</p>

    <SectionCard title="查询子图">
      <form class="graph-form" @submit.prevent="loadGraph">
        <div class="field">
          <label for="g_chapter">章节</label>
          <select id="g_chapter" v-model="chapterId" @change="resetPath">
            <option value="">全部章节</option>
            <option v-for="chapter in chapters" :key="chapter.id" :value="chapter.id">
              {{ chapter.title }}
            </option>
          </select>
        </div>
        <div class="field">
          <label for="g_root">根节点</label>
          <select id="g_root" v-model="rootId">
            <option value="">不指定（整图）</option>
            <option v-for="point in points" :key="point.id" :value="point.id">
              {{ nodeLabel({ knowledge_id: point.id, title: point.title }) }}
            </option>
          </select>
        </div>
        <div class="field">
          <label for="g_depth">深度（1—3）</label>
          <select id="g_depth" v-model.number="depth" :disabled="rootId === ''">
            <option v-for="value in [1, 2, 3]" :key="value" :value="value">{{ value }} 层</option>
          </select>
        </div>
        <button class="primary" type="submit" :disabled="loading">
          {{ loading ? '查询中…' : '查询' }}
        </button>
      </form>
      <p class="hint">未指定根节点时展示所选章节的全部已发布知识点，不做深度裁剪。</p>
    </SectionCard>

    <SectionCard title="先修路径">
      <form class="graph-form" @submit.prevent="loadPath">
        <div class="field">
          <label for="g_from">起点</label>
          <select id="g_from" v-model="fromId" required>
            <option value="" disabled>请选择知识点</option>
            <option v-for="point in points" :key="point.id" :value="point.id">{{ point.title }}</option>
          </select>
        </div>
        <div class="field">
          <label for="g_to">终点</label>
          <select id="g_to" v-model="toId" required>
            <option value="" disabled>请选择知识点</option>
            <option v-for="point in points" :key="point.id" :value="point.id">{{ point.title }}</option>
          </select>
        </div>
        <button type="submit" :disabled="pathLoading || fromId === '' || toId === ''">查路径</button>
      </form>
      <p v-if="pathError" class="error" role="alert">{{ pathError }}</p>
      <div v-else-if="path">
        <p v-if="!path.matched" class="hint hint--warning">
          两点之间没有先修链（按先修 → 后继方向）。未编造中间知识点。
        </p>
        <ol v-else class="path-steps">
          <li v-for="step in pathSteps(path)" :key="step.label">{{ step.label }}</li>
        </ol>
      </div>
    </SectionCard>

    <SectionCard title="图谱">
      <StatePanel v-if="loading" kind="loading" title="正在读取知识图谱" />
      <template v-else-if="graph">
        <p v-if="stats" class="stats">
          节点 {{ stats.nodeCount }} · 先修边 {{ stats.edgeCount }} · 最大深度 {{ stats.maxDepth }} ·
          根节点 {{ stats.roots }} · 孤立节点 {{ stats.isolated }}
        </p>
        <p v-if="notice" class="hint" :class="{ 'hint--warning': notice.tone !== 'neutral' }">
          {{ notice.text }}
        </p>
        <p v-if="highlightEdges.length > 0" class="hint">
          已高亮查询到的先修链（{{ highlightEdges.length }} 条边）。
        </p>
        <KnowledgeGraphChart v-if="graph.nodes.length > 0" :graph="graph" :highlight-edges="highlightEdges" />
        <button type="button" class="topology-button" @click="loadTopology">
          查看拓扑序（同层按排序与编号）
        </button>
        <div v-if="topology" class="topology">
          <p v-if="topology.has_cycle" class="error" role="alert">
            存在环，不提供拓扑序。成环节点对：
            <span v-for="edge in topology.cycle_edges" :key="`${edge.prerequisite_id}-${edge.target_id}`">
              #{{ edge.prerequisite_id }} → #{{ edge.target_id }}
            </span>
          </p>
          <p v-else class="topology__order">
            拓扑序（#{{ topology.order.length }} 个知识点）：
            {{ topology.order.map((id) => `#${id}`).join(' → ') }}
          </p>
        </div>
      </template>
    </SectionCard>
  </div>
</template>

<style scoped>
.graph-form {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(12rem, 1fr));
  gap: 0 var(--space-4);
  align-items: end;
  margin-bottom: var(--space-2);
}

.graph-form button {
  justify-self: start;
}

.stats {
  font-variant-numeric: tabular-nums;
  margin-bottom: var(--space-2);
}

.hint--warning {
  color: var(--color-warning-text, #7a5300);
}

.path-steps {
  margin: 0;
  padding-left: 1.4rem;
}

.topology-button {
  margin-top: var(--space-3);
}

.topology {
  margin-top: var(--space-2);
  font-size: var(--font-size-sm);
}

.topology__order {
  font-family: var(--font-mono);
  word-break: break-all;
}
</style>
