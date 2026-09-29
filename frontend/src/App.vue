<script setup>
import { computed } from 'vue'
import { RouterLink, RouterView, useRouter } from 'vue-router'

import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const router = useRouter()
const isAdmin = computed(() => auth.hasRole('admin'))
const isTeacher = computed(() => auth.hasRole('teacher'))
const isStudent = computed(() => auth.hasRole('student'))

async function signOut() {
  await auth.logout()
  router.push({ name: 'home' })
}
</script>

<template>
  <header class="app-nav">
    <RouterLink class="brand" :to="{ name: 'home' }">学海通 · 时序逻辑</RouterLink>
    <nav>
      <template v-if="auth.isAuthenticated()">
        <RouterLink :to="{ name: 'profile' }">{{ auth.user.display_name }}</RouterLink>
        <RouterLink v-if="isTeacher" :to="{ name: 'teacher-attendance' }">考勤与请假</RouterLink>
        <RouterLink v-if="isStudent" :to="{ name: 'student-classroom' }">我的课堂</RouterLink>
        <template v-if="isAdmin">
          <RouterLink :to="{ name: 'admin-users' }">账号管理</RouterLink>
          <RouterLink :to="{ name: 'admin-classes' }">班级管理</RouterLink>
        </template>
        <button type="button" @click="signOut">退出</button>
      </template>
      <template v-else>
        <RouterLink :to="{ name: 'login' }">登录</RouterLink>
        <RouterLink :to="{ name: 'register' }">注册</RouterLink>
      </template>
    </nav>
  </header>
  <RouterView />
</template>

<style scoped>
.app-nav {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  padding: 0.75rem 1.5rem;
  border-bottom: 1px solid #dadce0;
  flex-wrap: wrap;
}

.brand {
  font-weight: 600;
  color: #1a3c6e;
  text-decoration: none;
}

nav {
  display: flex;
  align-items: center;
  gap: 1rem;
}

nav a {
  color: #1a73e8;
  text-decoration: none;
}

nav button {
  padding: 0.25rem 0.7rem;
  border: 1px solid #1a73e8;
  border-radius: 0.25rem;
  background: #fff;
  color: #1a73e8;
  cursor: pointer;
}
</style>
