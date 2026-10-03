/**
 * 教师演示控制台的接线测试（SPEC-012 E054）。
 *
 * 这些用例挂载真实组件并点击真实按钮：动作请求必须带 expected_version，
 * 状态一律以服务器返回为准。曾经出现过「点击后请求根本没发出」的接线错误
 * （处理函数引用了已删除的变量），只测工具函数抓不到，因此在这里覆盖。
 */

import { createPinia, setActivePinia } from 'pinia'
import { flushPromises, mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { api } from '@/api/client'
import TeacherDemoView from '@/views/TeacherDemoView.vue'

vi.mock('@/api/client', () => ({ api: { get: vi.fn(), post: vi.fn() } }))

const DEMO = {
  id: 1,
  class_id: 1,
  experiment_id: 1,
  active: true,
  version: 3,
  state: { clock: 0, inputs: { d: 0, reset: 0 }, q: 0, step_no: 0 },
  history: [],
  reveal_next: false,
  next_q: null,
  last_updated: '2026-09-29T00:00:00Z',
  experiment: {
    id: 1,
    title: 'D 触发器：有效上升沿把 D 送入 Q',
    simulator_type: 'd',
    config: { initial_q: 0 },
    steps_md: '初态 Q=0。',
  },
}

async function setup() {
  const pinia = createPinia()
  setActivePinia(pinia)
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/teacher/demos/:id', name: 'teacher-demo', component: TeacherDemoView },
      { path: '/teacher/demos/:id/present', name: 'teacher-demo-present', component: { template: '<div />' } },
      { path: '/teacher/classroom', name: 'teacher-classroom', component: { template: '<div />' } },
    ],
  })
  await router.push('/teacher/demos/1')
  await router.isReady()
  const wrapper = mount(TeacherDemoView, { global: { plugins: [pinia, router] } })
  await flushPromises()
  return wrapper
}

function buttonWith(wrapper, text) {
  const found = wrapper.findAll('button').find((button) => button.text().includes(text))
  expect(found, `找不到按钮「${text}」`).toBeTruthy()
  return found
}

