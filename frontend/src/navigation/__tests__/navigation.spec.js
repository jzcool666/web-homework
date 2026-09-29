import { createPinia, setActivePinia } from 'pinia'
import { mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import AppShell from '@/layouts/AppShell.vue'
import { navigationFor } from '@/navigation'
import { useAuthStore } from '@/stores/auth'

const routes = [
  { path: '/', name: 'home', component: { template: '<div />' } },
  { path: '/login', name: 'login', component: { template: '<div />' } },
  { path: '/register', name: 'register', component: { template: '<div />' } },
  { path: '/profile', name: 'profile', component: { template: '<div />' } },
  { path: '/teacher/content', name: 'teacher-content', component: { template: '<div />' } },
  { path: '/teacher/attendance', name: 'teacher-attendance', component: { template: '<div />' } },
  { path: '/student/learning', name: 'student-learning', component: { template: '<div />' } },
  { path: '/student/knowledge/1', name: 'student-knowledge', component: { template: '<div />' } },
  { path: '/student/classroom', name: 'student-classroom', component: { template: '<div />' } },
  { path: '/admin/users', name: 'admin-users', component: { template: '<div />' } },
  { path: '/admin/classes', name: 'admin-classes', component: { template: '<div />' } },
  { path: '/admin/classes/1/enrollments', name: 'admin-enrollments', component: { template: '<div />' } },
]

async function setup(role, path = '/') {
  const pinia = createPinia()
  setActivePinia(pinia)
  const auth = useAuthStore()
  auth.user = { id: 1, display_name: '测试用户', role }
  const router = createRouter({ history: createMemoryHistory(), routes })
  await router.push(path)
  await router.isReady()
  const wrapper = mount(AppShell, { global: { plugins: [pinia, router] } })
  return { wrapper, auth, router }
}

describe('role navigation and shell', () => {
  beforeEach(() => vi.restoreAllMocks())

  it('计划入口不可点击，学生看不到管理员入口', async () => {
    const { wrapper } = await setup('student')
    expect(wrapper.find('a.nav-item--active').text()).toContain('学习首页')
    expect(wrapper.findAll('.nav-item--planned').length).toBeGreaterThan(0)
    expect(wrapper.findAll('a.nav-item').map((item) => item.text())).not.toContain('账号管理')
    expect(wrapper.find('.nav-item--planned').attributes('aria-disabled')).toBe('true')
    wrapper.unmount()
  })

  it('班级名单仍高亮班级管理，退出返回首页', async () => {
    const { wrapper, auth, router } = await setup('admin', '/admin/classes/1/enrollments')
    expect(wrapper.find('a.nav-item--active').text()).toContain('班级管理')
    auth.logout = vi.fn(async () => { auth.user = null })
    await wrapper.find('.topbar__logout').trigger('click')
    await vi.waitFor(() => expect(router.currentRoute.value.name).toBe('home'))
    expect(auth.logout).toHaveBeenCalledOnce()
    wrapper.unmount()
  })

  it('未知角色没有导航入口', () => {
    expect(navigationFor('unknown')).toEqual([])
  })

  it('已实现的课程与考勤入口可点击，并在详情页高亮课程', async () => {
    const { wrapper } = await setup('student', '/student/knowledge/1')
    const links = wrapper.findAll('a.nav-item').map((item) => item.text())
    expect(links).toContain('课程学习与收藏')
    expect(links).toContain('考勤与请假')
    expect(wrapper.find('a.nav-item--active').text()).toContain('课程学习与收藏')
    wrapper.unmount()

    expect(navigationFor('teacher').find((item) => item.route === 'teacher-content')).toBeTruthy()
    expect(navigationFor('teacher').find((item) => item.route === 'teacher-attendance')).toBeTruthy()
    expect(navigationFor('admin').find((item) => item.route === 'teacher-content')).toBeTruthy()
  })
})
