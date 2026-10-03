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

/** 只按已有边安排位置；稳定排序，环和孤立点仍保留，不编造先修关系。 */
export function graphLayout(nodes = [], edges = []) {
  const ids = nodes.map(node => node.knowledge_id).sort((a, b) => a - b)
  const degrees = new Map(ids.map(id => [id, 0]))
  const targets = new Map(ids.map(id => [id, []]))
  const levels = new Map(ids.map(id => [id, 0]))
  for (const edge of edges) {
    if (!degrees.has(edge.prerequisite_id) || !degrees.has(edge.target_id)) continue
    targets.get(edge.prerequisite_id).push(edge.target_id)
    degrees.set(edge.target_id, degrees.get(edge.target_id) + 1)
  }
  const queue = ids.filter(id => degrees.get(id) === 0)
  const seen = new Set()
  while (queue.length) {
    const id = queue.shift()
    seen.add(id)
    for (const target of targets.get(id).sort((a, b) => a - b)) {
      levels.set(target, Math.max(levels.get(target), levels.get(id) + 1))
      degrees.set(target, degrees.get(target) - 1)
      if (degrees.get(target) === 0) queue.push(target)
    }
  }
  // 环内节点集中放在最后一列，依然显示实际边，页面另有环警告。
  const last = Math.max(0, ...[...seen].map(id => levels.get(id))) + 1
  for (const id of ids) if (!seen.has(id)) levels.set(id, last)
  const groups = new Map()
  for (const id of ids) {
    const level = levels.get(id)
    if (!groups.has(level)) groups.set(level, [])
    groups.get(level).push(id)
  }
  const positions = new Map()
  let yOffset = 0, maxColumns = 1
  // 超过六列分成下一个区段，避免大图产生超宽canvas。
  const bands = Math.ceil((Math.max(0, ...groups.keys()) + 1) / 6)
  for (let band = 0; band < bands; band++) {
    let rows = 1
    for (let column = 0; column < 6; column++) {
      const group = groups.get(band * 6 + column) ?? []
      if (group.length) maxColumns = Math.max(maxColumns, column + 1)
      rows = Math.max(rows, group.length)
      group.forEach((id, row) => positions.set(id, { x: 120 + column * 220, y: 95 + yOffset + row * 112 }))
    }
    yOffset += rows * 112 + 60
  }
  return { positions, width: Math.max(680, maxColumns * 220 + 80), height: Math.max(420, yOffset + 100) }
}

function cardLabel(node) {
  const title = [...node.title]
  const lines = [title.slice(0, 10).join(''), title.slice(10, 20).join('') + (title.length > 20 ? '…' : '')].filter(Boolean)
  return `#${node.knowledge_id}\n${lines.join('\n')}`
}

/** ECharts 关系图配置；不依赖 DOM，可在 jsdom 下直接断言。 */
export function buildGraphOption({ nodes = [], edges = [], highlightEdges = [] } = {}) {
  const chapters = [...new Set(nodes.map((node) => node.chapter_id))].sort((a, b) => a - b)
  const highlighted = new Set(highlightEdges.map(edgeKey))
  const { positions } = graphLayout(nodes, edges)
  return {
    animation: false,
    tooltip: {
      renderMode: 'richText',
      formatter: (params) =>
        params.dataType === 'edge'
          ? `先修 → 后继：${params.data.sourceLabel} → ${params.data.targetLabel}`
          : `知识点 ${params.data.title}（#${params.data.knowledgeId}）\n章节 ${params.data.chapterId} · 第 ${params.data.depth} 层`,
    },
    legend: [{ data: chapters.map((id) => `章节 ${id}`), bottom: 0 }],
    series: [
      {
        type: 'graph',
        layout: 'none',
        left: 100, right: 100, top: 65, bottom: 85,
        roam: true,
        draggable: false,
        edgeSymbol: ['none', 'arrow'],
        edgeSymbolSize: 8,
        label: { show: true, position: 'inside', color: '#193963', fontSize: 12, lineHeight: 18, formatter: (params) => params.data.short },
        itemStyle: { borderColor: '#b6cae5', borderWidth: 1, color: '#edf4ff' },
        emphasis: { focus: 'adjacency', itemStyle: { color: '#ddeaff', borderColor: '#3564ff', borderWidth: 2 } },
        categories: chapters.map((id) => ({ name: `章节 ${id}` })),
        data: nodes.map((node) => ({
          id: String(node.knowledge_id),
          name: nodeLabel(node),
          short: cardLabel(node),
          title: node.title,
          knowledgeId: node.knowledge_id,
          chapterId: node.chapter_id,
          depth: node.depth,
          category: chapters.indexOf(node.chapter_id),
          symbol: 'roundRect',
          symbolSize: [172, 76],
          ...positions.get(node.knowledge_id),
          itemStyle: { color: ['#edf4ff', '#eff9f4', '#f5f0ff', '#fff6e7', '#eaf8fc', '#fff0f2'][chapters.indexOf(node.chapter_id) % 6] },
        })),
        links: edges.map((edge) => ({
          source: String(edge.prerequisite_id),
          target: String(edge.target_id),
          sourceLabel: `#${edge.prerequisite_id}`,
          targetLabel: `#${edge.target_id}`,
          lineStyle: {
            width: highlighted.has(edgeKey(edge)) ? 3 : 1.5,
            color: highlighted.has(edgeKey(edge)) ? '#3564ff' : '#94aaca',
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
