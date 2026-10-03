import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import TimingPreview from '../TimingPreview.vue'

describe('固定输入时序概览', () => {
  it('紧凑概览完整绘制已下发输入，不添加 Q 答案或强制撑宽卡片', () => {
    const wrapper = mount(TimingPreview, { props: { kind: 'jk', compact: true, events: [
      { op: 'set', inputs: { j: 1, k: 0 } }, { op: 'toggle_clock' }, { op: 'toggle_clock' },
    ] } })
    expect(wrapper.text()).toContain('输出由你预测')
    expect(wrapper.findAll('g text').map(row => row.text())).toEqual(['CLK', 'J', 'K', 'RESET'])
    expect(wrapper.get('svg').element.style.minWidth).toBe('')
    expect(wrapper.get('svg').attributes('aria-label')).toContain('不包含标准状态')
    expect(wrapper.findAll('g path')[0].attributes('d')).toContain('V5')
  })
})
