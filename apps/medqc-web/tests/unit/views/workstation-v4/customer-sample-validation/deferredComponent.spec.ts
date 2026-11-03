import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent, h } from 'vue'
import { describe, expect, it, vi } from 'vitest'
import { deferredComponent } from '@/views/workstation-v4/customer-sample-validation/deferredComponent'

describe('延迟加载反馈', () => {
  it('加载期间有反馈，解析完成后保留原组件和props', async () => {
    const target = defineComponent({ props: { open: Boolean }, setup: (p) => () => h('div', { 'data-open': p.open }, 'loaded') })
    let complete!: (component: typeof target) => void
    const deferred = deferredComponent(() => new Promise<typeof target>((resolve) => { complete = resolve }))
    const host = defineComponent({ props: { open: Boolean }, setup: (p) => () => h(deferred, { open: p.open }) })
    const wrapper = mount(host, { props: { open: true } })
    expect(wrapper.get('[role="status"]').text()).toContain('正在加载')
    complete(target)
    await flushPromises()
    expect(wrapper.text()).toBe('loaded')
    expect(wrapper.get('[data-open]').attributes('data-open')).toBe('true')
    wrapper.unmount()
  })

  it('加载失败明确提示，关闭后不遗留错误占位', async () => {
    const loader = vi.fn().mockRejectedValue(new Error('synthetic asset failure'))
    const deferred = deferredComponent(loader)
    const host = defineComponent({ props: { open: Boolean }, setup: (p) => () => h(deferred, { open: p.open }) })
    const wrapper = mount(host, {
      props: { open: true },
      global: { config: { errorHandler: vi.fn() } },
    })
    await flushPromises()
    expect(wrapper.get('[role="alert"]').text()).toContain('刷新后重试')
    expect(loader).toHaveBeenCalledTimes(1)
    await wrapper.setProps({ open: false })
    expect(wrapper.find('[role="alert"]').exists()).toBe(false)
    wrapper.unmount()
  })
})
