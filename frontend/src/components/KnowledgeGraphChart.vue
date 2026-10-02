<script setup>
/**
 * 知识图谱画布（SPEC-016 第 4 节第 7 条）。
 *
 * ECharts 只负责画；服务器返回的节点/边同时以文字清单渲染，因此
 * 「节点按章节或深度区分、并以文字与编号同时标注」不依赖画布是否可用：
 * 画布初始化失败（例如无 2D 上下文的环境）时降级为清单 + 明确提示，
 * 不静默变成一块空白。
 */
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'

import { GraphChart } from 'echarts/charts'
import { LegendComponent, TooltipComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import * as echarts from 'echarts/core'

import { buildGraphOption, nodeListLabel } from '@/utils/knowledgeGraph'

echarts.use([GraphChart, TooltipComponent, LegendComponent, CanvasRenderer])

const props = defineProps({
  graph: { type: Object, default: null },
  highlightEdges: { type: Array, default: () => [] },
})

const canvasEl = ref(null)
const renderError = ref(null)
let chart = null

/** 没有 2D 上下文时 ECharts 会在动画帧里异步抛错，所以在初始化前先探测。 */
let canvasSupported = null

function canvasUsable() {
  if (canvasSupported !== null) return canvasSupported
  try {
    const probe = document.createElement('canvas')
    const context = probe.getContext && probe.getContext('2d')
    canvasSupported = Boolean(context && typeof context.clearRect === 'function')
  } catch {
    canvasSupported = false
  }
  return canvasSupported
}

function draw() {
  if (!canvasEl.value || !props.graph) return
  if (!canvasUsable()) {
    renderError.value = '当前环境没有 2D 绘图上下文'
    return
  }
  const option = buildGraphOption({
    nodes: props.graph.nodes ?? [],
    edges: props.graph.edges ?? [],
    highlightEdges: props.highlightEdges ?? [],
  })
  if (!chart) {
    try {
      chart = echarts.init(canvasEl.value, null, { width: 900, height: 480 })
    } catch (err) {
      renderError.value = err?.message || '图形渲染不可用'
      return
    }
  }
  if (!chart) return
  try {
    chart.setOption(option, true)
    renderError.value = null
  } catch (err) {
    renderError.value = err?.message || '图形渲染不可用'
  }
}

function resize() {
  if (chart) chart.resize()
}

onMounted(() => {
  draw()
  window.addEventListener('resize', resize)
})

watch(() => [props.graph, props.highlightEdges], draw, { deep: true })

onBeforeUnmount(() => {
  window.removeEventListener('resize', resize)
  if (chart) {
    chart.dispose()
    chart = null
  }
})
</script>

<template>
  <div class="graph-chart">
    <div ref="canvasEl" class="graph-chart__canvas" role="img" aria-label="知识点先修关系图"></div>
    <p v-if="renderError" class="hint hint--warning">
      当前环境无法绘制关系图（{{ renderError }}）；下方文字清单是同一份数据，可照常阅读。
    </p>
    <ul v-if="graph && graph.nodes.length > 0" class="node-list">
      <li v-for="node in graph.nodes" :key="node.knowledge_id">{{ nodeListLabel(node) }}</li>
    </ul>
  </div>
</template>

<style scoped>
.graph-chart__canvas {
  width: 100%;
  height: 480px;
  border: 1px solid var(--color-border, #d8dbe0);
  border-radius: var(--radius-md, 8px);
  background: var(--color-surface, #fff);
}

.node-list {
  margin: var(--space-3) 0 0;
  padding-left: 1.2rem;
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(16rem, 1fr));
  gap: 0.25rem var(--space-4);
  font-size: var(--font-size-sm);
}

.hint--warning {
  color: var(--color-warning-text, #7a5300);
}
</style>
