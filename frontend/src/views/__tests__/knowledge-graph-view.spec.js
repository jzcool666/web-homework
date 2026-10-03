/**
 * 知识图谱页面与展示装配测试（SPEC-016 E066/E067/E068）。
 *
 * jsdom 下没有真实 2D 画布，ECharts 画不出来；因此这里断言的是**数据装配**
 * （节点/边/分类/高亮）与文字清单，以及画布不可用时的降级提示——页面在任何
 * 情况下都不能只剩一块空白。
 */

import { createPinia, setActivePinia } from 'pinia'
import { flushPromises, mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { api } from '@/api/client'
import KnowledgeGraphView from '@/views/KnowledgeGraphView.vue'
import {
  buildGraphOption,
  graphNotice,
  graphLayout,
  nodeListLabel,
  pathSteps,
  summarize,
} from '@/utils/knowledgeGraph'

vi.mock('@/api/client', () => ({
  api: { get: vi.fn(), post: vi.fn(), patch: vi.fn() },
}))

const CHAPTERS = [
  { id: 1, title: '第一单元 时序基础' },
  { id: 5, title: '第五单元 计数器' },
]

const POINTS = [
  { id: 9, title: '二进制计数器与模值' },
  { id: 10, title: '模 6 计数器与 5→0 回卷' },
]

const GRAPH = {
  nodes: [
    { knowledge_id: 10, title: '模 6 计数器与 5→0 回卷', chapter_id: 5, depth: 0, dimension: 1 },
    { knowledge_id: 9, title: '二进制计数器与模值', chapter_id: 5, depth: 1, dimension: 0 },
  ],
  edges: [{ prerequisite_id: 9, target_id: 10 }],
  has_cycle: false,
  truncated: false,
}

const PATH = {
  matched: true,
  nodes: [
    { knowledge_id: 9, title: '二进制计数器与模值', chapter_id: 5, depth: 0, dimension: 1 },
    { knowledge_id: 10, title: '模 6 计数器与 5→0 回卷', chapter_id: 5, depth: 1, dimension: 0 },
  ],
  edges: [{ prerequisite_id: 9, target_id: 10 }],
}

function mockApi({ graph = GRAPH, path = PATH, topology = null } = {}) {
  api.get.mockImplementation((url) => {
    if (url.startsWith('/chapters')) return Promise.resolve(structuredClone(CHAPTERS))
    if (url.startsWith('/knowledge-points')) return Promise.resolve(structuredClone(POINTS))
    if (url.startsWith('/knowledge-graph/path')) return Promise.resolve(structuredClone(path))
    if (url.startsWith('/knowledge-graph/topological')) {
      return Promise.resolve(structuredClone(topology))
    }
    return Promise.resolve(structuredClone(graph))
  })
}

async function setup(options) {
  mockApi(options)
  const pinia = createPinia()
  setActivePinia(pinia)
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', name: 'home', component: { template: '<div />' } },
      { path: '/knowledge-graph', name: 'knowledge-graph', component: { template: '<div />' } },
      { path: '/student/knowledge/:id', name: 'student-knowledge', component: { template: '<div />' } },
    ],
  })
  await router.push('/knowledge-graph')
  await router.isReady()
  const wrapper = mount(KnowledgeGraphView, { global: { plugins: [pinia, router] } })
  await flushPromises()
  return wrapper
}

