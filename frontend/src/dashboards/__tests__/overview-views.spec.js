import { createPinia, setActivePinia } from 'pinia'
import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { api } from '@/api/client'
import { useAuthStore } from '@/stores/auth'
import TeacherDashboard from '../TeacherDashboardView.vue'
import StudentAnalytics from '@/views/StudentAnalyticsView.vue'
vi.mock('@/api/client', () => ({ api: { get: vi.fn() } }))
const link = { props: ['to'], template: '<a><slot /></a>' }
function setup(component, role) {
  const pinia = createPinia(); setActivePinia(pinia)
  useAuthStore().user = { id: 1, display_name: '测试', role }
  return mount(component, { global: { plugins: [pinia], stubs: { RouterLink: link } } })
}
beforeEach(() => vi.clearAllMocks())
describe('角色首页真实数据边界', () => {
  it('快速切班时迟到的旧班响应不能覆盖新班', async () => {
    let releaseOld
    const old = new Promise(resolve => { releaseOld = resolve })
    api.get.mockImplementation(path => {
      if (path.startsWith('/classes?')) return Promise.resolve([{ id: 1, name: '甲班', active: true }, { id: 2, name: '乙班', active: true }])
      if (path.includes('/classes/1/enrollments')) return old
      if (path.includes('/classes/2/enrollments')) return Promise.resolve([{ active: true }, { active: true }])
      if (path.includes('/demo-sessions?class_id=1')) return Promise.resolve([{ active: true, experiment: { title: '甲班旧演示' } }])
      if (path.includes('/demo-sessions?class_id=2')) return Promise.resolve([{ active: true, experiment: { title: '乙班当前演示' }, state: { step_no: 3 } }])
      return Promise.resolve([])
    })
    const wrapper = setup(TeacherDashboard, 'teacher')
    await flushPromises()
    await wrapper.get('select').setValue('2')
    await flushPromises()
    expect(wrapper.text()).toContain('乙班当前演示')
    releaseOld([{ active: true }]); await flushPromises()
    expect(wrapper.text()).toContain('乙班当前演示')
    expect(wrapper.text()).not.toContain('甲班旧演示')
    wrapper.unmount()
  })
  it('一个区块失败时保留其它真实数据，不将错误计为 0', async () => {
    api.get.mockImplementation(path => {
      if (path.startsWith('/knowledge-points')) return Promise.resolve([{ id: 1 }])
      if (path.startsWith('/me/learning-progress')) return Promise.reject(new Error('进度断线'))
      if (path.startsWith('/experiments')) return Promise.resolve([{ id: 7 }])
      if (path.startsWith('/me/experiment-attempts')) return Promise.resolve([{ experiment_id: 7, passed: true }])
      if (path.startsWith('/me/recommendations')) return Promise.resolve({ items: [{ kind: 'knowledge', knowledge_id: 1, resource_id: 1, title: '基础知识', score: null, reasons: [] }] })
      return Promise.resolve([])
    })
    const wrapper = setup(StudentAnalytics, 'student'); await flushPromises()
    const cards = wrapper.findAll('.metric-card')
    expect(cards[0].text()).toContain('暂无足够数据')
    expect(cards[1].text()).toContain('1 / 1')
    expect(wrapper.text()).toContain('进度断线')
    expect(wrapper.text()).toContain('基础路径')
    wrapper.unmount()
  })
  it('无班级时不请求班级接口，也不制造空统计', async () => {
    api.get.mockResolvedValue([])
    const wrapper = setup(TeacherDashboard, 'teacher'); await flushPromises()
    expect(api.get).toHaveBeenCalledTimes(1)
    expect(wrapper.text()).toContain('尚未选择任教班级')
    expect(wrapper.findAll('.metric-card')).toHaveLength(0)
    wrapper.unmount()
  })
})
