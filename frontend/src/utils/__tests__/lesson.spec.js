import { describe, expect, it } from 'vitest'

import {
  TARGET_LABEL,
  addItem,
  dueState,
  move,
  previewItemLabel,
  removeAt,
  renumber,
  summarizeItems,
  targetKey,
} from '@/utils/lesson'

const item = (type, id) => ({ target_type: type, target_id: id })

describe('SPEC-008 备课条目换算', () => {
  it('按当前顺序重排 sort_order，从 1 开始', () => {
    expect(renumber([item('knowledge', 5), item('question', 9)])).toEqual([
      { target_type: 'knowledge', target_id: 5, sort_order: 1 },
      { target_type: 'question', target_id: 9, sort_order: 2 },
    ])
    expect(renumber([])).toEqual([])
    expect(renumber(undefined)).toEqual([])
  })

  it('条目身份用类型 + ID 区分', () => {
    expect(targetKey(item('knowledge', 3))).toBe('knowledge:3')
    expect(targetKey(item('question', 3))).not.toBe(targetKey(item('knowledge', 3)))
  })

  it('追加目标会重排顺序，且不重复添加同一目标', () => {
    const once = addItem([], 'knowledge', 7)
    expect(once).toEqual([{ target_type: 'knowledge', target_id: 7, sort_order: 1 }])
    const twice = addItem(once, 'knowledge', 7)
    expect(twice).toHaveLength(1)
    const added = addItem(once, 'experiment', 2)
    expect(added.map((entry) => entry.sort_order)).toEqual([1, 2])
    expect(addItem(once, 'chapter', 1)).toHaveLength(1)
  })

  it('删除与移动后顺序连续', () => {
    let items = [item('knowledge', 1), item('question', 2), item('experiment', 3)]
    items = removeAt(items, 0)
    expect(items).toEqual([
      { target_type: 'question', target_id: 2, sort_order: 1 },
      { target_type: 'experiment', target_id: 3, sort_order: 2 },
    ])

    let moving = [item('knowledge', 1), item('question', 2), item('experiment', 3)]
    moving = move(moving, 2, -1)
    expect(moving.map((entry) => [entry.target_type, entry.sort_order])).toEqual([
      ['knowledge', 1],
      ['experiment', 2],
      ['question', 3],
    ])
    // 越界不动，但仍会重排
    expect(move(moving, 0, -1).map((entry) => entry.sort_order)).toEqual([1, 2, 3])
    expect(move(moving, 9, 1).map((entry) => entry.sort_order)).toEqual([1, 2, 3])
  })

  it('按类型汇总条目', () => {
    expect(summarizeItems([])).toEqual([])
    expect(
      summarizeItems([item('knowledge', 1), item('knowledge', 2), item('experiment', 3)]),
    ).toEqual(['知识点 2', '实验 1'])
    expect(TARGET_LABEL.question).toBe('题目')
  })
})

describe('SPEC-008 预习待办截止状态', () => {
  const now = new Date('2026-09-29T06:00:00Z')

  it('无期限与已过期分开表达', () => {
    expect(dueState(null, now)).toEqual({ tone: 'neutral', text: '无期限', overdue: false })
    expect(dueState('bad', now).text).toBe('无期限')
    const past = dueState('2026-09-28T06:00:00Z', now)
    expect(past.overdue).toBe(true)
    expect(past.tone).toBe('danger')
  })

  it('当天到期用警告色，之后到期用中性色', () => {
    expect(dueState('2026-09-29T23:00:00Z', now).tone).toBe('warning')
    const later = dueState('2026-10-02T06:00:00Z', now)
    expect(later.tone).toBe('neutral')
    expect(later.overdue).toBe(false)
  })
})

describe('SPEC-008 预习条目文案', () => {
  it('按类型取快照摘要，题目只显示题干', () => {
    expect(previewItemLabel({ target_type: 'knowledge', content: { title: '同步复位' } })).toBe('知识点「同步复位」')
    expect(
      previewItemLabel({
        target_type: 'resource_version',
        content: { resource_title: '第 3 周课件', version_no: 2 },
      }),
    ).toBe('资源版本「第 3 周课件」v2')
    expect(
      previewItemLabel({ target_type: 'experiment', content: { title: 'D 触发器演示' } }),
    ).toBe('实验「D 触发器演示」')
  })

  it('过长的题干被截断，缺失内容不报错', () => {
    const long = '模4计数器当前状态为 11，下一个有效时钟沿后的状态是什么？请说明理由并画出状态图。'
    const label = previewItemLabel({ target_type: 'question', content: { stem_md: long } })
    expect(label.startsWith('题目「')).toBe(true)
    expect(label.endsWith('…」')).toBe(true)
    expect(previewItemLabel({ target_type: 'question', content: {} })).toBe('题目「」')
    expect(previewItemLabel(null)).toBe('条目')
    expect(previewItemLabel({ target_type: 'unknown' })).toBe('unknown')
  })
})
