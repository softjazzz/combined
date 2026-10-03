import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'
import WorkstationAssistPanel from '@/views/workstation-v4/components/WorkstationAssistPanel.vue'

const stubs = {
  'a-button': { template: '<button><slot /></button>' },
}

function mountPanel(props: Record<string, unknown> = {}) {
  return mount(WorkstationAssistPanel, {
    props,
    attachTo: document.body,
    global: { stubs },
    slots: { chat: '<div data-testid="chat-slot">chat</div>' },
  })
}

describe('智能助手面板外壳', () => {
  afterEach(() => {
    vi.useRealTimers()
    document.body.innerHTML = ''
  })

  it('入口为“智能助手”，角标超过 9 显示 9+，未读数增加时扩散提示', async () => {
    const wrapper = mountPanel({ messageCount: 30 })
    const trigger = wrapper.get('.assist-trigger')
    expect(trigger.attributes('aria-label')).toBe('智能助手')
    expect(trigger.get('.assist-trigger__badge').text()).toBe('9+')
    await wrapper.setProps({ messageCount: 31 })
    expect(wrapper.get('.assist-trigger').classes()).toContain('assist-trigger--pulse')
    wrapper.unmount()
  })

  it('3 秒无操作收起为图标，悬停时展开', async () => {
    vi.useFakeTimers()
    const wrapper = mountPanel({ messageCount: 1 })
    expect(wrapper.get('.assist-trigger').classes()).not.toContain('assist-trigger--collapsed')
    vi.advanceTimersByTime(3100)
    await wrapper.vm.$nextTick()
    expect(wrapper.get('.assist-trigger').classes()).toContain('assist-trigger--collapsed')
    await wrapper.get('.assist-trigger').trigger('mouseenter')
    expect(wrapper.get('.assist-trigger').classes()).not.toContain('assist-trigger--collapsed')
    wrapper.unmount()
  })

  it('Ctrl+/ 开关面板，焦点在面板内按 Esc 收起', async () => {
    const wrapper = mountPanel()
    expect(wrapper.find('.assist-panel').exists()).toBe(false)
    window.dispatchEvent(new KeyboardEvent('keydown', { key: '/', ctrlKey: true }))
    await flushPromises()
    expect(wrapper.find('.assist-panel').exists()).toBe(true)
    wrapper
      .get('.assist-panel')
      .element.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }))
    await flushPromises()
    expect(wrapper.find('.assist-panel').exists()).toBe(false)
    wrapper.unmount()
  })

  it('页面外的 Esc 不会收起面板', async () => {
    const wrapper = mountPanel({ visible: true })
    document.body.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }))
    await flushPromises()
    expect(wrapper.find('.assist-panel').exists()).toBe(true)
    wrapper.unmount()
  })

  it('只保留对话页签时不渲染侧栏，页签名可自定义', () => {
    const wrapper = mountPanel({
      visible: true,
      availableTabs: ['chat'],
      chatLabel: '问数',
      defaultTab: 'chat',
    })
    expect(wrapper.find('.assist-sidebar').exists()).toBe(false)
    expect(wrapper.find('[data-testid="chat-slot"]').exists()).toBe(true)
    wrapper.unmount()
  })

  it('完整页签时对话排第一，名称沿用“对话”', () => {
    const wrapper = mountPanel({ visible: true, defaultTab: 'chat' })
    const labels = wrapper.findAll('.assist-sidebar__label').map((node) => node.text())
    expect(labels[0]).toBe('对话')
    expect(labels).toHaveLength(8)
    wrapper.unmount()
  })

  it('初始页签不在可用页签内时回到第一个可用页签，对话内容保持可见', () => {
    const wrapper = mountPanel({ visible: true, availableTabs: ['chat'] })
    const slot = wrapper.get('[data-testid="chat-slot"]')
    expect((slot.element.closest('.assist-panel__slot') as HTMLElement).style.display).not.toBe(
      'none',
    )
    expect(wrapper.get('.assist-panel').classes()).toContain('assist-panel--wide')
    wrapper.unmount()
  })
})
