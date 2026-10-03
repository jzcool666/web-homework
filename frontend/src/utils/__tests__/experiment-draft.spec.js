import { describe, expect, it } from 'vitest'
import { appendClockStep, experimentDraft, experimentPayload, newExperimentDraft, sequenceTimeline } from '@/utils/experimentDraft'

const draft = () => ({ ...newExperimentDraft(1), title: '  D采样  ', steps_md: '设置D后观察上升沿。', input_sequence: [{ op: 'set', inputs: { d: 1 } }, { op: 'toggle_clock' }] })
describe('实验定义的可写字段与时钟上下文', () => {
  it('只提交可写字段，不提交checkpoint、owner、Q或期望输出', () => {
    const form = { ...draft(), owner_id: 99, checkpoints: [{ expected: 1 }] }
    expect(experimentPayload(form, true)).toEqual({ title: 'D采样', knowledge_id: 1, simulator_type: 'd', config: { initial_q: 0 }, steps_md: '设置D后观察上升沿。', input_sequence: [{ op: 'set', inputs: { d: 1 } }, { op: 'toggle_clock' }], published: true })
  })
  it('非计数器不发送模数，计数器保留合法无效初态教学配置', () => {
    const form = { ...draft(), simulator_type: 'counter', initial_q: 15, modulus: 6, input_sequence: [] }
    expect(experimentPayload(form, false).config).toEqual({ initial_q: 15, modulus: 6 })
  })
  it.each([['initial_q', 2, '初态'], ['title', '', '标题'], ['knowledge_id', '', '知识点'], ['steps_md', '', '说明']])('拒绝不符合后端范围的%s', (field,value,word) => {
    expect(() => experimentPayload({ ...draft(), [field]: value }, false)).toThrow(word)
  })
  it('拒绝模型之外的输入、bool值和夹带Q字段', () => {
    for (const event of [{ op: 'set', inputs: { enable: 1 } }, { op: 'set', inputs: { d: true } }, { op: 'toggle_clock', q: 1 }, { op: 'toString' }]) {
      expect(() => experimentPayload({ ...draft(), input_sequence: [event] }, false)).toThrow()
    }
  })
  it('序列上下文计算有效沿，恢复初态清空先前检查点', () => {
    const rows = sequenceTimeline('d', [{ op: 'set', inputs: { d: 1 } }, { op: 'toggle_clock' }, { op: 'toggle_clock' }, { op: 'toggle_clock' }, { op: 'reset_view' }, { op: 'toggle_clock' }])
    expect(rows.map(row => row.step_no)).toEqual([0, 1, 1, 2, 0, 1])
    expect(rows.at(-1).inputs.d).toBe(0)
    expect(rows.at(-1)).not.toHaveProperty('q')
  })
  it('添加一拍按末尾CLK补齐，128事件边界不产生部分序列', () => {
    expect(appendClockStep('d', [])).toEqual([{ op: 'toggle_clock' }])
    expect(appendClockStep('d', [{ op: 'toggle_clock' }])).toHaveLength(3)
    const almostFull = Array.from({ length: 127 }, () => ({ op: 'toggle_clock' }))
    expect(() => appendClockStep('d', almostFull)).toThrow('128')
    expect(almostFull).toHaveLength(127)
  })
  it('编辑草稿不原地修改响应的输入序列', () => {
    const row = { ...experimentPayload(draft(), true), config: { initial_q: 0 } }
    const form = experimentDraft(row); form.input_sequence[0].inputs.d = 0
    expect(row.input_sequence[0].inputs.d).toBe(1)
  })
})
