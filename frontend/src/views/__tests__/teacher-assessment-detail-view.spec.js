import { flushPromises, mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { api } from '@/api/client'
import TeacherAssessmentDetailView from '@/views/TeacherAssessmentDetailView.vue'

vi.mock('@/api/client', () => ({
  API_BASE: '/api/v1',
  api: { get: vi.fn(), post: vi.fn(), patch: vi.fn() },
}))

const detail = {
  id: 1, class_id: 1, title: '随堂测', kind: 'quiz', state: 'closed',
  effective_state: 'closed', feedback_released: true, total_score: 10, version: 3,
  starts_at: '2026-09-29T00:00:00Z', ends_at: '2026-09-29T00:10:00Z',
  items: [{
    id: 7, question_id: 4, position: 1, points: 10, type: 'single',
    stem_md: '发布时的题目', options: [{ key: 'A', label: '甲' }, { key: 'B', label: '乙' }],
    answer: ['A'], explanation_md: '发布时的解析',
  }],
}
const stats = {
  assessments: [{ id: 1, roster_count: 4, submitted_count: 3, blank_count: 1, submission_rate: 0.75, mean_percent: 33.33 }],
  items: [{ item_id: 7, answered_count: 3, unanswered_count: 1, correct_count: 2, correct_rate: 0.6667, option_counts: { A: 2 } }],
  score_buckets: [{ range: '0-<60', count: 2 }, { range: '90-100', count: 1 }],
}

async function setup() {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/teacher/assessments/:id', name: 'teacher-assessment-detail', component: TeacherAssessmentDetailView },
      { path: '/teacher/assessments', name: 'teacher-assessments', component: { template: '<div />' } },
    ],
  })
  await router.push('/teacher/assessments/1')
  await router.isReady()
  const wrapper = mount(TeacherAssessmentDetailView, { global: { plugins: [router] } })
  await flushPromises()
  return wrapper
}

describe('测评讲评和投屏', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    api.get.mockImplementation((path) => {
      if (path === '/assessments/1') return Promise.resolve(structuredClone(detail))
      if (path.startsWith('/analytics/assessment')) return Promise.resolve(structuredClone(stats))
      // 题库的当前答案已经改成 B；讲评应继续显示测评快照里的 A。
      if (path === '/questions?page_size=100') return Promise.resolve([{ id: 4, answer: ['B'] }])
      return Promise.reject(new Error('unexpected GET'))
    })
  })

  it('讲评显示冻结答案，投屏只显示匿名聚合面板', async () => {
    const wrapper = await setup()
    expect(wrapper.text()).toContain('参考答案 甲')
    expect(wrapper.text()).not.toContain('参考答案 乙')

    const button = wrapper.findAll('button').find((entry) => entry.text().includes('投屏统计'))
    await button.trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('提交率')
    expect(wrapper.text()).toContain('75%')
    expect(wrapper.text()).not.toContain('发布时的题目')
    expect(wrapper.text()).not.toContain('参考答案')
    expect(wrapper.text()).toContain('退出投屏')
    wrapper.unmount()
  })
})
