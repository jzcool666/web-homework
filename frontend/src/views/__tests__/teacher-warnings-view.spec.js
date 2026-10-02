/**
 * 教师学习预警页的接线测试（SPEC-004 E063/E064）。
 *
 * 挂载真实组件、点击真实按钮：生成快照必须发 POST /warnings/generations 且带上
 * 班级与窗口；页面读取走 GET /warnings 且只展示最近批次；样本不足显示「样本不足」
 * 而不是低风险，分数为 null 时显示「—」。
 */

import { createPinia, setActivePinia } from 'pinia'
import { flushPromises, mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { api } from '@/api/client'
import TeacherWarningsView from '@/views/TeacherWarningsView.vue'

vi.mock('@/api/client', () => ({
  API_BASE: '/api/v1',
  api: { get: vi.fn(), post: vi.fn(), put: vi.fn(), patch: vi.fn() },
}))

const CLASSES = [{ id: 1, name: '软件工程示例班' }]

const WARNINGS = [
  {
    student_id: 11,
    score: 70.0,
    level: 'high',
    factors: { attendance: 0.5, progress: 0.25, accuracy: 1.0 },
    available_factors: ['attendance', 'progress', 'accuracy'],
    sample_counts: { attendance: 2, progress: 4, accuracy: 3 },
    cluster_label: 2,
    reasons: ['出勤：风险 0.50（出勤表现 0.50），权重 0.3'],
    generated_at: '2026-10-02T02:00:00Z',
  },
  {
    student_id: 12,
    score: null,
    level: 'insufficient',
    factors: { attendance: 0.5, progress: null, accuracy: null },
    available_factors: ['attendance'],
    sample_counts: { attendance: 2, progress: 0, accuracy: 0 },
    cluster_label: null,
    reasons: ['学习进度：没有明确的完成/未完成记录，未计入'],
    generated_at: '2026-10-02T02:00:00Z',
  },
]

async function setup(initial = WARNINGS) {
  setActivePinia(createPinia())
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/', name: 'home', component: { template: '<div />' } }],
  })
  await router.push('/')
  await router.isReady()

  api.get.mockImplementation((path) => {
    if (path.startsWith('/classes')) return Promise.resolve(CLASSES)
    if (path.startsWith('/warnings?')) return Promise.resolve(initial)
    return Promise.reject(new Error(`unexpected path: ${path}`))
  })

  const wrapper = mount(TeacherWarningsView, { global: { plugins: [router] } })
  await flushPromises()
  return wrapper
}

describe('TeacherWarningsView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('初始读取最近批次，请求带班级、窗口与分页', async () => {
    await setup()

    const called = api.get.mock.calls.map(([path]) => path).find((p) => p.startsWith('/warnings?'))
    expect(called).toContain('class_id=1')
    expect(called).toContain('from=')
    expect(called).toContain('page_size=100')
  })

  it('展示等级、分数、风险因素、可用因素、分组与证据', async () => {
    const wrapper = await setup()

    const rows = wrapper.findAll('tbody tr')
    expect(rows).toHaveLength(2)
    const first = rows[0].findAll('td').map((cell) => cell.text())
    expect(first[0]).toBe('#11')
    expect(first[1]).toBe('高')
    expect(first[2]).toBe('70.0')
    expect(first.slice(3, 6)).toEqual(['0.50', '0.25', '1.00'])
    expect(first[6]).toBe('出勤、学习进度、知识点首答')
    expect(first[7]).toBe('组 2')
    expect(rows[0].text()).toContain('出勤：风险 0.50')
  })

  it('样本不足时显示等级文案与「—」，未计入的因素标为未计入', async () => {
    const wrapper = await setup()

    const second = wrapper.findAll('tbody tr')[1].findAll('td').map((cell) => cell.text())
    expect(second[1]).toBe('样本不足')
    expect(second[2]).toBe('—')
    expect(second.slice(3, 6)).toEqual(['0.50', '未计入', '未计入'])
    expect(second[6]).toBe('出勤')
  })

  it('点击生成快照发送 POST，并用响应替换列表', async () => {
    const wrapper = await setup([])
    expect(wrapper.text()).toContain('该窗口还没有预警批次')

    api.post.mockResolvedValue({
      generated_at: '2026-10-02T03:00:00Z',
      algorithm_version: 'warn-rules-v1',
      cluster_reason: '三因素齐全的学生只有 1 名，少于 10 名，未分组',
      disclaimer: '等级由项目规则计算',
      students: WARNINGS,
    })

    await wrapper.get('button.button--primary').trigger('click')
    await flushPromises()

    expect(api.post).toHaveBeenCalledTimes(1)
    const [path, payload] = api.post.mock.calls[0]
    expect(path).toBe('/warnings/generations')
    expect(payload.class_id).toBe(1)
    expect(payload.from).toMatch(/T00:00:00Z$/)
    expect(payload.to).toMatch(/T00:00:00Z$/)

    expect(wrapper.findAll('tbody tr')).toHaveLength(2)
    expect(wrapper.text()).toContain('少于 10 名')
  })

  it('接口报错时显示错误而不是空表', async () => {
    setActivePinia(createPinia())
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [{ path: '/', name: 'home', component: { template: '<div />' } }],
    })
    await router.push('/')
    await router.isReady()
    api.get.mockImplementation((path) => {
      if (path.startsWith('/classes')) return Promise.resolve(CLASSES)
      return Promise.reject(new Error('班级不存在'))
    })

    const wrapper = mount(TeacherWarningsView, { global: { plugins: [router] } })
    await flushPromises()

    expect(wrapper.text()).toContain('班级不存在')
    expect(wrapper.find('tbody').exists()).toBe(false)
  })
})