describe('教师演示控制台', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    api.get.mockImplementation((path) =>
      path === '/classes?page_size=100' ? Promise.resolve([]) : Promise.resolve(structuredClone(DEMO)),
    )
  })

  it('切换时钟带 expected_version 发送动作并采用服务器状态', async () => {
    api.post.mockResolvedValue({
      ...structuredClone(DEMO),
      version: 4,
      state: { clock: 1, inputs: { d: 0, reset: 0 }, q: 0, step_no: 1 },
      history: [
        { seq: 1, op: 'toggle_clock', clock: 1, inputs: { d: 0, reset: 0 }, q_before: 0, q: 0, rising: true, step_no: 1 },
      ],
    })

    const wrapper = await setup()
    await buttonWith(wrapper, '切换时钟半周期').trigger('click')
    await flushPromises()

    expect(api.post).toHaveBeenCalledWith('/demo-sessions/1/actions', {
      expected_version: 3,
      event: { op: 'toggle_clock' },
    })
    expect(wrapper.text()).toContain('版本 4')
    expect(wrapper.text()).toContain('第 1 拍')
  })

  it('输入按钮按模型引脚发送 set 事件', async () => {
    api.post.mockResolvedValue(structuredClone(DEMO))
    const wrapper = await setup()

    await wrapper.find('button.input-toggle').trigger('click')
    await flushPromises()

    expect(api.post).toHaveBeenCalledWith('/demo-sessions/1/actions', {
      expected_version: 3,
      event: { op: 'set', inputs: { d: 1 } },
    })
  })

  it('高电平时前进一步串行发送下降沿和上升沿，采用每次回执版本', async () => {
    api.get.mockImplementation((path) => path === '/classes?page_size=100' ? Promise.resolve([]) : Promise.resolve({ ...structuredClone(DEMO), state: { ...DEMO.state, clock: 1 } }))
    api.post.mockResolvedValueOnce({ ...structuredClone(DEMO), version: 4, state: { ...DEMO.state, clock: 0 } })
      .mockResolvedValueOnce({ ...structuredClone(DEMO), version: 5, state: { ...DEMO.state, clock: 1, q: 1, step_no: 1 } })
    const wrapper = await setup()
    await buttonWith(wrapper, '前进一步').trigger('click')
    await flushPromises()
    expect(api.post).toHaveBeenNthCalledWith(1, '/demo-sessions/1/actions', { expected_version: 3, event: { op: 'toggle_clock' } })
    expect(api.post).toHaveBeenNthCalledWith(2, '/demo-sessions/1/actions', { expected_version: 4, event: { op: 'toggle_clock' } })
    expect(wrapper.text()).toContain('版本 5')
    expect(wrapper.find('.decimal-display strong').text()).toBe('1')
  })

  it('低电平时前进一步只发一个上升沿请求', async () => {
    api.post.mockResolvedValue({ ...structuredClone(DEMO), version: 4, state: { ...DEMO.state, clock: 1, step_no: 1 } })
    const wrapper = await setup()
    await buttonWith(wrapper, '前进一步').trigger('click')
    await flushPromises()
    expect(api.post).toHaveBeenCalledTimes(1)
  })

  it('高电平前进的第一个请求冲突时停止，不继续或自动重放', async () => {
    api.get.mockImplementation((path) => path === '/classes?page_size=100' ? Promise.resolve([]) : Promise.resolve({ ...structuredClone(DEMO), state: { ...DEMO.state, clock: 1 } }))
    api.post.mockRejectedValue(new Error('演示已更新，请刷新后再操作'))
    const wrapper = await setup()
    await buttonWith(wrapper, '前进一步').trigger('click')
    await flushPromises()
    expect(api.post).toHaveBeenCalledTimes(1)
    expect(wrapper.text()).toContain('演示已更新')
  })

  it('等待回执期间重复前进不会发送第二个请求', async () => {
    let resolve
    api.post.mockImplementation(() => new Promise(done => { resolve = done }))
    const wrapper = await setup()
    await buttonWith(wrapper, '前进一步').trigger('click')
    await buttonWith(wrapper, '前进一步').trigger('click')
    expect(api.post).toHaveBeenCalledTimes(1)
    resolve(structuredClone(DEMO))
    await flushPromises()
  })

  it('预测未揭示时只显示待揭示，不显示下一状态', async () => {
    const wrapper = await setup()
    expect(wrapper.text()).toContain('待揭示')
    expect(wrapper.text()).not.toMatch(/下一状态 Q\(t\+1\)\s*\|?\s*1/)
  })

  it('揭示后采用服务器的 next_q', async () => {
    api.post.mockResolvedValue({
      ...structuredClone(DEMO),
      version: 4,
      reveal_next: true,
      next_q: 1,
    })
    const wrapper = await setup()
    await buttonWith(wrapper, '揭示下一状态').trigger('click')
    await flushPromises()

    expect(api.post).toHaveBeenCalledWith('/demo-sessions/1/actions', {
      expected_version: 3,
      action: { op: 'set_reveal', value: true },
    })
    // 按钮切换为「隐藏下一状态」，说明组件已采用服务器返回的 reveal_next
    expect(buttonWith(wrapper, '隐藏下一状态')).toBeTruthy()
  })

  it('版本冲突时显示服务端原因并重新拉取状态', async () => {
    api.post.mockRejectedValue(Object.assign(new Error('演示已更新，请刷新后再操作'), { status: 409 }))
    const wrapper = await setup()

    await buttonWith(wrapper, '切换时钟半周期').trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('演示已更新，请刷新后再操作')
    expect(api.get).toHaveBeenCalledWith('/demo-sessions/1')
  })

  it('演示结束后不再允许发送动作', async () => {
    api.get.mockImplementation((path) =>
      path === '/classes?page_size=100'
        ? Promise.resolve([])
        : Promise.resolve({ ...structuredClone(DEMO), active: false }),
    )
    const wrapper = await setup()
    await flushPromises()

    expect(buttonWith(wrapper, '切换时钟半周期').attributes('disabled')).toBeDefined()
    expect(wrapper.text()).toContain('演示已结束')
  })
})
