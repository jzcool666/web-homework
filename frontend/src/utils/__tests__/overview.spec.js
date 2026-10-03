import { describe, expect, it } from 'vitest'
import { completion, continuePoint, initialClassId, percent, recentAssessment, recommendedPoints } from '../overview'

describe('首页统计口径', () => {
  it('保留首页传入的班级，但拒绝未授权或停用班级 ID', () => {
    const rows = [{ id: 1, active: true }, { id: 2, active: true }, { id: 3, active: false }]
    expect(initialClassId(rows, '?class_id=2')).toBe(2)
    expect(initialClassId(rows, '?class_id=99')).toBe(1)
    expect(initialClassId(rows, '?class_id=3')).toBe(1)
    expect(initialClassId([], '?class_id=2')).toBe('')
  })
  it('剔除撤回内容的历史记录，完成与通过按内容去重', () => {
    const result = completion([{ id: 1 }, { id: 2 }], [{ knowledge_id: 1, completed: true }, { knowledge_id: 1, completed: true }, { knowledge_id: 3, completed: true }], [{ id: 7 }], [{ experiment_id: 7, passed: true }, { experiment_id: 7, passed: true }, { experiment_id: 8, passed: true }])
    expect(result).toMatchObject({ learned: 1, knowledgeTotal: 2, passed: 1, experimentTotal: 1, learningRatio: .5, experimentRatio: 1 })
  })
  it('无分母为 null，有内容无完成为真实 0', () => {
    expect(completion([], [], [], []).learningRatio).toBeNull()
    expect(completion([{ id: 1 }], [], [{ id: 2 }], []).learningRatio).toBe(0)
    expect(percent(null)).toBe('暂无足够数据')
    expect(percent(0)).toBe('0%')
  })
  it('推荐题目不计入推荐知识点数，重复知识点只算一次', () => {
    const items = [{ kind: 'question', knowledge_id: 1 }, { kind: 'knowledge', knowledge_id: 1 }, { kind: 'knowledge', knowledge_id: 1 }, { kind: 'knowledge', knowledge_id: 2, score: null }]
    expect(recommendedPoints(items)).toHaveLength(2)
  })
  it('继续学习不把推荐题目或已撤回知识点当作课程详情，按章节选择未完成点', () => {
    const points = [{ id: 1, chapter_id: 1, sort_order: 1 }, { id: 2, chapter_id: 2, sort_order: 1 }]
    expect(continuePoint(points, [], [{ kind: 'question', knowledge_id: 1 }, { kind: 'knowledge', knowledge_id: 9 }], [{ id: 1, sort_order: 2 }, { id: 2, sort_order: 1 }]).id).toBe(2)
    expect(continuePoint(points, points.map(row => ({ knowledge_id: row.id, completed: true })), [])).toBeNull()
  })
  it('最近测评排除自练和草稿，以时间而非响应顺序判断', () => {
    expect(recentAssessment([{ id: 9, kind: 'practice', starts_at: '2030', state: 'published' }, { id: 4, kind: 'quiz', starts_at: '2028', state: 'draft' }, { id: 1, kind: 'quiz', starts_at: '2026', state: 'closed' }, { id: 2, kind: 'exam', starts_at: '2027', state: 'published' }]).id).toBe(2)
  })
})
