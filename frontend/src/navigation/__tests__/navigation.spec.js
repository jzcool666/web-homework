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
  { path: '/teacher/classroom', name: 'teacher-classroom', component: { template: '<div />' } },
  { path: '/teacher/demos/1', name: 'teacher-demo', component: { template: '<div />' } },
  { path: '/teacher/demos/1/present', name: 'teacher-demo-present', component: { template: '<div />' } },
  { path: '/student/demos', name: 'student-demos', component: { template: '<div />' } },
  { path: '/student/demos/1', name: 'student-demo', component: { template: '<div />' } },
  { path: '/student/learning', name: 'student-learning', component: { template: '<div />' } },
  { path: '/student/knowledge/1', name: 'student-knowledge', component: { template: '<div />' } },
  { path: '/student/classroom', name: 'student-classroom', component: { template: '<div />' } },
  { path: '/teacher/questions', name: 'teacher-questions', component: { template: '<div />' } },
  { path: '/teacher/assessments', name: 'teacher-assessments', component: { template: '<div />' } },
  { path: '/teacher/assessments/1', name: 'teacher-assessment', component: { template: '<div />' } },
  { path: '/student/practice', name: 'student-practice', component: { template: '<div />' } },
  { path: '/student/assessments/1', name: 'student-assessment', component: { template: '<div />' } },
  { path: '/student/results/1', name: 'student-result', component: { template: '<div />' } },
  { path: '/student/mistakes', name: 'student-mistakes', component: { template: '<div />' } },
  { path: '/student/experiments', name: 'student-experiments', component: { template: '<div />' } },
  { path: '/student/experiments/1', name: 'student-experiment', component: { template: '<div />' } },
  { path: '/student/attempts', name: 'student-attempts', component: { template: '<div />' } },
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

  it('题库与习题训练入口已接通并在子页面高亮', async () => {
    const teacher = await setup('teacher', '/teacher/questions')
    expect(teacher.wrapper.findAll('a.nav-item').map((item) => item.text())).toContain('题库')
    expect(teacher.wrapper.find('a.nav-item--active').text()).toContain('题库')
    teacher.wrapper.unmount()

    const student = await setup('student', '/student/mistakes')
    const labels = student.wrapper.findAll('a.nav-item').map((item) => item.text())
    expect(labels).toContain('习题训练')
    expect(student.wrapper.find('a.nav-item--active').text()).toContain('习题训练')
    expect(student.wrapper.find('.topbar__context').text()).toContain('习题训练')
    student.wrapper.unmount()
  })

  it('测评与讲评入口已接通并在详情页高亮', async () => {
    const teacher = await setup('teacher', '/teacher/assessments/1')
    const labels = teacher.wrapper.findAll('a.nav-item').map((item) => item.text())
    expect(labels).toContain('测评与讲评')
    expect(teacher.wrapper.find('a.nav-item--active').text()).toContain('测评与讲评')
    teacher.wrapper.unmount()
  })

  it('课堂演示入口已接通，并在演示页高亮', async () => {
    expect(navigationFor('student').find((item) => item.route === 'student-demos')).toBeTruthy()
    expect(navigationFor('student').find((item) => item.label === '我的课堂').planned).toBeUndefined()
    expect(navigationFor('teacher').find((item) => item.route === 'teacher-classroom')).toBeTruthy()
    expect(navigationFor('teacher').find((item) => item.label === '课堂').planned).toBeUndefined()

    const { wrapper } = await setup('student', '/student/demos/1')
    expect(wrapper.find('a.nav-item--active').text()).toContain('我的课堂')
    wrapper.unmount()

    const teacher = await setup('teacher', '/teacher/demos/1/present')
    expect(teacher.wrapper.find('a.nav-item--active').text()).toContain('课堂')
    teacher.wrapper.unmount()
  })

  it('实验中心入口已接通，并在预测页与记录页高亮', async () => {
    expect(navigationFor('student').find((item) => item.route === 'student-experiments')).toBeTruthy()
    expect(navigationFor('student').find((item) => item.label === '实验中心').planned).toBeUndefined()
    // 教师端实验管理页仍属计划入口
    expect(navigationFor('teacher').find((item) => item.label === '实验').planned).toBeTruthy()

    for (const path of ['/student/experiments', '/student/experiments/1', '/student/attempts']) {
      const { wrapper } = await setup('student', path)
      expect(wrapper.find('a.nav-item--active').text()).toContain('实验中心')
      wrapper.unmount()
    }
  })
})
