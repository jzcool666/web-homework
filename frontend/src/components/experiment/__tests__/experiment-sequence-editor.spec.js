import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import ExperimentSequenceEditor from '@/components/experiment/ExperimentSequenceEditor.vue'

describe('可视化输入序列编辑', () => {
  it('高电平时一拍添加下降/上升两个合法事件', async () => {
    const wrapper = mount(ExperimentSequenceEditor, { props: { simulatorType: 'd', modelValue: [{ op: 'toggle_clock' }] } })
    await wrapper.findAll('button').find(button => button.text() === '＋ 一拍').trigger('click')
    expect(wrapper.emitted('update:modelValue')[0][0]).toEqual([{ op: 'toggle_clock' }, { op: 'toggle_clock' }, { op: 'toggle_clock' }])
  })
  it('模型字段按0/1写入，替换操作后移除旧输入字段', async () => {
    const wrapper = mount(ExperimentSequenceEditor, { props: { simulatorType: 'd', modelValue: [{ op: 'set', inputs: { d: 0, reset: 0 } }] } })
    await wrapper.get('select[aria-label="第1次操作 D"]').setValue('1')
    expect(wrapper.emitted('update:modelValue')[0][0][0].inputs.d).toBe(1)
    await wrapper.get('select[aria-label="第1次操作类型"]').setValue('toggle_clock')
    expect(wrapper.emitted('update:modelValue')[1][0][0]).toEqual({ op: 'toggle_clock' })
  })
  it('移除操作会发出新的数组，不修改父组件响应', async () => {
    const rows = [{ op: 'toggle_clock' }]
    const wrapper = mount(ExperimentSequenceEditor, { props: { simulatorType: 'd', modelValue: rows } })
    await wrapper.get('button[aria-label="移除第1次操作"]').trigger('click')
    expect(wrapper.emitted('update:modelValue')[0][0]).toEqual([])
    expect(rows).toHaveLength(1)
  })
  it('只读不显示编辑按钮，128边界一拍失败且保持原序列', async () => {
    const readonly = mount(ExperimentSequenceEditor, { props: { simulatorType: 'd', disabled: true } })
    expect(readonly.findAll('button')).toHaveLength(0)
    const wrapper = mount(ExperimentSequenceEditor, { props: { simulatorType: 'd', modelValue: Array.from({ length: 127 }, () => ({ op: 'toggle_clock' })) } })
    await wrapper.findAll('button').find(button => button.text() === '＋ 一拍').trigger('click')
    expect(wrapper.find('[role="alert"]').text()).toContain('128')
    expect(wrapper.emitted('update:modelValue')).toBeUndefined()
  })
})
