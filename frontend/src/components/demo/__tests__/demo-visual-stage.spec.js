import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import DemoVisualStage from '@/components/demo/DemoVisualStage.vue'

const base = { simulatorType: 'd', state: { q: 0, clock: 0, inputs: { d: 0, reset: 0 }, step_no: 0 } }
describe('动态教学画面', () => {
  it('即使错误地带来 nextQ，隐藏预测仍不渲染它', () => {
    const wrapper = mount(DemoVisualStage, { props: { ...base, nextQ: 1, revealNext: false } })
    expect(wrapper.find('[data-testid="next-state"]').exists()).toBe(false)
    expect(wrapper.text()).toContain('待揭示')
  })
  it('揭示时使用服务器提供的 nextQ', () => {
    const wrapper = mount(DemoVisualStage, { props: { ...base, nextQ: 1, revealNext: true } })
    expect(wrapper.get('[data-testid="next-state"]').text()).toBe('1')
  })
  it('学生和投屏的画面没有输入或时钟操作按钮', () => {
    const wrapper = mount(DemoVisualStage, { props: base })
    expect(wrapper.findAll('button')).toHaveLength(0)
    expect(wrapper.text()).toContain('跟随教师操作')
  })
  it('操作开关发出引脚名，禁用时不能继续操作', async () => {
    const wrapper = mount(DemoVisualStage, { props: { ...base, interactive: true } })
    await wrapper.get('button.input-toggle').trigger('click')
    expect(wrapper.emitted('input')).toEqual([['d']])
    await wrapper.setProps({ disabled: true })
    await wrapper.get('button.input-toggle').trigger('click')
    expect(wrapper.emitted('input')).toHaveLength(1)
  })
  it('仅已执行的移位有效沿出现移位动画，输入变化和保持不移动', async () => {
    const wrapper = mount(DemoVisualStage, { props: { ...base, simulatorType: 'shift', state: { q: 13, clock: 1, inputs: { enable: 1, serial_in: 1 } }, history: [{ rising: true, seq: 1, step_no: 1, q_before: 10, q: 13, inputs: { enable: 1, serial_in: 1 } }] } })
    expect(wrapper.findAll('.shift-token')).toHaveLength(5)
    await wrapper.setProps({ history: [{ rising: false, seq: 2, op: 'set', q: 13, inputs: { enable: 1 } }] })
    expect(wrapper.find('.shift-motion').exists()).toBe(false)
  })
  it('计数图使用配置模数且只标亮服务器当前 Q', () => {
    const wrapper = mount(DemoVisualStage, { props: { ...base, simulatorType: 'counter', config: { modulus: 6 }, state: { q: 5, inputs: {} } } })
    expect(wrapper.findAll('.count-node')).toHaveLength(6)
    expect(wrapper.findAll('.count-value--current')).toHaveLength(1)
    expect(wrapper.get('.count-value--current').text()).toBe('5')
  })
})
