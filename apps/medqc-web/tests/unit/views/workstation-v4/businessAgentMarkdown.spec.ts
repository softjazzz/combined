import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import BusinessAgentAnswer from '@/views/workstation-v4/components/BusinessAgentAnswer.vue'
import { parseAnswer, parseInline } from '@/views/workstation-v4/components/businessAgentMarkdown'

describe('助手回答 Markdown 渲染', () => {
  it('识别段落、标题、有序与无序列表、加粗和行内代码', () => {
    const blocks = parseAnswer(
      '## 概况\n共 **7 条**不合规，规则 `LX0609-01-01-01`。\n\n- 第一条\n- 第二条\n1. 先处理\n2. 再复检',
    )
    expect(blocks.map((block) => block.type)).toEqual(['heading', 'paragraph', 'list', 'list'])
    expect(blocks[1]).toEqual({
      type: 'paragraph',
      inline: [
        { text: '共 ' },
        { text: '7 条', bold: true },
        { text: '不合规，规则 ' },
        { text: 'LX0609-01-01-01', code: true },
        { text: '。' },
      ],
    })
    expect(blocks[2]).toMatchObject({ type: 'list', ordered: false })
    expect(blocks[3]).toMatchObject({ type: 'list', ordered: true })
  })

  it('未闭合标记按原文保留，表格分隔线不显示竖线', () => {
    expect(parseInline('单个 ** 星号')).toEqual([{ text: '单个 ** 星号' }])
    const blocks = parseAnswer('| 规则 | 次数 |\n| --- | --- |\n| 甲 | 5 |')
    const text = JSON.stringify(blocks)
    expect(text).not.toContain('|')
    expect(text).not.toContain('---')
  })

  it('模型输出中的标签只作为文本显示，不生成 HTML 元素', () => {
    const wrapper = mount(BusinessAgentAnswer, {
      props: { text: '**注意** <img src=x onerror=alert(1)> <script>alert(1)</script>' },
    })
    expect(wrapper.find('img').exists()).toBe(false)
    expect(wrapper.find('script').exists()).toBe(false)
    expect(wrapper.find('strong').text()).toBe('注意')
    expect(wrapper.text()).toContain('<img src=x onerror=alert(1)>')
  })
  it('相邻文本片段之间不额外插入空格', () => {
    const wrapper = mount(BusinessAgentAnswer, { props: { text: '共**7条**不合规' } })
    expect(wrapper.find('p').text()).toBe('共7条不合规')
  })

  it('超过 200 字的回答默认只显示开头结论，可展开与收起；短回答不显示折叠按钮', async () => {
    const long = [
      `结论段${'甲'.repeat(60)}`,
      `第二段说明${'乙'.repeat(40)}`,
      `第三段证据${'丙'.repeat(80)}`,
      `第四段局限${'丁'.repeat(60)}`,
    ].join('\n\n')
    const wrapper = mount(BusinessAgentAnswer, { props: { text: long } })
    expect(wrapper.text()).toContain('第二段说明')
    expect(wrapper.text()).not.toContain('第三段证据')
    const toggle = wrapper.get('[data-testid="business-agent-answer-toggle"]')
    expect(toggle.text()).toBe('展开全文')
    await toggle.trigger('click')
    expect(wrapper.text()).toContain('第四段局限')
    expect(toggle.text()).toBe('收起')

    const short = mount(BusinessAgentAnswer, { props: { text: '结论一句。\n\n第二段。' } })
    expect(short.find('[data-testid="business-agent-answer-toggle"]').exists()).toBe(false)
  })
})
