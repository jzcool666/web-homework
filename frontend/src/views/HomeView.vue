<script setup>
/** 首页只负责按角色分发；各角色的实际内容在 views/dashboards 下。 */
import { computed } from 'vue'

import AdminDashboardView from '@/dashboards/AdminDashboardView.vue'
import PublicHomeView from '@/dashboards/PublicHomeView.vue'
import StudentDashboardView from '@/dashboards/StudentDashboardView.vue'
import TeacherDashboardView from '@/dashboards/TeacherDashboardView.vue'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()

const dashboards = {
  student: StudentDashboardView,
  teacher: TeacherDashboardView,
  admin: AdminDashboardView,
}

// 未登录或未知角色都回落到公开首页，不展示任何用户数据。
const dashboard = computed(() => dashboards[auth.user?.role] ?? PublicHomeView)
</script>

<template>
  <component :is="dashboard" />
</template>