describe('图谱展示装配（纯函数）', () => {
  it('节点标签与清单标签都带编号，颜色不是唯一编码', () => {
    expect(nodeListLabel(GRAPH.nodes[0])).toBe('模 6 计数器与 5→0 回卷 (#10)·第 0 层，根节点集合成员')
    const option = buildGraphOption(GRAPH)
    const series = option.series[0]
    expect(series.type).toBe('graph')
    expect(series.data.map((item) => item.name)).toEqual([
      '模 6 计数器与 5→0 回卷 (#10)',
      '二进制计数器与模值 (#9)',
    ])
    expect(series.data[0].short).toContain('#10\n')
    expect(series.data[0].title).toBe(GRAPH.nodes[0].title)
    expect(series.data[0].short.split('\n').every(line => [...line].length <= 11)).toBe(true)
    expect(series.categories).toEqual([{ name: '章节 5' }])
    expect(series.edgeSymbol).toEqual(['none', 'arrow'])
    expect(series.links[0]).toMatchObject({ source: '9', target: '10' })
  })

  it('高亮先修链只加粗链上的边，其余边降透明度', () => {
    const graph = {
      ...GRAPH,
      nodes: [
        ...GRAPH.nodes,
        { knowledge_id: 6, title: '次态推导与状态方程', chapter_id: 3, depth: 1, dimension: 0 },
      ],
      edges: [...GRAPH.edges, { prerequisite_id: 6, target_id: 10 }],
    }
    const option = buildGraphOption({ ...graph, highlightEdges: [GRAPH.edges[0]] })
    const links = option.series[0].links
    expect(links[0].lineStyle.width).toBe(3)
    expect(links[0].lineStyle.opacity).toBe(0.9)
    expect(links[1].lineStyle.width).toBe(1.5)
    expect(links[1].lineStyle.opacity).toBe(0.25)
  })

  it('统计、告警与路径步骤分别覆盖空图、环与裁剪', () => {
    expect(summarize(GRAPH)).toMatchObject({ nodeCount: 2, edgeCount: 1, maxDepth: 1, roots: 1 })

    expect(graphNotice({ ...GRAPH, has_cycle: true }).tone).toBe('danger')
    expect(graphNotice({ ...GRAPH, truncated: true }).tone).toBe('warning')
    expect(graphNotice({ nodes: [], edges: [], has_cycle: false, truncated: false }).text).toContain(
      '还没有已发布的知识点',
    )
    expect(graphNotice(GRAPH)).toBeNull()

    expect(pathSteps(PATH).map((step) => step.label)).toEqual([
      '二进制计数器与模值 (#9)',
      '模 6 计数器与 5→0 回卷 (#10)',
    ])
    expect(pathSteps({ matched: false, nodes: [], edges: [] })).toEqual([])
  })

  it('孤立节点被计入统计，不与「无边」混为一谈', () => {
    const withIsolated = {
      ...GRAPH,
      nodes: [
        ...GRAPH.nodes,
        { knowledge_id: 1, title: '组合逻辑与时序逻辑的区别', chapter_id: 1, depth: 0, dimension: 1 },
      ],
    }
    const stats = summarize(withIsolated)
    expect(stats.nodeCount).toBe(3)
    expect(stats.roots).toBe(2)
    expect(stats.isolated).toBe(1)
  })

  it('API顺序变化时位置稳定，先修与后继方向一致，分支卡片互不覆盖', () => {
    const nodes = [1, 2, 3, 4].map(knowledge_id => ({ knowledge_id }))
    const edges = [{ prerequisite_id: 1, target_id: 2 }, { prerequisite_id: 1, target_id: 3 }, { prerequisite_id: 3, target_id: 4 }]
    const original = graphLayout(nodes, edges)
    expect([...graphLayout([...nodes].reverse(), [...edges].reverse()).positions]).toEqual([...original.positions])
    for (const edge of edges) expect(original.positions.get(edge.target_id).x).toBeGreaterThan(original.positions.get(edge.prerequisite_id).x)
    const points = [...original.positions.values()]
    for (let i = 0; i < points.length; i++) for (let j = i + 1; j < points.length; j++) {
      expect(Math.abs(points[i].x - points[j].x) >= 172 || Math.abs(points[i].y - points[j].y) >= 76).toBe(true)
    }
  })

  it('环和超长链仍保留所有节点，卡片留在画布边界内', () => {
    const nodes = Array.from({ length: 20 }, (_, i) => ({ knowledge_id: i + 1, title: '长标题'.repeat(20), chapter_id: 1 }))
    const edges = nodes.slice(1).map((node, i) => ({ prerequisite_id: i + 1, target_id: node.knowledge_id }))
    const layout = graphLayout(nodes, edges)
    expect(layout.positions.size).toBe(20)
    for (const point of layout.positions.values()) {
      expect(point.x - 86).toBeGreaterThanOrEqual(0)
      expect(point.x + 86).toBeLessThan(layout.width)
      expect(point.y + 38).toBeLessThan(layout.height)
    }
    const cyclic = buildGraphOption({ nodes: nodes.slice(0, 2), edges: [{ prerequisite_id: 1, target_id: 2 }, { prerequisite_id: 2, target_id: 1 }] })
    expect(cyclic.series[0].data).toHaveLength(2)
    expect(cyclic.series[0].links).toHaveLength(2)
    expect(cyclic.tooltip.renderMode).toBe('richText')
  })
})

