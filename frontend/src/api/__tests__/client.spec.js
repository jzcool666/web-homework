import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { API_BASE, ApiError, api, getCsrfToken, resetCsrfToken } from '@/api/client'

function jsonResponse(body, { ok = true, status = 200 } = {}) {
  return { ok, status, json: async () => body }
}

describe('api client', () => {
  beforeEach(() => {
    resetCsrfToken()
    global.fetch = vi.fn()
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('首次写请求先取匿名 CSRF 令牌，再带 X-CSRF-Token 发送', async () => {
    fetch.mockResolvedValueOnce(jsonResponse({ data: { csrf_token: 'tok-1' } }))
    fetch.mockResolvedValueOnce(jsonResponse({ data: { id: 1 } }, { status: 201 }))

    const result = await api.post('/auth/register', { login_name: 'stu_1' })

    expect(fetch).toHaveBeenCalledTimes(2)
    expect(fetch.mock.calls[0][0]).toBe(`${API_BASE}/auth/csrf`)
    const [url, options] = fetch.mock.calls[1]
    expect(url).toBe(`${API_BASE}/auth/register`)
    expect(options.headers['X-CSRF-Token']).toBe('tok-1')
    expect(options.credentials).toBe('same-origin')
    expect(result).toEqual({ id: 1 })
  })

  it('已有令牌时写请求不再重复取 CSRF', async () => {
    fetch.mockResolvedValueOnce(jsonResponse({ data: { csrf_token: 'tok-1' } }))
    fetch.mockResolvedValueOnce(jsonResponse({ data: {} }, { status: 200 }))
    fetch.mockResolvedValueOnce(jsonResponse({ data: {} }, { status: 200 }))

    await api.post('/auth/login', {})
    await api.post('/auth/logout', {})

    const csrfCalls = fetch.mock.calls.filter(([u]) => u === `${API_BASE}/auth/csrf`)
    expect(csrfCalls).toHaveLength(1)
  })

  it('GET 请求不附加 CSRF 头', async () => {
    fetch.mockResolvedValueOnce(jsonResponse({ data: [] }))

    await api.get('/me')

    expect(fetch).toHaveBeenCalledTimes(1)
    expect(fetch.mock.calls[0][1].headers['X-CSRF-Token']).toBeUndefined()
  })

  it('错误响应抛出带状态码与 code 的 ApiError', async () => {
    fetch.mockResolvedValueOnce(jsonResponse({ data: { csrf_token: 'tok-1' } }))
    fetch.mockResolvedValue(
      jsonResponse(
        { error: { code: 'CSRF_FAILED', message: 'CSRF 校验失败' } },
        { ok: false, status: 403 },
      ),
    )

    const failing = api.post('/auth/logout', {})
    await expect(failing).rejects.toBeInstanceOf(ApiError)
    await expect(failing).rejects.toMatchObject({ status: 403, code: 'CSRF_FAILED' })
  })

  it('令牌缺失时从响应读取，reset 后会重新申请', async () => {
    fetch.mockResolvedValue(jsonResponse({ data: { csrf_token: 'fresh' } }))
    await api.post('/auth/login', {})
    expect(getCsrfToken()).toBe('fresh')

    resetCsrfToken()
    expect(getCsrfToken()).toBeNull()
    await api.post('/auth/login', {})
    expect(getCsrfToken()).toBe('fresh')
  })
})
