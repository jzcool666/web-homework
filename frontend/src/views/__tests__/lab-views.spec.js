import { createPinia, setActivePinia } from 'pinia'
import { mount, flushPromises } from '@vue/test-utils'
import { createRouter, createMemoryHistory } from 'vue-router'
import { beforeEach, afterEach, expect, it, vi } from 'vitest'
import { api, ApiError } from '@/api/client'
import { useAuthStore } from '@/stores/auth'
import LabSessionView from '@/views/LabSessionView.vue'
import LabUploadView from '@/views/LabUploadView.vue'
import LabAttemptView from '@/views/LabAttemptView.vue'
vi.mock('@/api/client', async importOriginal => ({ ...await importOriginal(), api: { get: vi.fn(), post: vi.fn(), postForm: vi.fn() } }))

const task = { id: 1, version: 1, code: 'LAB-D', title: 'D触发器', instructions_md: '先清零', ports: [{ label: 'CLK', direction: 'input', width: 1 }, { label: 'Q', direction: 'output', width: 1 }], board: { chips: [{ id: 'U1', model: '74LS74' }], terminals: [{ id: 'VCC', kind: 'rail', label: '+5V' }, { id: 'D', kind: 'switch', label: 'D' }] }, catalog: { models: [{ model: '74LS74', pin_count: 14, pins: [{ number: 14, name: 'VCC', direction: 'power' }, { number: 5, name: 'Q', direction: 'output' }] }] } }
const session = () => ({ id: 1, task, task_version: 1, owner_id: 1, kind: 'practice', version: 1, saved_at: 'now', board: { wires: [], power: false, clock: 0, switches: {} }, state: { pins: {}, outputs: { Q: 'Z' }, diagnostics: [] }, events: [] })
const wrappers = []
async function setup(view, query = '', role = 'student') {
  const pinia = createPinia(); setActivePinia(pinia); const auth = useAuthStore(); auth.user = { id: 1, role }
  const routes = [
    { path: '/labs/sessions/:id', name: 'lab-session', component: LabSessionView },
    { path: '/student/labs/:id/upload', name: 'lab-upload', component: LabUploadView },
    { path: '/lab-attempts/:id', name: 'lab-attempt', component: LabAttemptView },
    ...['student-labs', 'teacher-labs', 'student-lab-records', 'teacher-lab-records'].map(name => ({ path: `/${name}`, name, component: { template: '<div />' } })),
  ]
  const router = createRouter({ history: createMemoryHistory(), routes })
  const path = view === LabSessionView ? '/labs/sessions/1' : view === LabUploadView ? '/student/labs/1/upload' : '/lab-attempts/1'
  await router.push(path + query); await router.isReady()
  const wrapper = mount(view, { global: { plugins: [pinia, router] } }); wrappers.push(wrapper); await flushPromises(); return { wrapper, router }
}
const button = (wrapper, label) => wrapper.findAll('button').find(item => item.text().includes(label))
beforeEach(() => {
  vi.clearAllMocks()
  api.get.mockImplementation(path => Promise.resolve(path.startsWith('/classes') ? [{ id: 1, name: '甲班', active: true }] : path.startsWith('/lab-tasks') ? structuredClone(task) : session()))
  api.post.mockImplementation(async (path, body) => ({ ...session(), version: body.version + 1 }))
})
afterEach(() => { for (const wrapper of wrappers.splice(0)) wrapper.unmount() })

it('点击两个真实SVG引脚带版本发出连线动作，采用返回状态', async () => {
  const { wrapper } = await setup(LabSessionView)
  await wrapper.get('[data-endpoint="terminal:VCC"]').trigger('click')
  await wrapper.get('[data-endpoint="chip:U1:14"]').trigger('click'); await flushPromises()
  expect(api.post).toHaveBeenCalledWith('/lab-sessions/1/actions', expect.objectContaining({ version: 1, op: 'connect', payload: { from: 'terminal:VCC', to: 'chip:U1:14' } }))
  expect(api.post.mock.calls[0][1]).not.toHaveProperty('q')
})

