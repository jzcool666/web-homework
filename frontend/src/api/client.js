/**
 * API 客户端（SPEC-001）。
 *
 * 统一处理 APIC 第 1 节的 {data,meta} / {error} 封装、CSRF 头注入与
 * 错误归一化。写方法自动取匿名 CSRF 令牌；登录轮换令牌后由调用方更新。
 */

export const API_BASE = '/api/v1'

let csrfToken = null

export function setCsrfToken(token) {
  csrfToken = token
}

export function getCsrfToken() {
  return csrfToken
}

export function resetCsrfToken() {
  csrfToken = null
}

export class ApiError extends Error {
  constructor(status, code, message, details) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
    this.details = details ?? null
  }
}

async function toError(response) {
  let body = null
  try {
    body = await response.json()
  } catch {
    body = null
  }
  const error = body?.error ?? {}
  return new ApiError(
    response.status,
    error.code ?? 'INVALID_REQUEST',
    error.message ?? '请求失败，请稍后重试',
    error.details,
  )
}

/** 确保存在可用的 CSRF 令牌（首次调用创建匿名会话）。 */
export async function ensureCsrf() {
  if (csrfToken) return csrfToken
  const response = await fetch(`${API_BASE}/auth/csrf`, { credentials: 'same-origin' })
  if (!response.ok) throw await toError(response)
  const body = await response.json()
  csrfToken = body.data.csrf_token
  return csrfToken
}

async function send(method, path, payload) {
  const headers = {}
  const options = { method, credentials: 'same-origin', headers }
  if (payload !== undefined) {
    headers['Content-Type'] = 'application/json'
    options.body = JSON.stringify(payload)
  }
  if (method !== 'GET') {
    headers['X-CSRF-Token'] = await ensureCsrf()
  }
  const response = await fetch(`${API_BASE}${path}`, options)
  if (!response.ok) throw await toError(response)
  const body = await response.json()
  return body.data
}

/**
 * multipart 上传（SPEC-005 E020）。文件上传不能用 JSON 序列化，
 * 这里单独走一条路径，CSRF 处理与 send 保持一致。
 */
async function sendForm(path, formData) {
  const response = await fetch(`${API_BASE}${path}`, {
    method: 'POST',
    credentials: 'same-origin',
    headers: { 'X-CSRF-Token': await ensureCsrf() },
    body: formData,
  })
  if (!response.ok) throw await toError(response)
  const body = await response.json()
  return body.data
}

export const api = {
  get: (path) => send('GET', path),
  post: (path, payload = {}) => send('POST', path, payload),
  put: (path, payload = {}) => send('PUT', path, payload),
  patch: (path, payload = {}) => send('PATCH', path, payload),
  delete: (path) => send('DELETE', path, {}),
  postForm: (path, formData) => sendForm(path, formData),
}

export { toError as _toError }
