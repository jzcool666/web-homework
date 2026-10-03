/**
 * 复习推荐页与展示换算测试（SPEC-015 E065）。
 *
 * 重点断言两件容易被写错的事：
 * - `score=null` 是「基础路径、没有个性化信号」，不能显示成 0 分；
 * - 换条数时按 1—10 提交 limit，越界不发给服务器。
 */

import { createPinia, setActivePinia } from 'pinia'
import { flushPromises, mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError, api } from '@/api/client'
import StudentRecommendationsView from '@/views/StudentRecommendationsView.vue'
import {
  DEFAULT_LIMIT,
  itemLink,
  normalizeLimit,
  reasonsOf,
  scoreLabel,
  scoreTone,
  summarize,
} from '@/utils/recommendations'

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

const PAYLOAD = {
  algorithm_version: 'spec015-signals-v1',
  items: [
    {
      kind: 'knowledge',
      resource_id: 9,
      knowledge_id: 9,
      title: '二进制计数器与模值',
      score: 100.0,
      reasons: ['2/2 道相关题目首答错误（错误率 100%）'],
    },
    {
      kind: 'question',
      resource_id: 41,
      knowledge_id: 9,
      title: '模 6 计数器下一状态？',
      score: 100.0,
      reasons: ['“二进制计数器与模值”的相关练习，尚未答对'],
    },
    {
      kind: 'knowledge',
      resource_id: 1,
      knowledge_id: 1,
      title: '组合逻辑与时序逻辑的区别',
      score: null,
      reasons: ['按章节顺序的基础路径'],
    },
  ],
}

async function setup(payload = PAYLOAD) {
  api.get.mockResolvedValue(structuredClone(payload))
  const pinia = createPinia()
  setActivePinia(pinia)
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', name: 'home', component: { template: '<div />' } },
      { path: '/student/recommendations', name: 'student-recommendations', component: { template: '<div />' } },
      { path: '/student/knowledge/:id', name: 'student-knowledge', component: { template: '<div />' } },
      { path: '/student/practice', name: 'student-practice', component: { template: '<div />' } },
    ],
  })
  await router.push('/student/recommendations')
  await router.isReady()
  const wrapper = mount(StudentRecommendationsView, { global: { plugins: [pinia, router] } })
  await flushPromises()
  return wrapper
}

describe('推荐展示换算', () => {
  it('null 分值写成基础路径，不写成 0 分', () => {
    expect(scoreLabel(null)).toBe('基础路径（无个性化信号）')
    expect(scoreLabel(undefined)).toBe('基础路径（无个性化信号）')
    expect(scoreLabel(0)).toBe('个性化优先度 0')
    expect(scoreLabel(100)).toBe('个性化优先度 100')
    expect(scoreTone(null)).toBe('neutral')
    expect(scoreTone(80)).toBe('warning')
    expect(scoreTone(10)).toBe('neutral')
  })

  it('统计区分个性化与基础路径，理由过滤空值', () => {
    const stats = summarize(PAYLOAD.items)
    expect(stats).toMatchObject({ total: 3, personalized: 2, basePath: 1 })
    expect(stats.kinds).toEqual({ knowledge: 2, question: 1 })
    expect(reasonsOf({ reasons: ['a', '', null] })).toEqual(['a'])
    expect(reasonsOf({})).toEqual([])
  })

  it('知识点进详情页、练习进自练页', () => {
    expect(itemLink({ kind: 'knowledge', knowledge_id: 9 })).toEqual({
      name: 'student-knowledge',
      params: { id: 9 },
    })
    expect(itemLink({ kind: 'question', knowledge_id: 9 })).toEqual({ name: 'student-practice' })
  })

  it('limit 只放行 1—10 的整数', () => {
    expect(normalizeLimit(5)).toBe(5)
    expect(DEFAULT_LIMIT).toBe(5)
    expect(normalizeLimit(0)).toBeNull()
    expect(normalizeLimit(11)).toBeNull()
    expect(normalizeLimit('abc')).toBeNull()
  })
})

describe('复习推荐页面', () => {
  beforeEach(() => vi.clearAllMocks())

  it('默认按 limit=5 取推荐，并渲染理由与分值口径', async () => {
    const wrapper = await setup()
    expect(api.get).toHaveBeenCalledWith(`/me/recommendations?limit=${DEFAULT_LIMIT}`)
    expect(wrapper.findAll('.recommendations .card')).toHaveLength(3)

    const text = wrapper.text()
    expect(text).toContain('二进制计数器与模值')
    expect(text).toContain('2/2 道相关题目首答错误（错误率 100%）')
    expect(text).toContain('尚未答对')
    expect(text).toContain('个性化优先度 100')
    expect(text).toContain('基础路径（无个性化信号）')
    expect(text).not.toContain('个性化优先度 0')

    expect(text).toContain('个性化 2 条、基础路径 1 条')
    expect(text).toContain('spec015-signals-v1')
    // 泄题相关的说明必须在页面上
    expect(text).toContain('不会进入推荐')
    wrapper.unmount()
  })

  it('切换条数后按新的 limit 重新取', async () => {
    const wrapper = await setup()
    await wrapper.find('#r_limit').setValue('10')
    await wrapper.find('button.primary').trigger('click')
    await flushPromises()
    expect(api.get).toHaveBeenLastCalledWith('/me/recommendations?limit=10')
    wrapper.unmount()
  })

  it('没有候选时说明原因而不是空白列表', async () => {
    const wrapper = await setup({ algorithm_version: 'spec015-signals-v1', items: [] })
    expect(wrapper.find('.recommendations').exists()).toBe(false)
    expect(wrapper.text()).toContain('暂时没有可推荐的内容')
    wrapper.unmount()
  })

  it('接口失败时显示原因，不显示半截列表', async () => {
    api.get.mockRejectedValueOnce(new ApiError(403, 'FORBIDDEN', '当前角色无权执行该操作'))
    const pinia = createPinia()
    setActivePinia(pinia)
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [{ path: '/student/recommendations', name: 'student-recommendations', component: { template: '<div />' } }],
    })
    await router.push('/student/recommendations')
    await router.isReady()
    const wrapper = mount(StudentRecommendationsView, { global: { plugins: [pinia, router] } })
    await flushPromises()

    expect(wrapper.find('.error').text()).toContain('当前角色无权执行该操作')
    expect(wrapper.findAll('.recommendations .card')).toHaveLength(0)
    wrapper.unmount()
  })
})
