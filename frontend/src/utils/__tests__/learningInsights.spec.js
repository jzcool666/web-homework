import { describe, expect, it } from 'vitest'
import { attemptActivity, chapterCompletion } from '../learningInsights'
describe('个人学习图表口径', () => {
  it('章节比例只计可见知识点，重复完成及撤回内容不增加分子', () => {
    expect(
      chapterCompletion(
        [
          { id: 1, chapter_id: 2 },
          { id: 1, chapter_id: 2 },
          { id: 2, chapter_id: 2 },
        ],
        [
          { knowledge_id: 1, completed: true },
          { knowledge_id: 1, completed: true },
          { knowledge_id: 9, completed: true },
          { knowledge_id: 2, completed: false },
        ],
        [
          { id: 2, title: '触发器', sort_order: 1 },
          { id: 3, title: '未发布章', sort_order: 0 },
        ],
      ),
    ).toEqual([
      { id: 2, title: '触发器', order: 1, total: 2, completed: 1, ratio: 0.5 },
    ])
  })
  it('按章节顺序排列，没有当前知识点时不生成虚假完成比例', () => {
    expect(chapterCompletion([], [], [{ id: 1, title: '空章节' }])).toEqual([])
    expect(
      chapterCompletion(
        [
          { id: 1, chapter_id: 2 },
          { id: 2, chapter_id: 1 },
        ],
        [],
        [
          { id: 1, title: '第二章', sort_order: 2 },
          { id: 2, title: '第一章', sort_order: 1 },
        ],
      ).map((row) => row.title),
    ).toEqual(['第一章', '第二章'])
  })
  it('实验活动使用 UTC 自然日、有效时间与记录 ID 去重，不统计未来或窗外记录', () => {
    const rows = attemptActivity(
      [
        { id: 1, created_at: '2026-10-03T00:00:00Z', passed: true },
        { id: 1, created_at: '2026-10-03T00:00:00Z', passed: true },
        { id: 2, created_at: '2026-10-02T23:30:00-02:00', passed: false },
        { id: 3, created_at: '2026-10-04T00:00:00Z', passed: true },
        { id: 4, created_at: '2026-09-26T23:59:59Z', passed: true },
        { id: 5, created_at: null, passed: true },
        { id: 6, created_at: 'bad-date', passed: true },
      ],
      new Date('2026-10-03T05:00:00Z'),
    )
    expect(rows).toHaveLength(7)
    expect(rows[0]).toEqual({ day: '2026-09-27', submitted: 0, passed: 0 })
    expect(rows[6]).toEqual({ day: '2026-10-03', submitted: 2, passed: 1 })
    expect(rows.slice(0, 6).every((row) => row.submitted === 0)).toBe(true)
  })
})
