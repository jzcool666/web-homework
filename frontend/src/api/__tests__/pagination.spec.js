import { beforeEach, describe, expect, it, vi } from 'vitest'
import { api } from '../client'
import { readAll } from '../pagination'
vi.mock('../client', () => ({ api: { get: vi.fn() } }))
beforeEach(() => vi.clearAllMocks())
describe('完整分页读取', () => {
  it('超过 100 条读到下一页，保留知识点过滤条件', async () => {
    api.get.mockResolvedValueOnce(Array.from({ length: 100 }, (_, id) => ({ id }))).mockResolvedValueOnce([{ id: 100 }])
    expect(await readAll('/resources?knowledge_id=7')).toHaveLength(101)
    expect(api.get.mock.calls.map(call => call[0])).toEqual(['/resources?knowledge_id=7&page_size=100', '/resources?knowledge_id=7&page_size=100&page=2'])
  })
  it('后续页失败不能返回部分统计', async () => {
    api.get.mockResolvedValueOnce(Array(100).fill({ id: 1 })).mockRejectedValueOnce(new Error('断线'))
    await expect(readAll('/experiments')).rejects.toThrow('断线')
  })
  it('非列表响应拒绝计算分母', async () => { api.get.mockResolvedValue({ items: [] }); await expect(readAll('/experiments')).rejects.toThrow('列表响应格式不正确') })
})
