import { api } from './client'

/** Read every page before using a list as a statistical denominator. */
export async function readAll(path) {
  const url = new URL(path, 'http://local')
  url.searchParams.set('page_size', '100')
  url.searchParams.delete('page')
  const rows = []
  for (let page = 1; ; page += 1) {
    if (page > 1) url.searchParams.set('page', String(page))
    const batch = await api.get(`${url.pathname}${url.search}`)
    if (!Array.isArray(batch)) throw new Error('列表响应格式不正确')
    rows.push(...batch)
    if (batch.length < 100) return rows
  }
}
