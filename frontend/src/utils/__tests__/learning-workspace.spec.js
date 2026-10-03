import { describe, expect, it } from 'vitest'
import { featuredKnowledge, inputTimeline } from '../learningWorkspace'
describe('公开输入的工作台展示', () => {
  it('时钟只由公开事件切换，设置输入不产生时钟沿或标准 Q', () => {
    const rows = inputTimeline([{ op: 'set', inputs: { j: 1, k: 0 } }, { op: 'toggle_clock' }, { op: 'set', inputs: { j: 0, k: 1 } }, { op: 'toggle_clock' }], 'jk')
    expect(rows.find(row => row.label === 'CLK').levels).toEqual([0, 1, 1, 0])
    expect(rows.find(row => row.label === 'J').levels).toEqual([1, 1, 0, 0])
    expect(rows.map(row => row.label)).not.toContain('Q')
  })
  it('reset_view 后只恢复输入与时钟，不沿用前一段输入', () => {
    const rows = inputTimeline([{ op: 'set', inputs: { enable: 0 } }, { op: 'toggle_clock' }, { op: 'reset_view' }], 'counter')
    expect(rows[0].levels).toEqual([0, 1, 0]); expect(rows[1].levels).toEqual([0, 0, 1])
  })
  it('展示四种模型时只能选择当前可见知识点，且不重复同一知识点', () => {
    const points = [{ id: 2 }, { id: 3 }, { id: 4 }, { id: 5 }]
    const exps = [{ simulator_type: 'd', knowledge_id: 99 }, { simulator_type: 'jk', knowledge_id: 3 }, { simulator_type: 'counter', knowledge_id: 3 }, { simulator_type: 'shift', knowledge_id: 5 }]
    const featured = featuredKnowledge(points, exps)
    expect(featured.map(row => row.id)).toEqual([3, 5, 2, 4]); expect(points).toEqual([{ id: 2 }, { id: 3 }, { id: 4 }, { id: 5 }])
  })
})
