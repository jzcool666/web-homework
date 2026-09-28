import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import { HEALTH_PATH, useHealthStore } from '@/stores/health'

const OK_BODY = {
  data: { status: 'ok', version: '0.1.0' },
  meta: { server_time: '2026-09-28T06:00:00Z' },
}

const UNAVAILABLE_BODY = {
  error: {
    code: 'DB_BUSY',
    message: '数据库不可用，服务暂时无法响应',
    details: { reason: 'OperationalError: unable to open database file' },
  },
  meta: { server_time: '2026-09-28T06:00:00Z' },
}

function stubFetch({ ok, body }) {
  const fetchMock = vi.fn(() => Promise.resolve({ ok, json: () => Promise.resolve(body) }))
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

describe('E000 健康状态 store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.unstubAllGlobals()
  })

  it('请求 APIC 规定的路径', async () => {
    const fetchMock = stubFetch({ ok: true, body: OK_BODY })
    await useHealthStore().load()

    expect(HEALTH_PATH).toBe('/api/v1/health')
    expect(fetchMock).toHaveBeenCalledWith(HEALTH_PATH)
  })

  it('200 时记录 ok 与 version', async () => {
    stubFetch({ ok: true, body: OK_BODY })
    const store = useHealthStore()
    await store.load()

    expect(store.status).toBe('ok')
    expect(store.version).toBe('0.1.0')
    expect(store.reason).toBeNull()
    expect(store.loading).toBe(false)
  })

  it('503 时记录可读原因，不当作成功', async () => {
    stubFetch({ ok: false, body: UNAVAILABLE_BODY })
    const store = useHealthStore()
    await store.load()

    expect(store.status).toBe('unavailable')
    expect(store.version).toBeNull()
    expect(store.reason).toContain('unable to open database file')
  })

  it('网络异常时标记不可用', async () => {
    vi.stubGlobal('fetch', vi.fn(() => Promise.reject(new Error('offline'))))
    const store = useHealthStore()
    await store.load()

    expect(store.status).toBe('unavailable')
    expect(store.reason).toBeTruthy()
  })
})
