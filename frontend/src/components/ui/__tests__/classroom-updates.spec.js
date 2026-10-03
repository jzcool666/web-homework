import { createPinia, setActivePinia } from 'pinia'
import { mount, flushPromises } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { useAuthStore } from '@/stores/auth'
import { api } from '@/api/client'
import ClassroomUpdates from '../ClassroomUpdates.vue'
vi.mock('@/api/client', () => ({ api: { get: vi.fn() } }))
function setup(role) { const pinia = createPinia(); setActivePinia(pinia); useAuthStore().user = { role }; return mount(ClassroomUpdates, { global: { plugins: [pinia], stubs: { RouterLink: { props: ['to'], template: '<a><slot /></a>' } } } }) }
beforeEach(() => vi.clearAllMocks())
describe('课堂动态真实活动', () => {
  it('学生未入班时显示空态，不读取测评列表', async () => {
    api.get.mockResolvedValue([]); const w = setup('student'); await w.get('button').trigger('click'); await flushPromises()
    expect(api.get).toHaveBeenCalledTimes(1); expect(w.text()).toContain('当前没有'); expect(w.findAll('li')).toHaveLength(0)
  })
  it('教师只用有效任教班级读取活动，并过滤自练与已结束的测评', async () => {
    api.get.mockImplementation(path => Promise.resolve(path.startsWith('/classes') ? [{ id: 7, active: true }] : [{ id: 1, title: '本班随堂测', kind: 'classroom', effective_state: 'open' }, { id: 2, title: '私人自练', kind: 'practice', effective_state: 'open' }, { id: 3, title: '已结束', kind: 'classroom', effective_state: 'closed' }]))
    const w = setup('teacher'); await w.get('button').trigger('click'); await flushPromises()
    expect(api.get.mock.calls[1][0]).toContain('class_id=7'); expect(w.text()).toContain('本班随堂测'); expect(w.text()).not.toContain('私人自练'); expect(w.text()).not.toContain('已结束')
    await w.get('section').trigger('keydown', { key: 'Escape' }); expect(w.find('section').exists()).toBe(false)
  })
  it('读取失败显示错误，不编造活动数或红点', async () => {
    api.get.mockRejectedValue(new Error('班级暂不可用')); const w = setup('student'); await w.get('button').trigger('click'); await flushPromises()
    expect(w.get('[role=alert]').text()).toBe('班级暂不可用'); expect(w.findAll('li')).toHaveLength(0)
  })
  it('教师的多个有效任教班级均能显示，不读取停用班级', async () => {
    api.get.mockImplementation(path => Promise.resolve(path.startsWith('/classes')
      ? [{ id: 7, name: '甲班', active: true }, { id: 8, name: '乙班', active: true }, { id: 9, active: false }]
      : [{ id: path.includes('class_id=7') ? 17 : 18, class_id: path.includes('class_id=7') ? 7 : 8, title: '随堂测', kind: 'quiz', effective_state: 'upcoming' }]))
    const w = setup('teacher'); await w.get('button').trigger('click'); await flushPromises()
    expect(w.findAll('li')).toHaveLength(2); expect(w.text()).toContain('甲班'); expect(w.text()).toContain('乙班')
    expect(api.get.mock.calls.some(([path]) => path.includes('class_id=9'))).toBe(false)
  })
})
