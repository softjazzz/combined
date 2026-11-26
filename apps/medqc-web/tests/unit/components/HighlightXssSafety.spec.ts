import { afterEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { buildHighlightedSegments, useDefectHighlight } from '@/composables/useDefectHighlight'
import ICDSearchPanel from '@/views/workstation-v4/components/ICDSearchPanel.vue'
import PreAnalysisView from '@/views/workstation-v4/frontpage/components/PreAnalysisView.vue'

vi.mock('@/api/drg', () => ({
  getPreGroupingHistory: vi.fn().mockResolvedValue([]),
  triggerAdmissionPreGrouping: vi.fn().mockResolvedValue({ success: true }),
  suggestGroupingCorrections: vi.fn().mockResolvedValue(null),
}))

vi.mock('@/views/drg-grouper/dipGrouper', () => ({
  performDipGrouping: vi.fn().mockReturnValue({
    status: '入组成功',
    dipCode: 'I10',
    dipName: '高血压病',
    messages: ['命中主诊断 I10.001 <img src=x onerror=alert(2)>'],
    matchType: '主诊断匹配',
    score: 100,
  }),
}))

describe('病历高亮、分析轨迹与 ICD 搜索 XSS 防护', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('buildHighlightedSegments 与 highlightDefects 均对高亮前后正文与缺陷内容安全转义', () => {
    const content = '前文<img src=x onerror=alert(1)>目标<svg onload=alert(2)>后文<script>alert(3)</script>'
    const start = content.indexOf('目标')
    const end = start + '目标<svg onload=alert(2)>'.length
    const ann = {
      defect_id: 'D1" onclick="alert(9)',
      start_offset: start,
      end_offset: end,
      keyword: '目标<svg onload=alert(2)>',
      description: '描述<img src=y onerror=alert(4)>',
      suggestion: '建议<img src=z onerror=alert(5)>',
      severity: 'error' as const,
      rule_name: 'R',
      category: 'C',
    }

    const segments = buildHighlightedSegments(content, [ann])
    expect(segments.map((s) => s.type)).toEqual(['text', 'defect', 'text'])
    expect(segments[0]).toEqual({ type: 'text', text: '前文<img src=x onerror=alert(1)>' })
    expect(segments[2]).toEqual({ type: 'text', text: '后文<script>alert(3)</script>' })

    const html = useDefectHighlight().highlightDefects(content, [ann])
    expect(html).not.toContain('<img')
    expect(html).not.toContain('<svg')
    expect(html).not.toContain('<script>')
    expect(html).not.toContain('onclick="alert(9)"')
    expect(html).toContain('&lt;img src=x onerror=alert(1)&gt;')
    expect(html).toContain('&lt;svg onload=alert(2)&gt;')
    expect(html).toContain('&lt;script&gt;alert(3)&lt;/script&gt;')
    expect(html).toContain('class="emr-defect emr-defect--error"')
  })

  it('ICDSearchPanel 高亮匹配词时对诊断名称中的 HTML 载荷按文本安全渲染', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockImplementation((url: string) => {
        if (String(url).includes('/api/v1/icd/search')) {
          return Promise.resolve({
            ok: true,
            status: 200,
            json: async () => ({
              success: true,
              data: {
                items: [
                  {
                    code: 'I10.x00',
                    name: '高血压<img src=x onerror=alert(1)>危象',
                    type: 'icd10',
                  },
                ],
                total: 1,
              },
            }),
          })
        }
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({ success: true, data: { items: [], total: 0, chapters: [] } }),
        })
      }),
    )

    const wrapper = mount(ICDSearchPanel, {
      global: {
        stubs: {
          'a-radio-group': true,
          'a-radio-button': true,
          'a-input-search': true,
          'a-spin': true,
          'a-button': true,
          'a-tree': true,
          MqIcon: true,
          ICDDetailPanel: true,
        },
      },
    })
    await flushPromises()

    const vm = wrapper.vm as unknown as {
      searchQuery: string
      doSearch: (offset?: number) => Promise<void>
    }
    vm.searchQuery = '高血压'
    await vm.doSearch(0)
    await flushPromises()

    expect(wrapper.find('img').exists()).toBe(false)
    expect(wrapper.find('mark').text()).toBe('高血压')
    expect(wrapper.text()).toContain('高血压<img src=x onerror=alert(1)>危象')
    wrapper.unmount()
  })

  it('PreAnalysisView 病历高亮与执行轨迹中的 HTML 载荷按文本安全渲染', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => ({
          success: true,
          data: {
            admission_id: 'ADM-XSS-1',
            diagnoses: {
              discharge_main_diagnosis_text: '高血压<img src=x onerror=alert(1)>',
              discharge_main_icd: 'I10.x00',
              discharge_other_diagnoses_texts: [],
            },
            procedures: {},
            costs: { total_cost: 900 },
          },
        }),
      }),
    )

    const wrapper = mount(PreAnalysisView, {
      global: {
        stubs: {
          'a-spin': true,
          'a-tag': true,
          'a-select': true,
          'a-select-option': true,
          'a-input-number': true,
          'a-input': true,
          'a-tooltip': true,
        },
      },
    })
    await flushPromises()

    const textarea = wrapper.find('textarea')
    if (textarea.exists()) {
      await textarea.setValue('出院诊断：高血压<img src=x onerror=alert(1)>')
    }
    const extractBtn = wrapper.findAll('button').find((btn) => btn.text().includes('抽取'))
    expect(extractBtn).toBeTruthy()
    await extractBtn!.trigger('click')
    await flushPromises()

    expect(wrapper.find('img').exists()).toBe(false)
    expect(wrapper.find('mark.hl-diag').text()).toBe('高血压<img src=x onerror=alert(1)>')
    expect(wrapper.find('code.trace-code').text()).toBe('I10.001')
    expect(wrapper.text()).toContain('命中主诊断 I10.001 <img src=x onerror=alert(2)>')
    wrapper.unmount()
  })
})