it('网络中断保留同一个动作键重试，确认前阻止另一操作', async () => {
  api.post.mockRejectedValueOnce(new TypeError('offline')).mockResolvedValueOnce({ ...session(), version: 2 })
  const { wrapper } = await setup(LabSessionView)
  await button(wrapper, '开启电源').trigger('click'); await flushPromises()
  const first = api.post.mock.calls[0][1]
  expect(button(wrapper, '开启电源').attributes('disabled')).toBeDefined()
  await button(wrapper, '重试保存').trigger('click'); await flushPromises()
  expect(api.post.mock.calls[1][1]).toEqual(first)
})

it('409显示原因并恢复服务器过程', async () => {
  api.post.mockRejectedValueOnce(new ApiError(409, 'VERSION_CONFLICT', '过程已更新'))
  const { wrapper } = await setup(LabSessionView)
  await button(wrapper, '开启电源').trigger('click'); await flushPromises()
  expect(wrapper.text()).toContain('过程已更新'); expect(api.get).toHaveBeenCalledTimes(2)
})

it('投屏与教师读取学生会话均无编辑和提交控件', async () => {
  const presentation = await setup(LabSessionView, '?present=1', 'teacher')
  expect(button(presentation.wrapper, '开启电源')).toBeUndefined()
  expect(button(presentation.wrapper, '提交接线')).toBeUndefined()
  api.get.mockResolvedValue({ ...session(), owner_id: 2 })
  const reading = await setup(LabSessionView, '', 'teacher')
  expect(button(reading.wrapper, '开启电源')).toBeUndefined()
})

it('接线提交仅发送会话版本，不携带客户端成绩', async () => {
  api.post.mockResolvedValue({ id: 12 })
  const { wrapper, router } = await setup(LabSessionView)
  await button(wrapper, '提交接线').trigger('click'); await flushPromises()
  expect(Object.keys(api.post.mock.calls[0][1]).sort()).toEqual(['request_key', 'session_id', 'session_version', 'task_version'])
  expect(router.currentRoute.value.params.id).toBe('12')
})

it('上传走multipart，网络失败再次使用同一个key', async () => {
  api.postForm.mockRejectedValueOnce(new TypeError('offline')).mockResolvedValueOnce({ id: 7 })
  const { wrapper, router } = await setup(LabUploadView)
  const file = new File(['<project/>'], 'D.circ'); const input = wrapper.get('#circ-file')
  Object.defineProperty(input.element, 'files', { value: [file] }); await input.trigger('change')
  await wrapper.get('form').trigger('submit'); await flushPromises()
  const body = api.postForm.mock.calls[0][1]
  expect([...body.keys()].sort()).toEqual(['class_id', 'file', 'request_key', 'task_id', 'task_version'])
  expect(body.get('file')).toBe(file)
  await wrapper.get('form').trigger('submit'); await flushPromises()
  expect(api.postForm.mock.calls[1][1].get('request_key')).toBe(body.get('request_key'))
  expect(router.currentRoute.value.params.id).toBe('7')
})

it('测评故障显示无成绩，结果回放请求冻结记录的at_seq', async () => {
  const snapshot = { ...session(), events: [{ seq: 1, op: 'power', payload: { on: true }, received_at: 'now' }] }
  api.get.mockResolvedValue({ id: 2, mode: 'wiring', status: 'error', task, score: null, error: { message: '测评中断' }, session_snapshot: snapshot })
  const { wrapper } = await setup(LabAttemptView)
  expect(wrapper.text()).toContain('本次没有成绩'); expect(wrapper.text()).not.toContain('0 分')
  await button(wrapper, '上一步').trigger('click'); await flushPromises()
  expect(api.get).toHaveBeenCalledWith('/lab-attempts/1?at_seq=0')
})