describe('知识图谱页面', () => {
  beforeEach(() => vi.clearAllMocks())

  it('渲染统计、文字清单与全部章节默认查询', async () => {
    const wrapper = await setup()
    expect(api.get).toHaveBeenCalledWith('/knowledge-graph')
    expect(wrapper.text()).toContain('节点 2 · 先修边 1 · 最大深度 1 · 根节点 1 · 孤立节点 0')
    expect(wrapper.text()).toContain('模 6 计数器与 5→0 回卷 (#10)')
    expect(wrapper.text()).toContain('二进制计数器与模值 (#9)')
    expect(wrapper.findAll('.node-list li')).toHaveLength(2)
    wrapper.unmount()
  })

  it('指定根节点与深度时把参数带给后端', async () => {
    const wrapper = await setup()
    await wrapper.find('#g_root').setValue('10')
    await wrapper.find('#g_depth').setValue('2')
    await wrapper.find('.graph-form').trigger('submit')
    await flushPromises()
    expect(api.get).toHaveBeenLastCalledWith('/knowledge-graph?root_id=10&depth=2')
    wrapper.unmount()
  })

  it('查询到先修链时按顺序列出节点', async () => {
    const wrapper = await setup()
    await wrapper.find('#g_from').setValue('9')
    await wrapper.find('#g_to').setValue('10')
    await wrapper.findAll('form')[1].trigger('submit')
    await flushPromises()
    expect(api.get).toHaveBeenLastCalledWith('/knowledge-graph/path?from=9&to=10')
    const steps = wrapper.findAll('.path-steps li')
    expect(steps.map((step) => step.text())).toEqual([
      '二进制计数器与模值 (#9)',
      '模 6 计数器与 5→0 回卷 (#10)',
    ])
    wrapper.unmount()
  })

  it('没有先修链时给提示，不编造中间节点', async () => {
    const wrapper = await setup({ path: { matched: false, nodes: [], edges: [] } })
    await wrapper.find('#g_from').setValue('10')
    await wrapper.find('#g_to').setValue('9')
    await wrapper.findAll('form')[1].trigger('submit')
    await flushPromises()
    expect(wrapper.text()).toContain('没有先修链')
    expect(wrapper.findAll('.path-steps li')).toHaveLength(0)
    wrapper.unmount()
  })

  it('有环时提示拓扑序不可用并列出环上的边', async () => {
    const cycle = {
      nodes: [
        { knowledge_id: 9, title: '二进制计数器与模值', chapter_id: 5, depth: 0, dimension: 1 },
        { knowledge_id: 10, title: '模 6 计数器与 5→0 回卷', chapter_id: 5, depth: 1, dimension: 0 },
      ],
      edges: [
        { prerequisite_id: 9, target_id: 10 },
        { prerequisite_id: 10, target_id: 9 },
      ],
      has_cycle: true,
      truncated: false,
    }
    const wrapper = await setup({
      graph: cycle,
      topology: { has_cycle: true, cycle_edges: cycle.edges },
    })
    expect(wrapper.text()).toContain('先修关系存在环')

    await wrapper.find('.topology-button').trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('存在环，不提供拓扑序')
    expect(wrapper.text()).toContain('#9 → #10')
    expect(wrapper.find('.topology__order').exists()).toBe(false)
    wrapper.unmount()
  })

  it('无环时显示唯一的拓扑序', async () => {
    const wrapper = await setup({ topology: { order: [9, 10], has_cycle: false, cycle_edges: [] } })
    await wrapper.find('.topology-button').trigger('click')
    await flushPromises()
    expect(wrapper.find('.topology__order').text()).toContain('#9 → #10')
    wrapper.unmount()
  })

  it('章节为空或无先修关系时说明原因而不是空白画布', async () => {
    const wrapper = await setup({
      graph: { nodes: [], edges: [], has_cycle: false, truncated: false },
    })
    expect(wrapper.text()).toContain('还没有已发布的知识点')
    expect(wrapper.findComponent({ name: 'KnowledgeGraphChart' }).exists()).toBe(false)
    wrapper.unmount()
  })

  it('节点超限时明确提示已按距离裁剪', async () => {
    const wrapper = await setup({ graph: { ...GRAPH, truncated: true } })
    expect(wrapper.text()).toContain('已按到根节点的距离裁剪显示')
    wrapper.unmount()
  })

  it('画布不可用时降级为文字清单并说明原因', async () => {
    const wrapper = await setup()
    // jsdom 里 canvas.getContext('2d') 返回 null：组件必须提前探测并降级，
    // 而不是等 ECharts 在动画帧里异步抛错（那会留下空白画布）
    const hint = wrapper.find('.hint--warning')
    expect(hint.exists()).toBe(true)
    expect(hint.text()).toContain('无法绘制关系图')
    expect(wrapper.findAll('.node-list li')).toHaveLength(2)
    wrapper.unmount()
  })
})
