import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { api } from '@/api/client'
import StudentPreviewTodo from '@/components/StudentPreviewTodo.vue'

vi.mock('@/api/client', () => ({ api: { get: vi.fn() } }))

describe('StudentPreviewTodo', () => {
  beforeEach(() => vi.clearAllMocks())

  it('显示发布时冻结的标题与条目，不将数据库 ID 当作预习序号', async () => {
    api.get.mockImplementation((path) => {
      if (path.startsWith('/classes')) return Promise.resolve([{ id: 1, name: '甲班' }])
      if (path.startsWith('/preview-assignments')) return Promise.resolve([{
        id: 42,
        plan_title: '第 3 周备课',
        due_at: null,
        items: [{ sort_order: 1, target_type: 'knowledge', target_id: 7, content: { title: '同步复位' } }],
      }])
      return Promise.reject(new Error(`unexpected path: ${path}`))
    })

    const wrapper = mount(StudentPreviewTodo)
    await flushPromises()
    expect(wrapper.text()).toContain('第 3 周备课 · 1 项')
    expect(wrapper.text()).toContain('知识点「同步复位」')
    expect(wrapper.text()).not.toContain('第 42 次预习')
  })
})
