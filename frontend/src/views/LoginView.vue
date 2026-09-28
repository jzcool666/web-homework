<script setup>
import { ref } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'

import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()

const form = ref({ login_name: '', password: '' })
const error = ref(null)
const submitting = ref(false)

async function submit() {
  error.value = null
  submitting.value = true
  try {
    await auth.login({ ...form.value })
    router.push(route.query.redirect || { name: 'profile' })
  } catch (err) {
    error.value = err.message
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <main class="page">
    <h1>登录</h1>
    <p class="hint">学生、教师与管理员使用同一入口，角色由服务端判定。</p>

    <form class="card" @submit.prevent="submit">
      <div class="field">
        <label for="login_name">登录名</label>
        <input id="login_name" v-model="form.login_name" autocomplete="username" required />
      </div>
      <div class="field">
        <label for="password">密码</label>
        <input
          id="password"
          v-model="form.password"
          type="password"
          autocomplete="current-password"
          required
        />
      </div>
      <button class="primary" type="submit" :disabled="submitting">登录</button>
      <p v-if="error" class="error" role="alert">{{ error }}</p>
      <p class="hint">还没有账号？<RouterLink :to="{ name: 'register' }">学生注册</RouterLink></p>
    </form>
  </main>
</template>
