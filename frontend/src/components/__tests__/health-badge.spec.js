import { beforeEach, describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

import HealthBadge from '@/components/HealthBadge.vue'
import { useHealthStore } from '@/stores/health'

describe('HealthBadge', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('ok 时显示服务正常与版本号', () => {
    const store = useHealthStore()
    store.status = 'ok'
    store.version = '0.1.0'

    const wrapper = mount(HealthBadge)

    expect(wrapper.text()).toContain('服务正常')
    expect(wrapper.text()).toContain('0.1.0')
    expect(wrapper.get('p').attributes('data-status')).toBe('ok')
  })

  it('不可用时不显示版本号，并给出原因', () => {
    const store = useHealthStore()
    store.status = 'unavailable'
    store.reason = '数据库不可用，服务暂时无法响应'

    const wrapper = mount(HealthBadge)

    expect(wrapper.text()).toContain('服务不可用')
    expect(wrapper.text()).toContain('数据库不可用')
    expect(wrapper.text()).not.toContain('版本')
    expect(wrapper.get('p').attributes('data-status')).toBe('unavailable')
  })
})
