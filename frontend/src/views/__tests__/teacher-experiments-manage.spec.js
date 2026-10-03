import { createPinia, setActivePinia } from 'pinia'
import { flushPromises, mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { api, resetCsrfToken } from '@/api/client'
import { useAuthStore } from '@/stores/auth'
import TeacherExperimentsManageView from '@/views/TeacherExperimentsManageView.vue'
vi.mock('@/api/client', () => ({ api: { get: vi.fn(), post: vi.fn(), patch: vi.fn() }, resetCsrfToken: vi.fn() }))
const row = (overrides = {}) => ({ id: 1, owner_id: 1, version: 1, title: 'D采样', knowledge_id: 1, simulator_type: 'd', config: { initial_q: 0 }, steps_md: '上升沿采样。', input_sequence: [{ op: 'set', inputs: { d: 1 } }, { op: 'toggle_clock' }], checkpoints: [{ index: 0 }], published: true, ...overrides })
async function setup() {
  const pinia = createPinia(); setActivePinia(pinia); useAuthStore().user = { id: 1, role: 'teacher' }
  const router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/', component: TeacherExperimentsManageView }, { path: '/teacher/classroom', name: 'teacher-classroom', component: { template: '<div />' } }] })
  await router.push('/'); await router.isReady()
  const wrapper = mount(TeacherExperimentsManageView, { global: { plugins: [pinia, router] } }); await flushPromises(); return wrapper
}
const button = (wrapper,label) => wrapper.findAll('button').find(node => node.text() === label)
describe('教师实验管理', () => {
  beforeEach(() => {
    vi.clearAllMocks(); vi.spyOn(window,'confirm').mockReturnValue(true)
    api.get.mockImplementation(path => Promise.resolve(path.startsWith('/knowledge-points') ? [{ id: 1, title: 'D触发器' }] : path === '/experiments/1' ? row() : [row()]))
  })
  it('编辑使用当前version和可写字段，成功后采用回执版本', async () => {
    api.patch.mockResolvedValue(row({ version: 2, title: '新标题' }))
    const wrapper = await setup(); await wrapper.get('#experiment-title').setValue('新标题')
    await button(wrapper,'保存已发布实验').trigger('click'); await flushPromises()
    expect(api.patch).toHaveBeenCalledWith('/experiments/1', expect.objectContaining({ version: 1, title: '新标题', published: true }))
    expect(api.patch.mock.calls[0][1]).not.toHaveProperty('checkpoints')
    expect(wrapper.text()).toContain('当前版本 v2')
  })
  it('新建草稿使用POST且不夹带version或owner', async () => {
    api.post.mockResolvedValue(row({ id: 2, title: '新实验', published: false }))
    const wrapper = await setup(); await button(wrapper,'新建实验').trigger('click'); await flushPromises()
    await wrapper.get('#experiment-title').setValue('新实验'); await wrapper.get('#experiment-steps').setValue('观察输入。')
    await button(wrapper,'保存草稿').trigger('click'); await flushPromises()
    expect(api.post).toHaveBeenCalledWith('/experiments', expect.objectContaining({ title: '新实验', published: false, input_sequence: [] }))
    expect(api.post.mock.calls[0][1]).not.toHaveProperty('version')
    expect(wrapper.text()).toContain('草稿已保存')
  })
  it('他人公开实验只读，不显示任何写按钮', async () => {
    api.get.mockImplementation(path => Promise.resolve(path.startsWith('/knowledge-points') ? [] : path === '/experiments/1' ? row({ owner_id: 2 }) : [row({ owner_id: 2 })]))
    const wrapper = await setup()
    expect(wrapper.get('fieldset').attributes('disabled')).toBeDefined()
    expect(button(wrapper,'保存已发布实验')).toBeUndefined()
    expect(wrapper.text()).toContain('只有创建者可以修改')
  })
  it('409保留编辑内容且不自动推进version，明确载入后再保存', async () => {
    api.patch.mockRejectedValueOnce(Object.assign(new Error('实验已被修改'),{ status: 409 }))
    const wrapper = await setup(); await wrapper.get('#experiment-title').setValue('我的未保存标题')
    await button(wrapper,'保存已发布实验').trigger('click'); await flushPromises()
    expect(wrapper.get('#experiment-title').element.value).toBe('我的未保存标题')
    expect(button(wrapper,'保存已发布实验').attributes('disabled')).toBeDefined()
    expect(api.patch).toHaveBeenCalledTimes(1)
    api.get.mockResolvedValueOnce(row({ version: 2, title: '别处的新标题' }))
    await button(wrapper,'重新载入最新版本').trigger('click'); await flushPromises()
    expect(wrapper.get('#experiment-title').element.value).toBe('别处的新标题')
    api.patch.mockResolvedValueOnce(row({ version: 3 }))
    await button(wrapper,'保存已发布实验').trigger('click'); await flushPromises()
    expect(api.patch.mock.calls[1][1].version).toBe(2)
  })
  it('422显示字段原因并保留表单，必填失败不发请求', async () => {
    api.patch.mockRejectedValueOnce(Object.assign(new Error('请求字段不合法'), { status: 422, details: { fields: { steps_md: '说明内容不合法' } } }))
    const wrapper = await setup(); await wrapper.get('#experiment-title').setValue('保留的标题')
    await button(wrapper,'保存已发布实验').trigger('click'); await flushPromises()
    expect(wrapper.text()).toContain('说明内容不合法'); expect(wrapper.get('#experiment-title').element.value).toBe('保留的标题')
    await wrapper.get('#experiment-title').setValue(''); await button(wrapper,'保存已发布实验').trigger('click'); await flushPromises()
    expect(api.patch).toHaveBeenCalledTimes(1)
  })
  it('草稿撤回使用PATCH published=false和version', async () => {
    api.patch.mockResolvedValue(row({ version: 2, published: false }))
    const wrapper = await setup(); await button(wrapper,'撤回为草稿').trigger('click'); await flushPromises()
    expect(api.patch.mock.calls[0][1]).toMatchObject({ version: 1, published: false })
  })
  it('多标签令牌轮换后保留内容，明确再次保存时仍用原version', async () => {
    api.patch.mockRejectedValueOnce(Object.assign(new Error('CSRF校验失败'), { status: 403, code: 'CSRF_FAILED' }))
    const wrapper = await setup(); await wrapper.get('#experiment-title').setValue('保留的草稿')
    await button(wrapper,'保存已发布实验').trigger('click'); await flushPromises()
    expect(resetCsrfToken).toHaveBeenCalledOnce()
    expect(wrapper.get('#experiment-title').element.value).toBe('保留的草稿')
    expect(wrapper.text()).toContain('请再次保存')
    expect(api.patch).toHaveBeenCalledTimes(1)
    api.patch.mockResolvedValueOnce(row({ version: 2, title: '保留的草稿' }))
    await button(wrapper,'保存已发布实验').trigger('click'); await flushPromises()
    expect(api.patch.mock.calls[1][1]).toMatchObject({ version: 1, title: '保留的草稿' })
  })
  it('放弃修改被取消时保留原实验，不切换到新建', async () => {
    const wrapper = await setup(); await wrapper.get('#experiment-title').setValue('未保存')
    window.confirm.mockReturnValue(false); await button(wrapper,'新建实验').trigger('click'); await flushPromises()
    expect(wrapper.get('#experiment-title').element.value).toBe('未保存')
  })
})
