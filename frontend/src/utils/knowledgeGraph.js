/**
 * 知识图谱的纯换算（SPEC-016 第 4 节第 7 条）。
 *
 * 服务器已经把图算好并按权限过滤（只含已发布知识点）；这里只做展示装配：
 * 节点按章节分组、按到 root 的深度给出层级说明，并把节点编号写进标签——
 * **颜色不作唯一编码**，色觉障碍或黑白打印下靠文字与编号仍可读。
 */

export const DEPTH_LABEL = {
  0: '第 0 层（根/当前）',
  1: '第 1 层',
  2: '第 2 层',
  3: '第 3 层',
}

/** 节点标签同时给标题与编号：`模 6 计数器 (#10)`。 */
export function nodeLabel(node) {
  return `${node.title} (#${node.knowledge_id})`
}

export function nodeListLabel(node) {
  const root = node.dimension === 1 ? '，根节点集合成员' : ''
  return `${nodeLabel(node)}·第 ${node.depth} 层${root}`
}

export function summarize(graph) {
  const nodes = graph?.nodes ?? []
  const edges = graph?.edges ?? []
  const depths = nodes.map((node) => node.depth ?? 0)
  return {
    nodeCount: nodes.length,
    edgeCount: edges.length,
    maxDepth: depths.length ? Math.max(...depths) : 0,
    roots: nodes.filter((node) => node.dimension === 1).length,
    isolated: nodes.filter(
      (node) =>
        !edges.some(
          (edge) =>
            edge.prerequisite_id === node.knowledge_id || edge.target_id === node.knowledge_id,
        ),
    ).length,
  }
}

/** 环、裁剪与空数据要分别讲清楚，不能都显示成「没有内容」。 */
export function graphNotice(graph) {
  if (!graph) return null
  if (graph.has_cycle) {
    return { tone: 'danger', text: '先修关系存在环，拓扑序不可用；请修正先修关系后重试。' }
  }
  if (graph.truncated) {
    return { tone: 'warning', text: '节点数超过上限 200，已按到根节点的距离裁剪显示。' }
  }
  if ((graph.nodes ?? []).length === 0) {
    return { tone: 'neutral', text: '该范围还没有已发布的知识点或先修关系。' }
  }
  return null
}

export function edgeKey(edge) {
  return `${edge.prerequisite_id}->${edge.target_id}`
}

/** ECharts 关系图配置；不依赖 DOM，可在 jsdom 下直接断言。 */
export function buildGraphOption({ nodes = [], edges = [], highlightEdges = [] } = {}) {
  const chapters = [...new Set(nodes.map((node) => node.chapter_id))].sort((a, b) => a - b)
  const highlighted = new Set(highlightEdges.map(edgeKey))
  return {
    tooltip: {
      formatter: (params) =>
        params.dataType === 'edge'
          ? `先修 → 后继：${params.data.sourceLabel} → ${params.data.targetLabel}`
          : `知识点 ${params.data.title}（#${params.data.knowledgeId}）\n章节 ${params.data.chapterId} · 第 ${params.data.depth} 层`,
    },
    legend: [{ data: chapters.map((id) => `章节 ${id}`), bottom: 0 }],
    series: [
      {
        type: 'graph',
        layout: 'force',
        roam: true,
        draggable: true,
        edgeSymbol: ['none', 'arrow'],
        edgeSymbolSize: 8,
        label: { show: true, position: 'right', formatter: (params) => params.data.short },
        categories: chapters.map((id) => ({ name: `章节 ${id}` })),
        data: nodes.map((node) => ({
          id: String(node.knowledge_id),
          name: nodeLabel(node),
          short: `#${node.knowledge_id} ${node.title}`,
          title: node.title,
          knowledgeId: node.knowledge_id,
          chapterId: node.chapter_id,
          depth: node.depth,
          category: chapters.indexOf(node.chapter_id),
          symbolSize: 16 + 6 * Math.min(node.depth ?? 0, 3),
        })),
        links: edges.map((edge) => ({
          source: String(edge.prerequisite_id),
          target: String(edge.target_id),
          sourceLabel: `#${edge.prerequisite_id}`,
          targetLabel: `#${edge.target_id}`,
          lineStyle: {
            width: highlighted.has(edgeKey(edge)) ? 3 : 1,
            type: highlighted.has(edgeKey(edge)) ? 'solid' : 'solid',
            opacity: highlighted.size === 0 || highlighted.has(edgeKey(edge)) ? 0.9 : 0.25,
          },
        })),
      },
    ],
  }
}

/** 先修链的顺序号写在文字里，避免只靠箭头方向判断。 */
export function pathSteps(path) {
  if (!path?.matched) return []
  return (path.nodes ?? []).map((node, index) => ({
    position: index + 1,
    label: nodeLabel(node),
  }))
}
