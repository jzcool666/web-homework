/**
 * 学生状态表识别页的接线测试（SPEC-017 E069/E070）。
 *
 * 挂载真实组件、走真实上传：multipart 必须带 image/class_id/kind 三个字段；
 * 成功结果显示状态序列与次态转换，并固定标注「需人工核对」；
 * 失败结果显示中文格式原因而不是猜测的状态。
 */

import { createPinia, setActivePinia } from 'pinia'
import { flushPromises, mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { api } from '@/api/client'
import StudentRecognitionView from '@/views/StudentRecognitionView.vue'

vi.mock('@/api/client', () => ({
  API_BASE: '/api/v1',
  api: { get: vi.fn(), post: vi.fn(), postForm: vi.fn(), put: vi.fn(), patch: vi.fn() },
}))

const CLASSES = [{ id: 1, name: '软件工程示例班' }]

const DONE_TASK = {
  id: 7,
  class_id: 1,
  kind: 'state_table',
  status: 'done',
  created_at: '2026-10-02T03:00:00Z',
  result: {
    rows: 3,
    cols: 4,
    states: [
      { row: 0, value: 0 },
      { row: 1, value: 1 },
      { row: 2, value: 2 },
    ],
    transitions: [
      { from: 0, to: 1 },
      { from: 1, to: 2 },
    ],
    confidence: 0.9375,
    requires_review: true,
  },
  error: null,
}

const FAILED_TASK = {
  ...DONE_TASK,
  id: 8,
  status: 'failed',
  result: null,
  error: { code: 'GRID_NOT_DETECTED', message: '未检测到网格', details: {} },
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
    return Promise.reject(new Error(`unexpected path: ${path}`))
  })

  const wrapper = mount(StudentRecognitionView, { global: { plugins: [router] } })
  await flushPromises()
  return wrapper
}

async function pickFile(wrapper, name = 'state.png') {
  const file = new File([new Uint8Array([137, 80, 78, 71])], name, { type: 'image/png' })
  const input = wrapper.get('#r_image')
  Object.defineProperty(input.element, 'files', { value: [file], configurable: true })
  await input.trigger('change')
  return file
}

describe('StudentRecognitionView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('未选文件时给出提示且不发请求', async () => {
    const wrapper = await setup()

    await wrapper.get('button.button--primary').trigger('click')
    await flushPromises()

    expect(api.postForm).not.toHaveBeenCalled()
    expect(wrapper.text()).toContain('请先选择一张状态表图片')
  })

  it('上传时带上 image/class_id/kind 三个字段', async () => {
    const wrapper = await setup()
    const file = await pickFile(wrapper)
    api.postForm.mockResolvedValue(DONE_TASK)

    await wrapper.get('button.button--primary').trigger('click')
    await flushPromises()

    expect(api.postForm).toHaveBeenCalledTimes(1)
    const [path, form] = api.postForm.mock.calls[0]
    expect(path).toBe('/recognition-tasks')
    expect(form).toBeInstanceOf(FormData)
    expect(form.get('image')).toBe(file)
    expect(form.get('class_id')).toBe('1')
    expect(form.get('kind')).toBe('state_table')
  })

  it('成功时展示状态序列、次态转换与人工核对标注', async () => {
    const wrapper = await setup()
    await pickFile(wrapper)
    api.postForm.mockResolvedValue(DONE_TASK)

    await wrapper.get('button.button--primary').trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('识别完成')
    expect(wrapper.text()).toContain('93.8%')
    expect(wrapper.text()).toContain('3 行 × 4 列')
    const rows = wrapper.findAll('tbody tr')
    expect(rows).toHaveLength(3)
    expect(rows[0].findAll('td').map((cell) => cell.text())).toEqual(['1', '0000', '0'])
    expect(rows[2].findAll('td').map((cell) => cell.text())).toEqual(['3', '0010', '2'])
    expect(wrapper.findAll('.transitions li').map((item) => item.text())).toEqual([
      '0000 → 0001',
      '0001 → 0010',
    ])
    expect(wrapper.text()).toContain('需人工核对')
    expect(wrapper.text()).toContain('不采用识别结论或客户端字段')
  })

  it('失败时展示中文格式原因且不显示状态表', async () => {
    const wrapper = await setup()
    await pickFile(wrapper)
    api.postForm.mockResolvedValue(FAILED_TASK)

    await wrapper.get('button.button--primary').trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('识别失败')
    expect(wrapper.text()).toContain('未检测到网格')
    expect(wrapper.find('tbody').exists()).toBe(false)
    expect(wrapper.text()).not.toContain('置信度')
  })

  it('上传被拒绝时显示服务端错误', async () => {
    const wrapper = await setup()
    await pickFile(wrapper, 'state.gif')
    api.postForm.mockRejectedValue(new Error('仅支持 PNG、JPEG 图片'))

    await wrapper.get('button.button--primary').trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('仅支持 PNG、JPEG 图片')
    expect(wrapper.find('tbody').exists()).toBe(false)
  })
})
