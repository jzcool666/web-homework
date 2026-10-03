import { flushPromises, mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { api } from '@/api/client'
import StudentAssessmentView from '@/views/StudentAssessmentView.vue'

vi.mock('@/api/client', () => ({ api: { get: vi.fn(), post: vi.fn(), put: vi.fn() } }))

function deferred() {
  let resolve
  const promise = new Promise((done) => { resolve = done })
  return { promise, resolve }
}

const assessment = {
  id: 1,
  title: '随堂测',
  state: 'published',
  effective_state: 'open',
  total_score: 10,
  ends_at: '2030-01-01T00:00:00Z',
  items: [{
    id: 7, position: 1, type: 'single', stem_md: '选出正确项', points: 10,
    options: [{ key: 'A', label: '甲' }, { key: 'B', label: '乙' }],
  }],
}
const submission = { id: 9, version: 1, status: 'draft', answers: [], saved_at: null }

async function setup() {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/student/assessments/:id', name: 'student-assessment', component: StudentAssessmentView },
      { path: '/student/practice', name: 'student-practice', component: { template: '<div />' } },
      { path: '/student/results/:submissionId', name: 'student-result', component: { template: '<div />' } },
    ],
  })
  await router.push('/student/assessments/1')
  await router.isReady()
  const wrapper = mount(StudentAssessmentView, { global: { plugins: [router] } })
  await flushPromises()
  return wrapper
}

describe('学生作答自动保存', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    api.get.mockResolvedValue(structuredClone(assessment))
    api.post.mockResolvedValue(structuredClone(submission))
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })
  it('题号切换保留两题答案，提交前保存完整答案集', async () => {
    const second = { ...assessment.items[0], id: 8, position: 2, stem_md: '第二题' }
    api.get.mockResolvedValue({ ...structuredClone(assessment), items: [...structuredClone(assessment.items), second] })
    api.put.mockResolvedValue({ ...submission, version: 2, saved_at: '10:00:00' })
    const wrapper = await setup()
    await wrapper.findAll('input[type="radio"]')[0].trigger('change')
    await wrapper.findAll('button').find(button => button.text() === '下一题').trigger('click')
    expect(wrapper.text()).toContain('第二题')
    await wrapper.findAll('input[type="radio"]')[1].trigger('change')
    await wrapper.findAll('button').find(button => button.text() === '上一题').trigger('click')
    expect(wrapper.findAll('input[type="radio"]')[0].element.checked).toBe(true)
    await wrapper.findAll('button').find(button => button.text() === '立即保存').trigger('click')
    await flushPromises()
    expect(api.put.mock.calls[0][1].answers).toEqual([{ item_id: 7, selected: ['A'] }, { item_id: 8, selected: ['B'] }])
    wrapper.unmount()
  })
  it('保存失败时不发最终提交请求，保留选择供重试', async () => {
    api.put.mockRejectedValue(new Error('断线'))
    const wrapper = await setup()
    await wrapper.findAll('input[type="radio"]')[0].trigger('change')
    await wrapper.findAll('button').find(button => button.text() === '提交并判分').trigger('click')
    await flushPromises()
    expect(api.post.mock.calls.some(call => call[0].includes('finalization'))).toBe(false)
    expect(wrapper.findAll('input[type="radio"]')[0].element.checked).toBe(true)
    expect(wrapper.text()).toContain('保存失败')
    wrapper.unmount()
  })

  it('编辑发生在保存请求进行中时，下一次保存使用新版本和最新答案', async () => {
    const first = deferred()
    const second = deferred()
    api.put.mockImplementationOnce(() => first.promise).mockImplementationOnce(() => second.promise)
    const wrapper = await setup()
    const options = wrapper.findAll('input[type="radio"]')
    expect(options).toHaveLength(2)

    await options[0].trigger('change')
    const saveButton = wrapper.findAll('button').find((button) => button.text().includes('立即保存'))
    await saveButton.trigger('click')
    await flushPromises()
    expect(api.put).toHaveBeenCalledTimes(1)
    expect(api.put.mock.calls[0][1]).toMatchObject({ version: 1, answers: [{ item_id: 7, selected: ['A'] }] })

    await options[1].trigger('change')
    await new Promise((resolve) => setTimeout(resolve, 1100))
    expect(api.put).toHaveBeenCalledTimes(1)
    first.resolve({ ...submission, version: 2, saved_at: '10:00:00', answers: [{ item_id: 7, selected: ['A'] }] })
    await flushPromises()
    expect(api.put).toHaveBeenCalledTimes(2)
    expect(api.put.mock.calls[1][1]).toMatchObject({ version: 2, answers: [{ item_id: 7, selected: ['B'] }] })

    second.resolve({ ...submission, version: 3, saved_at: '10:00:01', answers: [{ item_id: 7, selected: ['B'] }] })
    await flushPromises()
    expect(wrapper.text()).toContain('已保存 10:00:01')
    wrapper.unmount()
  })
})
