/**
 * 问答语料管理与学生提问页的接线测试（SPEC-007 E059/E061）。
 *
 * 挂载真实组件、点击真实按钮：保存后必须能看到成功提示（曾经因为先清空提示
 * 再渲染而永远不显示），提交检索必须只带 query 字段。
 */

import { createPinia, setActivePinia } from 'pinia'
import { flushPromises, mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError, api } from '@/api/client'
import StudentQaView from '@/views/StudentQaView.vue'
import TeacherQaView from '@/views/TeacherQaView.vue'

vi.mock('@/api/client', () => {
  class MockApiError extends Error {
    constructor(status, code, message) {
      super(message)
      this.name = 'ApiError'
      this.status = status
      this.code = code
    }
  }
  return { ApiError: MockApiError, api: { get: vi.fn(), post: vi.fn(), patch: vi.fn() } }
})

const POINTS = [
  { id: 1, title: '组合逻辑与时序逻辑的区别' },
  { id: 2, title: '时钟信号与有效时钟沿' },
]

const ENTRY = {
  id: 5,
  knowledge_id: 1,
  question: '组合逻辑会保存状态吗？',
  answer_md: '不保存。',
  source_url: null,
  published: true,
  owner_id: 2,
  version: 1,
}

const MATCHED = {
  matched: true,
  corpus_version: 'v1-abcdef123456',
  matches: [
    {
      knowledge_id: 1,
      title: '组合逻辑与时序逻辑的区别',
      excerpt: '组合逻辑的输出只由当前输入决定。',
      source_url: 'https://computationstructures.org/notes/sequential_logic/notes.html',
      similarity: 0.4231,
    },
  ],
}

const UNMATCHED = { matched: false, corpus_version: 'v1-abcdef123456', matches: [] }

async function setup(component) {
  const pinia = createPinia()
  setActivePinia(pinia)
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', name: 'home', component: { template: '<div />' } },
      { path: '/student/knowledge/:id', name: 'student-knowledge', component: { template: '<div />' } },
      { path: '/student/learning', name: 'student-learning', component: { template: '<div />' } },
    ],
  })
  await router.push('/')
  await router.isReady()
  const wrapper = mount(component, { global: { plugins: [pinia, router] } })
  await flushPromises()
  return wrapper
}

describe('教师问答语料页', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    api.get.mockImplementation((path) => {
      if (path.startsWith('/qa-entries')) return Promise.resolve([structuredClone(ENTRY)])
      return Promise.resolve(structuredClone(POINTS))
    })
  })

  it('新增条目只提交可写字段，并显示成功提示', async () => {
    api.post.mockResolvedValue(structuredClone(ENTRY))
    const wrapper = await setup(TeacherQaView)
    expect(wrapper.findAll('tbody tr')).toHaveLength(1)

    await wrapper.find('#qa_point').setValue('2')
    await wrapper.find('#qa_question').setValue('时钟沿有什么作用？')
    await wrapper.find('#qa_answer').setValue('状态只在有效上升沿更新。')
    await wrapper.find('#qa_source').setValue('')
    await wrapper.find('form').trigger('submit')
    await flushPromises()

    expect(api.post).toHaveBeenCalledTimes(1)
    const [path, payload] = api.post.mock.calls[0]
    expect(path).toBe('/qa-entries')
    expect(payload).toEqual({
      knowledge_id: 2,
      question: '时钟沿有什么作用？',
      answer_md: '状态只在有效上升沿更新。',
      source_url: null,
      published: true,
    })
    // 成功提示必须在表单重置之后仍然可见
    expect(wrapper.text()).toContain('已新增问答条目')
  })

  it('编辑提交带 version，服务端冲突时显示原因', async () => {
    api.patch.mockRejectedValueOnce(new ApiError(409, 'VERSION_CONFLICT', '问答条目已被修改，请刷新后重试'))
    const wrapper = await setup(TeacherQaView)

    const edit = wrapper.findAll('button').find((button) => button.text().includes('编辑'))
    await edit.trigger('click')
    await flushPromises()
    expect(wrapper.find('#qa_question').element.value).toBe(ENTRY.question)

    await wrapper.find('form').trigger('submit')
    await flushPromises()

    expect(api.patch.mock.calls[0][0]).toBe('/qa-entries/5')
    expect(api.patch.mock.calls[0][1].version).toBe(1)
    expect(wrapper.text()).toContain('问答条目已被修改，请刷新后重试')
  })
})

describe('学生提问页', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('提交检索只带 query，并展示来源与相似度', async () => {
    api.post.mockResolvedValue(structuredClone(MATCHED))
    const wrapper = await setup(StudentQaView)

    await wrapper.find('#qa_query').setValue('组合逻辑会保存状态吗')
    await wrapper.find('form').trigger('submit')
    await flushPromises()

    expect(api.post).toHaveBeenCalledWith('/qa/queries', { query: '组合逻辑会保存状态吗' })
    expect(wrapper.text()).toContain('组合逻辑与时序逻辑的区别')
    expect(wrapper.text()).toContain('文本相似度 42%')
    expect(wrapper.text()).toContain('computationstructures.org')
    expect(wrapper.text()).toContain('语料版本 v1-abcdef123456')
    // 相似度不等于正确率，页面上必须写明
    expect(wrapper.text()).toContain('不是')
  })

  it('没有匹配时给出章节浏览入口而不是编造解释', async () => {
    api.post.mockResolvedValue(structuredClone(UNMATCHED))
    const wrapper = await setup(StudentQaView)

    await wrapper.find('#qa_query').setValue('今天天气怎么样')
    await wrapper.find('form').trigger('submit')
    await flushPromises()

    expect(wrapper.text()).toContain('没有可靠匹配')
    expect(wrapper.text()).toContain('按章节浏览课程')
    expect(wrapper.findAll('.matches li')).toHaveLength(0)
  })

  it('少于 2 个字符不提交', async () => {
    const wrapper = await setup(StudentQaView)
    await wrapper.find('#qa_query').setValue('计')
    expect(wrapper.find('button[type="submit"]').attributes('disabled')).toBeDefined()
    expect(api.post).not.toHaveBeenCalled()
  })
})
