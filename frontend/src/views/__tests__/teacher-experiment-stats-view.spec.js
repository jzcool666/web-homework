/**
 * 教师实验统计页的接线测试（SPEC-014 E058）。
 *
 * 挂载真实组件、走真实加载逻辑：请求路径必须只带非空筛选条件，
 * 页面展示的数字必须与服务器返回一致；null 通过率显示「—」而不是 0%。
 */

import { createPinia, setActivePinia } from 'pinia'
import { flushPromises, mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { api } from '@/api/client'
import TeacherExperimentStatsView from '@/views/TeacherExperimentStatsView.vue'

vi.mock('@/api/client', () => ({
  API_BASE: '/api/v1',
  api: { get: vi.fn(), post: vi.fn(), put: vi.fn(), patch: vi.fn() },
}))

const CLASSES = [
  { id: 1, name: '软件工程示例班' },
  { id: 2, name: '网络工程示例班' },
]

const EXPERIMENTS = [
  { id: 11, title: '模 6 计数器：从 4 开始的四拍' },
  { id: 12, title: '模 6 计数器：从 0 开始的两拍' },
]

function statsPayload() {
  return {
    window: { from: '2026-08-30T00:00:00Z', to: '2026-09-29T00:00:01Z' },
    published_count: 2,
    participants: 2,
    passed_students: 1,
    pass_rate: 0.5,
    attempt_count: 4,
    experiments: [
      {
        experiment_id: 11,
        title: '模 6 计数器：从 4 开始的四拍',
        participants: 2,
        passed_students: 1,
        attempt_count: 4,
        pass_rate: 0.5,
      },
      {
        experiment_id: 12,
        title: '模 6 计数器：从 0 开始的两拍',
        participants: 0,
        passed_students: 0,
        attempt_count: 0,
        pass_rate: null,
      },
    ],
  }
}

async function setup() {
  setActivePinia(createPinia())
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/', name: 'home', component: { template: '<div />' } }],
  })
  await router.push('/')
  await router.isReady()

  api.get.mockImplementation((path) => {
    if (path.startsWith('/classes')) return Promise.resolve(CLASSES)
    if (path.startsWith('/experiments')) return Promise.resolve(EXPERIMENTS)
    if (path.startsWith('/analytics/experiment')) return Promise.resolve(statsPayload())
    return Promise.reject(new Error(`unexpected path: ${path}`))
  })

  const wrapper = mount(TeacherExperimentStatsView, { global: { plugins: [router] } })
  await flushPromises()
  return wrapper
}

describe('TeacherExperimentStatsView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('默认加载第一个班级的统计，且不带空筛选条件', async () => {
    const wrapper = await setup()

    expect(api.get).toHaveBeenCalledWith('/analytics/experiment?class_id=1')
    const tiles = wrapper.findAll('.tile__value').map((node) => node.text())
    expect(tiles).toEqual(['2', '2', '1', '50.0%', '4'])
  })

  it('逐实验明细显示通过率；无参与显示「—」', async () => {
    const wrapper = await setup()

    const rows = wrapper.findAll('tbody tr')
    expect(rows).toHaveLength(2)
    const first = rows[0].findAll('td').map((cell) => cell.text())
    expect(first).toEqual(['模 6 计数器：从 4 开始的四拍', '2', '1', '4', '50.0%'])
    const second = rows[1].findAll('td').map((cell) => cell.text())
    expect(second).toEqual(['模 6 计数器：从 0 开始的两拍', '0', '0', '0', '—'])
  })

  it('导出 CSV 使用同一组筛选条件', async () => {
    const wrapper = await setup()

    const csv = wrapper.get('a[href*="format=csv"]')
    expect(csv.attributes('href')).toBe('/api/v1/analytics/experiment?class_id=1&format=csv')
  })

  it('切换班级后按新 class_id 重新请求', async () => {
    const wrapper = await setup()

    await wrapper.get('#es_class').setValue(2)
    await flushPromises()

    expect(api.get).toHaveBeenLastCalledWith('/analytics/experiment?class_id=2')
  })

  it('选择实验后带上 experiment_id', async () => {
    const wrapper = await setup()

    await wrapper.get('#es_experiment').setValue(12)
    await flushPromises()

    expect(api.get).toHaveBeenLastCalledWith('/analytics/experiment?class_id=1&experiment_id=12')
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
      if (path.startsWith('/experiments')) return Promise.resolve(EXPERIMENTS)
      return Promise.reject(new Error('班级不存在'))
    })

    const wrapper = mount(TeacherExperimentStatsView, { global: { plugins: [router] } })
    await flushPromises()

    expect(wrapper.text()).toContain('班级不存在')
    expect(wrapper.find('tbody').exists()).toBe(false)
  })
})
