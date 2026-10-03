import { flushPromises, mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { api } from '@/api/client'
import StudentKnowledge from '../StudentKnowledgeView.vue'
vi.mock('@/api/client', () => ({
  api: { get: vi.fn(), put: vi.fn(), delete: vi.fn(), post: vi.fn() },
}))
async function setup() {
  const empty = { template: '<div />' }
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      {
        path: '/student/knowledge/:id',
        name: 'student-knowledge',
        component: StudentKnowledge,
      },
      { path: '/student/learning', name: 'student-learning', component: empty },
      { path: '/student/practice', name: 'student-practice', component: empty },
      {
        path: '/student/experiments/:id',
        name: 'student-experiment',
        component: empty,
      },
    ],
  })
  await router.push('/student/knowledge/1')
  await router.isReady()
  const wrapper = mount(StudentKnowledge, { global: { plugins: [router] } })
  await flushPromises()
  return { wrapper, router }
}
beforeEach(() => {
  vi.clearAllMocks()
  api.get.mockImplementation((path) =>
    path.startsWith('/knowledge-points/')
      ? Promise.resolve({
          id: Number(path.split('/').at(-1)),
          title: '知识点 ' + path.split('/').at(-1),
          body_md: '<img src=x onerror=alert(1)>',
          chapter_id: 1,
        })
      : Promise.resolve([]),
  )
})
describe('课程内容与状态隔离', () => {
  it('收藏及完成的迟到响应不修改切换后的知识点状态', async () => {
    const responses = []
    api.put.mockImplementation(
      () => new Promise((resolve) => responses.push(resolve)),
    )
    const { wrapper, router } = await setup()
    await wrapper
      .findAll('button')
      .find((button) => button.text() === '☆ 收藏')
      .trigger('click')
    await wrapper
      .findAll('button')
      .find((button) => button.text() === '标记完成')
      .trigger('click')
    expect(api.put.mock.calls[1][1].knowledge_id).toBe(1)
    await router.push('/student/knowledge/2')
    await flushPromises()
    responses[0]({})
    responses[1]({ completed: true })
    await flushPromises()
    expect(wrapper.find('h1').text()).toBe('知识点 2')
    expect(
      wrapper.findAll('button').some((button) => button.text() === '☆ 收藏'),
    ).toBe(true)
    expect(
      wrapper.findAll('button').some((button) => button.text() === '标记完成'),
    ).toBe(true)
    wrapper.unmount()
  })
  it('正文继续转义 HTML，无关联实验不生成假电路或标准状态', async () => {
    const { wrapper } = await setup()
    expect(wrapper.find('.markdown img').exists()).toBe(false)
    expect(wrapper.find('.markdown').text()).toContain(
      '<img src=x onerror=alert(1)>',
    )
    expect(wrapper.find('.circuit-preview').exists()).toBe(false)
    expect(wrapper.find('.comparison').exists()).toBe(false)
    wrapper.unmount()
  })
})
