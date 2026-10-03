import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import PredictionConsole from '../PredictionConsole.vue'
const experiment = { id: 1, version: 1, simulator_type: 'jk', checkpoints: [{ index: 0, inputs: { j: 1, k: 0, reset: 0 } }, { index: 1, inputs: { j: 0, k: 1, reset: 0 } }] }
describe('逐拍查看与预测选择', () => {
  it('步进只更改检查点显示，不生成任何答案；选择 Q 才发出该拍的用户预测', async () => {
    const wrapper = mount(PredictionConsole, { props: { experiment, answers: ['', ''] } })
    await wrapper.findAll('button').find(row => row.text().includes('下一拍')).trigger('click')
    expect(wrapper.text()).toContain('第 2 / 2 拍'); expect(wrapper.emitted('answer')).toBeUndefined()
    await wrapper.get('select').setValue('1'); expect(wrapper.emitted('answer')).toEqual([[1, '1']])
  })
  it('提交后锁定预测，切换工作区版本回到第一拍', async () => {
    const wrapper = mount(PredictionConsole, { props: { experiment, answers: ['0', '1'], locked: true } })
    expect(wrapper.get('select').attributes('disabled')).toBeDefined()
    await wrapper.findAll('button').find(row => row.text().includes('下一拍')).trigger('click')
    await wrapper.setProps({ experiment: { ...experiment, version: 2 } }); expect(wrapper.text()).toContain('第 1 / 2 拍')
  })
})
