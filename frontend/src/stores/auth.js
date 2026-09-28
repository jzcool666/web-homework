/**
 * 账号状态（SPEC-001）。角色与资料始终以服务器 /me 为准，
 * 前端守卫只做体验优化，后端仍独立鉴权。
 */

import { ref } from 'vue'
import { defineStore } from 'pinia'

import { api, resetCsrfToken, setCsrfToken } from '@/api/client'

export const useAuthStore = defineStore('auth', () => {
  const user = ref(null)
  const ready = ref(false)
  const loading = ref(false)

  function isAuthenticated() {
    return user.value !== null
  }

  function hasRole(...roles) {
    return user.value !== null && roles.includes(user.value.role)
  }

  /** 应用启动时探一次会话；401 视为未登录。 */
  async function bootstrap() {
    try {
      user.value = await api.get('/me')
    } catch {
      user.value = null
    } finally {
      ready.value = true
    }
    return user.value
  }

  async function login(payload) {
    loading.value = true
    try {
      const data = await api.post('/auth/login', payload)
      // 登录轮换 CSRF 令牌，必须用响应里的新值
      setCsrfToken(data.csrf_token)
      user.value = data.user
      return data.user
    } finally {
      loading.value = false
    }
  }

  async function register(payload) {
    loading.value = true
    try {
      await api.post('/auth/register', payload)
    } finally {
      loading.value = false
    }
    return login({ login_name: payload.login_name, password: payload.password })
  }

  async function logout() {
    try {
      await api.post('/auth/logout', {})
    } finally {
      resetCsrfToken()
      user.value = null
    }
  }

  /** 更新资料或改密码；改密码会作废所有会话，需重新登录。 */
  async function updateProfile(payload) {
    const updated = await api.patch('/me', payload)
    if (payload.new_password) {
      resetCsrfToken()
      user.value = null
    } else {
      user.value = updated
    }
    return updated
  }

  return { user, ready, loading, isAuthenticated, hasRole, bootstrap, login, register, logout, updateProfile }
})
