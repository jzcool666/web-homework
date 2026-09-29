/**
 * 学生逐拍预测页的接线测试（SPEC-013 E050）。
 *
 * 挂载真实组件、点击真实按钮：提交必须只带 experiment_version / predictions /
 * request_key，结果完全采用服务器返回的判分；同一份提交在网络失败后重试要复用
 * 同一个 request_key（幂等），业务错误则换新 key。
 */

import { createPinia, setActivePinia } from 'pinia'
import { flushPromises, mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError, api } from '@/api/client'
import StudentExperimentView from '@/views/StudentExperimentView.vue'

vi.mock('@/api/client', () => {
  class MockApiError extends Error {
    constructor(status, code, message) {
      super(message)
      this.name = 'ApiError'
      this.status = status
      this.code = code
    }
  }
  return { ApiError: MockApiError, api: { get: vi.fn(), post: vi.fn() } }
})

const EXPERIMENT = {
  id: 1,
  title: '模 6 计数器：从 4 开始的四拍',
  simulator_type: 'counter',
  config: { initial_q: 4, modulus: 6 },
  steps_md: '初态 0100，连续切换时钟四拍。',
  input_sequence: [{ op: 'toggle_clock' }, { op: 'toggle_clock' }],
  checkpoints: [
    { index: 0, step_no: 1, inputs: { enable: 1, reset: 0 } },
    { index: 1, step_no: 2, inputs: { enable: 1, reset: 0 } },
    { index: 2, step_no: 3, inputs: { enable: 1, reset: 0 } },
    { index: 3, step_no: 4, inputs: { enable: 1, reset: 0 } },
  ],
  published: true,
  version: 1,
}

const PASSED = {
  id: 7,
  experiment_id: 1,
  passed: true,
  first_error_index: null,
  expected: [5, 0, 1, 2],
  actual: [5, 0, 1, 2],
  explanations: ['第 1 拍：预测正确。', '第 2 拍：预测正确。', '第 3 拍：预测正确。', '第 4 拍：预测正确。'],
  experiment_version: 1,
}

const FAILED = {
  ...PASSED,
  passed: false,
  first_error_index: 1,
  actual: [5, 6, 1, 2],
  explanations: [
    '第 1 拍：预测正确。',
    '第 2 拍：正确答案 0000（0），你填了 0110（6）。计数器每个有效上升沿加 1。',
    '第 3 拍：预测正确。',
    '第 4 拍：预测正确。',
  ],
}

async function setup() {
  const pinia = createPinia()
  setActivePinia(pinia)
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/student/experiments', name: 'student-experiments', component: { template: '<div />' } },
      { path: '/student/experiments/:id', name: 'student-experiment', component: StudentExperimentView },
      { path: '/student/attempts', name: 'student-attempts', component: { template: '<div />' } },
    ],
  })
  await router.push('/student/experiments/1')
  await router.isReady()
  const wrapper = mount(StudentExperimentView, { global: { plugins: [pinia, router] } })
  await flushPromises()
  return wrapper
}

function submitButton(wrapper) {
  return wrapper.findAll('button').find((button) => button.text().includes('提交预测'))
}

async function fill(wrapper, values) {
  const inputs = wrapper.findAll('input[type="number"]')
  for (let index = 0; index < values.length; index += 1) {
    await inputs[index].setValue(String(values[index]))
  }
}

describe('学生逐拍预测页', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    api.get.mockImplementation((path) => {
      if (path.startsWith('/experiments/')) return Promise.resolve(structuredClone(EXPERIMENT))
      return Promise.resolve([])
    })
  })

  it('按检查点渲染输入框，并与该拍输入对应', async () => {
    const wrapper = await setup()
    expect(wrapper.findAll('input[type="number"]')).toHaveLength(4)
    expect(wrapper.text()).toContain('第 1 拍')
    expect(wrapper.text()).toContain('第 4 拍')
    expect(wrapper.text()).toContain('EN=1 RESET=0')
  })

  it('提交只带 experiment_version、predictions 与 request_key', async () => {
    api.post.mockResolvedValue(structuredClone(PASSED))
    const wrapper = await setup()
    await fill(wrapper, [5, 0, 1, 2])
    await submitButton(wrapper).trigger('click')
    await flushPromises()

    expect(api.post).toHaveBeenCalledTimes(1)
    const [path, payload] = api.post.mock.calls[0]
    expect(path).toBe('/experiments/1/attempts')
    expect(Object.keys(payload).sort()).toEqual(['experiment_version', 'predictions', 'request_key'])
    expect(payload.experiment_version).toBe(1)
    expect(payload.predictions).toEqual([5, 0, 1, 2])
    expect(payload.request_key).toMatch(/^[0-9a-f-]{36}$/i)
    // 任何判分字段都不由前端产生
    expect(payload.passed).toBeUndefined()
    expect(payload.expected).toBeUndefined()
  })

  it('未填完时不提交并给出提示', async () => {
    const wrapper = await setup()
    await fill(wrapper, [5, 0])
    await submitButton(wrapper).trigger('click')
    await flushPromises()

    expect(api.post).not.toHaveBeenCalled()
    expect(wrapper.text()).toContain('请为每一拍填写一个状态值')
  })

  it('采用服务器的判分并逐拍标出错处', async () => {
    api.post.mockResolvedValue(structuredClone(FAILED))
    const wrapper = await setup()
    await fill(wrapper, [5, 6, 1, 2])
    await submitButton(wrapper).trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('未通过')
    expect(wrapper.text()).toContain('第 2 拍出错')
    expect(wrapper.text()).toContain('错误')
    expect(wrapper.text()).toContain('正确答案 0000（0）')
    expect(wrapper.text()).toContain('你填了 0110（6）')
  })

  it('网络失败后重试复用同一个 request_key', async () => {
    api.post.mockRejectedValueOnce(new TypeError('Failed to fetch'))
    api.post.mockResolvedValueOnce(structuredClone(PASSED))
    const wrapper = await setup()
    await fill(wrapper, [5, 0, 1, 2])

    await submitButton(wrapper).trigger('click')
    await flushPromises()
    await submitButton(wrapper).trigger('click')
    await flushPromises()

    expect(api.post).toHaveBeenCalledTimes(2)
    const first = api.post.mock.calls[0][1].request_key
    const second = api.post.mock.calls[1][1].request_key
    expect(second).toBe(first)
  })

  it('版本冲突时换新 key 并重新拉取实验', async () => {
    api.post.mockRejectedValueOnce(new ApiError(409, 'VERSION_CONFLICT', '实验已被更新，请刷新后再提交'))
    const wrapper = await setup()
    const before = api.get.mock.calls.length

    await fill(wrapper, [5, 0, 1, 2])
    await submitButton(wrapper).trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('实验已被更新，请刷新后再提交')
    expect(api.get.mock.calls.length).toBeGreaterThan(before)
    // 实验已更新，答案被清空，必须重新作答
    expect(wrapper.findAll('input[type="number"]').every((input) => input.element.value === '')).toBe(true)

    api.post.mockResolvedValueOnce(structuredClone(PASSED))
    await fill(wrapper, [5, 0, 1, 2])
    await submitButton(wrapper).trigger('click')
    await flushPromises()
    expect(api.post.mock.calls[1][1].request_key).not.toBe(api.post.mock.calls[0][1].request_key)
  })
})
