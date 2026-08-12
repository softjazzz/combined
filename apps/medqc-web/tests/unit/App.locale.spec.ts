import { mount } from '@vue/test-utils'
import { ConfigProvider } from 'ant-design-vue'
import dayjs from 'dayjs'
import { afterEach, describe, expect, it } from 'vitest'

import App from '@/App.vue'

describe('应用全局日期语言', () => {
  afterEach(() => {
    dayjs.locale('en')
  })

  it('为全项目日期组件提供中文语言并启用中文日期库', () => {
    dayjs.locale('en')

    const wrapper = mount(App, {
      global: {
        stubs: {
          RouterView: true,
        },
      },
    })

    const provider = wrapper.findComponent(ConfigProvider)
    const locale = provider.props('locale') as {
      locale?: string
      DatePicker?: { lang?: { placeholder?: string; rangePlaceholder?: string[] } }
    }

    expect(provider.exists()).toBe(true)
    expect(locale.locale).toBe('zh-cn')
    expect(locale.DatePicker?.lang?.placeholder).toBe('请选择日期')
    expect(locale.DatePicker?.lang?.rangePlaceholder).toEqual(['开始日期', '结束日期'])
    expect(dayjs.locale()).toBe('zh-cn')
  })
})
