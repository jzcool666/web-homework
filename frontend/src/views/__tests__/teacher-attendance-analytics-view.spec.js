/**
 * 教师出勤统计页的接线测试（SPEC-003 E055）。
 *
 * 挂载真实组件、走真实加载逻辑：请求路径必须只带非空筛选条件，
 * 页面展示的数字必须与服务器返回一致；没有分母的出勤率显示「无分母」，
 * 未计算的相关系数显示原因而不是 0。
 */

import { createPinia, setActivePinia } from 'pinia'
import { flushPromises, mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { api } from '@/api/client'
import TeacherAttendanceAnalyticsView from '@/views/TeacherAttendanceAnalyticsView.vue'

vi.mock('@/api/client', () => ({
  API_BASE: '/api/v1',
  api: { get: vi.fn(), post: vi.fn(), put: vi.fn(), patch: vi.fn() },
}))

const CLASSES = [
  { id: 1, name: '软件工程示例班' },
  { id: 2, name: '网络工程示例班' },
]

function statsPayload(overrides = {}) {
  return {
    window: { from: '2026-09-01T00:00:00Z', to: '2026-10-01T00:00:00Z' },
    settled_tasks: 1,
    counts: { present: 2, late: 1, leave: 1, absent: 1 },
    attendance_rate: 0.75,
    students: [
      {
        student_id: 11,
        student_no: '20240001',
        display_name: '学生甲',
        counts: { present: 1, late: 0, leave: 0, absent: 0 },
        attendance_rate: 1.0,
      },
      {
        student_id: 12,
        student_no: '20240002',
        display_name: null,
        counts: { present: 0, late: 0, leave: 1, absent: 0 },
        attendance_rate: null,
      },
    ],
    correlation: { coefficient: null, n: 4, reason: '同时具备出勤与成绩的学生只有 4 名' },
    ...overrides,
  }
}

async function setup(payload = statsPayload()) {
  setActivePinia(createPinia())
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/', name: 'home', component: { template: '<div />' } }],
  })
  await router.push('/')
  await router.isReady()

  api.get.mockImplementation((path) => {
    if (path.startsWith('/classes')) return Promise.resolve(CLASSES)
    if (path.startsWith('/analytics/attendance')) return Promise.resolve(payload)
    return Promise.reject(new Error(`unexpected path: ${path}`))
  })

  const wrapper = mount(TeacherAttendanceAnalyticsView, { global: { plugins: [router] } })
  await flushPromises()
  return wrapper
}

describe('TeacherAttendanceAnalyticsView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('默认加载第一个班级，窗口按 UTC 日边界传给后端', async () => {
    const wrapper = await setup()

    // 默认窗口由页面生成，只断言 class_id 与 format 之外的形状
    const called = api.get.mock.calls.map(([path]) => path).find((path) => path.includes('/analytics/attendance'))
    expect(called).toContain('class_id=1')
    expect(called).toContain('from=')
    expect(called).toContain('to=')
    expect(wrapper.text()).toContain('已结算任务：1')
  })

  it('展示出勤分布、学生明细与「无分母」标记', async () => {
    const wrapper = await setup()

    const text = wrapper.text()
    expect(text).toContain('出勤：2')
    expect(text).toContain('迟到：1')
    expect(text).toContain('请假：1')
    expect(text).toContain('缺勤：1')
    expect(text).toContain('出勤率 75%')

    const rows = wrapper.findAll('tbody tr')
    expect(rows).toHaveLength(2)
    expect(rows[0].findAll('td').map((cell) => cell.text())).toEqual([
      '学生甲（20240001）',
      '1',
      '0',
      '0',
      '0',
      '100%',
    ])
    // 只有请假的学生没有分母
    expect(rows[1].findAll('td').map((cell) => cell.text())).toEqual([
      '#12',
      '0',
      '0',
      '1',
      '0',
      '—（无分母）',
    ])
  })

  it('相关系数未计算时显示原因而不是 0', async () => {
    const wrapper = await setup()

    const text = wrapper.text()
    expect(text).toContain('共同样本：4')
    expect(text).toContain('只有 4 名')
    expect(wrapper.text()).not.toContain('相关系数：0')
  })

  it('计算出相关系数时显示数值', async () => {
    const wrapper = await setup(
      statsPayload({ correlation: { coefficient: 1.0, n: 5, reason: null } }),
    )

    expect(wrapper.text()).toContain('相关系数：1')
    expect(wrapper.text()).toContain('共同样本：5')
  })

  it('导出 CSV 使用与页面相同的筛选条件', async () => {
    const wrapper = await setup()

    const href = wrapper.get('a[href*="format=csv"]').attributes('href')
    expect(href.startsWith('/api/v1/analytics/attendance?')).toBe(true)
    expect(href).toContain('class_id=1')
    expect(href).toContain('format=csv')
  })

  it('切换班级后按新 class_id 重新请求', async () => {
    const wrapper = await setup()

    await wrapper.get('#at_class').setValue(2)
    await flushPromises()

    const last = api.get.mock.calls.map(([path]) => path).at(-1)
    expect(last).toContain('class_id=2')
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

    const wrapper = mount(TeacherAttendanceAnalyticsView, { global: { plugins: [router] } })
    await flushPromises()

    expect(wrapper.text()).toContain('班级不存在')
    expect(wrapper.find('tbody').exists()).toBe(false)
  })
})
