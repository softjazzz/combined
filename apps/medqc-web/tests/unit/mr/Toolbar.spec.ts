import { mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import Toolbar from '@/mr/components/Toolbar.vue'

vi.mock('ant-design-vue', () => ({
  message: {
    success: vi.fn(),
    info: vi.fn(),
    error: vi.fn(),
  },
}))

describe('MrToolbar 文内搜索安全高亮（防 XSS）', () => {
  let contentHost: HTMLDivElement

  beforeEach(() => {
    contentHost = document.createElement('div')
    contentHost.className = 'layout-content-main'
    document.body.appendChild(contentHost)
    Element.prototype.scrollIntoView = vi.fn()
  })

  afterEach(() => {
    contentHost.remove()
    vi.restoreAllMocks()
  })

  it('高亮含 HTML 恶意载荷的文本时只创建纯文本与 mark 节点，不执行/注入 DOM 标签', async () => {
    const paragraph = document.createElement('p')
    paragraph.textContent =
      '主诉：<img src=x onerror=window.__mrXss=1> 伴咳嗽及 <script>window.__mrXss=2</script> 发热'
    contentHost.appendChild(paragraph)

    const wrapper = mount(Toolbar, {
      global: {
        stubs: {
          'a-button-group': { template: '<div><slot /></div>' },
          'a-button': { template: '<button @click="$emit(\'click\')"><slot /></button>' },
          'a-divider': { template: '<span />' },
          'a-input-search': {
            props: ['value', 'size', 'allowClear', 'placeholder'],
            emits: ['update:value', 'search', 'press-enter'],
            template:
              '<input class="search-stub" :value="value" @input="$emit(\'update:value\', $event.target.value)" @keydown.enter="$emit(\'search\', $event.target.value)" />',
          },
        },
      },
    })

    const input = wrapper.get('input.search-stub')
    await input.setValue('onerror')
    await input.trigger('keydown.enter')

    const marks = contentHost.querySelectorAll('mark.search-highlight[data-search-result]')
    expect(marks).toHaveLength(1)
    expect(marks[0]?.textContent).toBe('onerror')
    expect(contentHost.querySelector('img')).toBeNull()
    expect(contentHost.querySelector('script')).toBeNull()
    expect((window as any).__mrXss).toBeUndefined()
    expect(paragraph.textContent).toContain('<img src=x onerror=window.__mrXss=1>')

    // 清空搜索应恢复原始纯文本且移除高亮节点
    await input.setValue('')
    await input.trigger('keydown.enter')
    expect(contentHost.querySelectorAll('mark.search-highlight')).toHaveLength(0)
    expect(contentHost.querySelector('img')).toBeNull()
    expect(paragraph.textContent).toContain('<img src=x onerror=window.__mrXss=1>')

    wrapper.unmount()
  })

  it('同一文本节点内多个匹配项全部安全高亮且不丢失其余字符', async () => {
    const paragraph = document.createElement('p')
    paragraph.textContent = '咳嗽三天，夜间咳嗽加重，<b>非HTML标签</b>咳嗽'
    contentHost.appendChild(paragraph)

    const wrapper = mount(Toolbar, {
      global: {
        stubs: {
          'a-button-group': { template: '<div><slot /></div>' },
          'a-button': { template: '<button @click="$emit(\'click\')"><slot /></button>' },
          'a-divider': { template: '<span />' },
          'a-input-search': {
            props: ['value', 'size', 'allowClear', 'placeholder'],
            emits: ['update:value', 'search', 'press-enter'],
            template:
              '<input class="search-stub" :value="value" @input="$emit(\'update:value\', $event.target.value)" @keydown.enter="$emit(\'search\', $event.target.value)" />',
          },
        },
      },
    })

    const input = wrapper.get('input.search-stub')
    await input.setValue('咳嗽')
    await input.trigger('keydown.enter')

    const marks = contentHost.querySelectorAll('mark.search-highlight')
    expect(marks).toHaveLength(3)
    expect(contentHost.querySelector('b')).toBeNull()
    expect(paragraph.textContent).toBe('咳嗽三天，夜间咳嗽加重，<b>非HTML标签</b>咳嗽')

    wrapper.unmount()
  })
})
