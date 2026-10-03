import { describe, expect, it } from 'vitest'
import { committedShiftTokens, describeCommittedEvent } from '@/utils/demoPresentation'

describe('课堂演示只解释已经执行的事件', () => {
  it('改输入和下降沿都解释为保持，不提供未来状态', () => {
    expect(describeCommittedEvent({ op: 'set', inputs: { d: 1 }, q: 0 }, 'd').text).toContain('Q 仍为 0')
    expect(describeCommittedEvent({ op: 'toggle_clock', rising: false, q: 1 }, 'd').title).toContain('下降沿')
  })
  it('同步复位优先于其他已执行动作', () => {
    const story = describeCommittedEvent({ rising: true, step_no: 3, inputs: { reset: 1, j: 1, k: 1 }, q_before: 1, q: 0 }, 'jk')
    expect(story.text).toContain('同步复位')
    expect(story.text).not.toContain('翻转')
    expect(story.text).toContain('1 → 0')
  })
  it.each([['00', '保持'], ['01', '清零'], ['10', '置位'], ['11', '翻转']])('解释 JK=%s 的已执行动作', (inputs, label) => {
    expect(describeCommittedEvent({ rising: true, step_no: 1, inputs: { j: Number(inputs[0]), k: Number(inputs[1]) }, q_before: 0, q: 0 }, 'jk').text).toContain(label)
  })
  it('移位动画采用已执行的旧位值和输入，不从当前 Q 推算未来', () => {
    expect(committedShiftTokens({ rising: true, inputs: { enable: 1, serial_in: 1 }, q_before: 10, q: 13 })).toEqual([1, 1, 0, 1, 0])
    expect(committedShiftTokens({ rising: false, inputs: { enable: 1 }, q_before: 10 })).toEqual([])
    expect(committedShiftTokens({ rising: true, inputs: { enable: 0 }, q_before: 10 })).toEqual([])
    expect(committedShiftTokens({ rising: true, inputs: { enable: 1, reset: 1 }, q_before: 10 })).toEqual([])
  })
})
