import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { getCsrfToken, resetCsrfToken } from '@/api/client'
import { useAuthStore } from '@/stores/auth'

function jsonResponse(body, { ok = true, status = 200 } = {}) {
  return { ok, status, json: async () => body }
}

const STUDENT = { id: 7, login_name: 'stu_7', display_name: '学生七', role: 'student', active: true, version: 1 }

describe('auth store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    resetCsrfToken()
    global.fetch = vi.fn()
  })

  it('登录后保存用户，并采用响应里轮换后的 CSRF 令牌', async () => {
    fetch.mockResolvedValueOnce(jsonResponse({ data: { csrf_token: 'anon' } }))
    fetch.mockResolvedValueOnce(jsonResponse({ data: { user: STUDENT, csrf_token: 'after-login' } }))

    const auth = useAuthStore()
    await auth.login({ login_name: 'stu_7', password: 'Passw0rd!23' })

    expect(auth.isAuthenticated()).toBe(true)
    expect(auth.user).toEqual(STUDENT)
    expect(getCsrfToken()).toBe('after-login')
  })

  it('bootstrap 未登录时把用户置空且不抛错', async () => {
    fetch.mockResolvedValueOnce(
      jsonResponse({ error: { code: 'UNAUTHENTICATED', message: '请先登录' } }, { ok: false, status: 401 }),
    )

    const auth = useAuthStore()
    await auth.bootstrap()

    expect(auth.user).toBeNull()
    expect(auth.ready).toBe(true)
  })

  it('退出清空用户与令牌', async () => {
    fetch.mockResolvedValueOnce(jsonResponse({ data: { csrf_token: 'anon' } }))
    fetch.mockResolvedValueOnce(jsonResponse({ data: { user: STUDENT, csrf_token: 'after-login' } }))
    fetch.mockResolvedValueOnce(jsonResponse({ data: { logged_out: true } }))

    const auth = useAuthStore()
    await auth.login({ login_name: 'stu_7', password: 'Passw0rd!23' })
    await auth.logout()

    expect(auth.isAuthenticated()).toBe(false)
    expect(getCsrfToken()).toBeNull()
  })

  it('注册成功后自动登录', async () => {
    fetch.mockResolvedValueOnce(jsonResponse({ data: { csrf_token: 'anon' } })) // 注册前的 CSRF
    fetch.mockResolvedValueOnce(jsonResponse({ data: STUDENT }, { status: 201 })) // register
    fetch.mockResolvedValueOnce(jsonResponse({ data: { user: STUDENT, csrf_token: 'after-login' } })) // login

    const auth = useAuthStore()
    await auth.register({
      login_name: 'stu_7',
      student_no: '20240007',
      display_name: '学生七',
      password: 'Passw0rd!23',
    })

    expect(auth.user).toEqual(STUDENT)
  })

  it('改密码成功后本地会话清空，需要重新登录', async () => {
    fetch.mockResolvedValueOnce(jsonResponse({ data: { csrf_token: 'anon' } }))
    fetch.mockResolvedValueOnce(jsonResponse({ data: { user: STUDENT, csrf_token: 'after-login' } }))
    fetch.mockResolvedValueOnce(jsonResponse({ data: STUDENT }))

    const auth = useAuthStore()
    await auth.login({ login_name: 'stu_7', password: 'Passw0rd!23' })
    await auth.updateProfile({
      version: 1,
      current_password: 'Passw0rd!23',
      new_password: 'NewPassw0rd!24',
    })

    expect(auth.isAuthenticated()).toBe(false)
    expect(getCsrfToken()).toBeNull()
  })

  it('hasRole 按角色判定', async () => {
    fetch.mockResolvedValueOnce(jsonResponse({ data: { csrf_token: 'anon' } }))
    fetch.mockResolvedValueOnce(jsonResponse({ data: { user: STUDENT, csrf_token: 'x' } }))

    const auth = useAuthStore()
    await auth.login({ login_name: 'stu_7', password: 'Passw0rd!23' })

    expect(auth.hasRole('student')).toBe(true)
    expect(auth.hasRole('admin')).toBe(false)
  })
})
