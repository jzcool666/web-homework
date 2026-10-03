import { createRouter, createWebHistory } from 'vue-router'

import HomeView from '@/views/HomeView.vue'
import { useAuthStore } from '@/stores/auth'

const routes = [
  {
    path: '/student/analytics',
    name: 'student-analytics',
    component: () => import('@/views/StudentAnalyticsView.vue'),
    meta: { requiresAuth: true, roles: ['student'] },
  },
  { path: '/student/labs', name: 'student-labs', component: () => import('@/views/LabTasksView.vue'), meta: { requiresAuth: true, roles: ['student'] } },
  { path: '/teacher/labs', name: 'teacher-labs', component: () => import('@/views/LabTasksView.vue'), meta: { requiresAuth: true, roles: ['teacher'] } },
  { path: '/labs/sessions/:id', name: 'lab-session', component: () => import('@/views/LabSessionView.vue'), meta: { requiresAuth: true, roles: ['student', 'teacher'] } },
  { path: '/student/labs/:id/upload', name: 'lab-upload', component: () => import('@/views/LabUploadView.vue'), meta: { requiresAuth: true, roles: ['student'] } },
  { path: '/student/lab-records', name: 'student-lab-records', component: () => import('@/views/LabRecordsView.vue'), meta: { requiresAuth: true, roles: ['student'] } },
  { path: '/teacher/lab-records', name: 'teacher-lab-records', component: () => import('@/views/LabRecordsView.vue'), meta: { requiresAuth: true, roles: ['teacher'] } },
  { path: '/lab-attempts/:id', name: 'lab-attempt', component: () => import('@/views/LabAttemptView.vue'), meta: { requiresAuth: true, roles: ['student', 'teacher'] } },
  { path: '/', name: 'home', component: HomeView },
  {
    path: '/login',
    name: 'login',
    component: () => import('@/views/LoginView.vue'),
    meta: { guestOnly: true, authLayout: true },
  },
  {
    path: '/register',
    name: 'register',
    component: () => import('@/views/RegisterView.vue'),
    meta: { guestOnly: true, authLayout: true },
  },
  {
    path: '/profile',
    name: 'profile',
    component: () => import('@/views/ProfileView.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/teacher/classroom',
    name: 'teacher-classroom',
    component: () => import('@/views/TeacherClassroomView.vue'),
    meta: { requiresAuth: true, roles: ['teacher'] },
  },
  {
    path: '/teacher/demos/:id',
    name: 'teacher-demo',
    component: () => import('@/views/TeacherDemoView.vue'),
    meta: { requiresAuth: true, roles: ['teacher'] },
  },
  {
    path: '/teacher/demos/:id/present',
    name: 'teacher-demo-present',
    component: () => import('@/views/TeacherDemoPresentView.vue'),
    meta: { requiresAuth: true, roles: ['teacher'] },
  },
  {
    path: '/student/demos',
    name: 'student-demos',
    component: () => import('@/views/StudentDemosView.vue'),
    meta: { requiresAuth: true, roles: ['student'] },
  },
  {
    path: '/student/demos/:id',
    name: 'student-demo',
    component: () => import('@/views/StudentDemoView.vue'),
    meta: { requiresAuth: true, roles: ['student'] },
  },
  {
    path: '/student/experiments',
    name: 'student-experiments',
    component: () => import('@/views/StudentExperimentsView.vue'),
    meta: { requiresAuth: true, roles: ['student'] },
  },
  {
    path: '/student/experiments/:id',
    name: 'student-experiment',
    component: () => import('@/views/StudentExperimentView.vue'),
    meta: { requiresAuth: true, roles: ['student'] },
  },
  {
    path: '/student/attempts',
    name: 'student-attempts',
    component: () => import('@/views/StudentAttemptsView.vue'),
    meta: { requiresAuth: true, roles: ['student'] },
  },
  {
    path: '/student/recognition',
    name: 'student-recognition',
    component: () => import('@/views/StudentRecognitionView.vue'),
    meta: { requiresAuth: true, roles: ['student'] },
  },
  {
    path: '/teacher/attendance',
    name: 'teacher-attendance',
    component: () => import('@/views/TeacherAttendanceView.vue'),
    meta: { requiresAuth: true, roles: ['teacher'] },
  },
  {
    path: '/teacher/experiment-stats',
    name: 'teacher-experiment-stats',
    component: () => import('@/views/TeacherExperimentStatsView.vue'),
    meta: { requiresAuth: true, roles: ['teacher'] },
  },
  {
    path: '/student/classroom',
    name: 'student-classroom',
    component: () => import('@/views/StudentClassroomView.vue'),
    meta: { requiresAuth: true, roles: ['student'] },
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
    path: '/teacher/analytics/learning',
    name: 'teacher-learning-analytics',
    component: () => import('@/views/TeacherLearningAnalyticsView.vue'),
    meta: { requiresAuth: true, roles: ['teacher'] },
  },
  {
    path: '/teacher/analytics/attendance',
    name: 'teacher-attendance-analytics',
    component: () => import('@/views/TeacherAttendanceAnalyticsView.vue'),
    meta: { requiresAuth: true, roles: ['teacher'] },
  },
  {
    path: '/teacher/warnings',
    name: 'teacher-warnings',
    component: () => import('@/views/TeacherWarningsView.vue'),
    meta: { requiresAuth: true, roles: ['teacher'] },
  },
  {
    path: '/teacher/lesson-plans',
    name: 'teacher-lesson-plans',
    component: () => import('@/views/TeacherLessonPlansView.vue'),
    meta: { requiresAuth: true, roles: ['teacher'] },
  },
  {
    path: '/teacher/questions',
    name: 'teacher-questions',
    component: () => import('@/views/TeacherQuestionsView.vue'),
    meta: { requiresAuth: true, roles: ['teacher'] },
  },
  {
    path: '/student/practice',
    name: 'student-practice',
    component: () => import('@/views/StudentPracticeView.vue'),
    meta: { requiresAuth: true, roles: ['student'] },
  },
  {
    path: '/student/assessments/:id',
    name: 'student-assessment',
    component: () => import('@/views/StudentAssessmentView.vue'),
    meta: { requiresAuth: true, roles: ['student'] },
  },
  {
    path: '/student/results/:submissionId',
    name: 'student-result',
    component: () => import('@/views/StudentResultView.vue'),
    meta: { requiresAuth: true, roles: ['student'] },
  },
  {
    path: '/student/mistakes',
    name: 'student-mistakes',
    component: () => import('@/views/StudentMistakesView.vue'),
    meta: { requiresAuth: true, roles: ['student'] },
  },
  {
    path: '/student/recommendations',
    name: 'student-recommendations',
    component: () => import('@/views/StudentRecommendationsView.vue'),
    meta: { requiresAuth: true, roles: ['student'] },
  },
  {
    path: '/teacher/assessments',
    name: 'teacher-assessments',
    component: () => import('@/views/TeacherAssessmentsView.vue'),
    meta: { requiresAuth: true, roles: ['teacher'] },
  },
  {
    path: '/teacher/paper-generations',
    name: 'teacher-paper-generation',
    component: () => import('@/views/TeacherPaperGenerationView.vue'),
    meta: { requiresAuth: true, roles: ['teacher'] },
  },
  {
    path: '/teacher/assessments/:id',
    name: 'teacher-assessment',
    component: () => import('@/views/TeacherAssessmentDetailView.vue'),
    meta: { requiresAuth: true, roles: ['teacher'] },
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
  {
    path: '/teacher/qa',
    name: 'teacher-qa',
    component: () => import('@/views/TeacherQaView.vue'),
    meta: { requiresAuth: true, roles: ['teacher'] },
  },
  {
    path: '/student/qa',
    name: 'student-qa',
    component: () => import('@/views/StudentQaView.vue'),
    meta: { requiresAuth: true, roles: ['student'] },
  },
  {
    path: '/knowledge-graph',
    name: 'knowledge-graph',
    component: () => import('@/views/KnowledgeGraphView.vue'),
    meta: { requiresAuth: true, roles: ['student', 'teacher'] },
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
