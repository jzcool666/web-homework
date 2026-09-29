import { createRouter, createWebHistory } from 'vue-router'

import HomeView from '@/views/HomeView.vue'
import { useAuthStore } from '@/stores/auth'

const routes = [
  { path: '/', name: 'home', component: HomeView },
  {
    path: '/login',
    name: 'login',
    component: () => import('@/views/LoginView.vue'),
    meta: { guestOnly: true },
  },
  {
    path: '/register',
    name: 'register',
    component: () => import('@/views/RegisterView.vue'),
    meta: { guestOnly: true },
  },
  {
    path: '/profile',
    name: 'profile',
    component: () => import('@/views/ProfileView.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/teacher/content',
    name: 'teacher-content',
    component: () => import('@/views/TeacherContentView.vue'),
    meta: { requiresAuth: true, roles: ['teacher', 'admin'] },
  },
  {
    path: '/student/learning',
    name: 'student-learning',
    component: () => import('@/views/StudentLearningView.vue'),
    meta: { requiresAuth: true, roles: ['student'] },
  },
  {
    path: '/student/knowledge/:id',
    name: 'student-knowledge',
    component: () => import('@/views/StudentKnowledgeView.vue'),
    meta: { requiresAuth: true, roles: ['student'] },
  },
  {
    path: '/admin/users',
    name: 'admin-users',
    component: () => import('@/views/AdminUsersView.vue'),
    meta: { requiresAuth: true, roles: ['admin'] },
  },
  {
    path: '/admin/classes',
    name: 'admin-classes',
    component: () => import('@/views/AdminClassesView.vue'),
    meta: { requiresAuth: true, roles: ['admin'] },
  },
  {
    path: '/admin/classes/:id/enrollments',
    name: 'admin-enrollments',
    component: () => import('@/views/AdminEnrollmentsView.vue'),
    meta: { requiresAuth: true, roles: ['admin'] },
    props: true,
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

// 守卫只改善体验：先探一次会话，再按 meta 决定去向；后端仍独立鉴权。
router.beforeEach(async (to) => {
  const auth = useAuthStore()
  if (!auth.ready) await auth.bootstrap()

  if (to.meta.requiresAuth && !auth.isAuthenticated()) {
    return { name: 'login', query: { redirect: to.fullPath } }
  }
  if (to.meta.roles && !auth.hasRole(...to.meta.roles)) {
    return { name: 'home' }
  }
  if (to.meta.guestOnly && auth.isAuthenticated()) {
    return { name: 'home' }
  }
  return true
})

export default router
