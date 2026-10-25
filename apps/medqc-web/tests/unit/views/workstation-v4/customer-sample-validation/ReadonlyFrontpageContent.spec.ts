import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import ReadonlyMedicalDocumentContent from '@/views/workstation-v4/customer-sample-validation/ReadonlyMedicalDocumentContent.vue'
import { normalizeFrontpageDisplay } from '@/views/workstation-v4/customer-sample-validation/frontpageDisplay'

describe('病案首页只读展示', () => {
  const display = () =>
    normalizeFrontpageDisplay({
      groups: [
        {
          key: 'basic',
          label: '首页基本信息',
          fields: [
            { key: 'age_year', label: '年龄', value: null },
            { key: 'total_cost', label: '总费用', value: 0 },
          ],
        },
      ],
      diagnoses: {
        columns: [
          { key: 'diagnosis_name', label: '诊断名称' },
          { key: 'diagnosis_code', label: '诊断编码' },
        ],
        rows: [
          { diagnosis_name: '合成诊断甲', diagnosis_code: null },
          { diagnosis_name: '合成诊断乙', diagnosis_code: 'TEST' },
        ],
      },
      surgeries: { columns: [{ key: 'surgery_name', label: '手术名称' }], rows: [] },
    })

  it('通过原文书组件展示首页、所有诊断和未返回字段，0不误判为空', () => {
    const wrapper = mount(ReadonlyMedicalDocumentContent, {
      props: {
        document: {
          key: 'mr::test',
          document_type: 'mr',
          title: '病案首页',
          content: '备用文本',
          frontpage_display: display(),
        },
      },
    })
    expect(wrapper.get('[data-testid="readonly-frontpage"]').text()).toContain('首页基本信息')
    expect(wrapper.findAll('tbody tr')).toHaveLength(2)
    expect(wrapper.text()).toContain('合成诊断甲')
    expect(wrapper.text()).toContain('合成诊断乙')
    expect(wrapper.text()).toContain('手术及操作')
    expect(wrapper.findAll('dd').map((el) => el.text())).toEqual(['未返回', '0'])
    expect(wrapper.findAll('td').map((el) => el.text())).toContain('未返回')
    expect(wrapper.text()).not.toContain('备用文本')
    expect(wrapper.text()).not.toContain('无手术')
  })

  it('旧文书缺少首页投影时仍按原有内容展示', () => {
    const wrapper = mount(ReadonlyMedicalDocumentContent, {
      props: {
        document: { key: 'old', document_type: 'mr', title: '旧首页', content: '旧首页原文' },
      },
    })
    expect(wrapper.text()).toContain('旧首页原文')
    expect(wrapper.find('[data-testid="readonly-frontpage"]').exists()).toBe(false)
  })

  it('结构化内容按文本转义，不执行源端HTML', () => {
    const value = display()
    if (!value) throw new Error('缺少测试首页')
    value.groups[0].fields[0].value = '<img src=x onerror=alert(1)>'
    const wrapper = mount(ReadonlyMedicalDocumentContent, {
      props: {
        document: {
          key: 'safe',
          document_type: 'mr',
          title: '首页',
          content: '',
          frontpage_display: value,
        },
      },
    })
    expect(wrapper.find('img').exists()).toBe(false)
    expect(wrapper.text()).toContain('<img src=x onerror=alert(1)>')
  })

  it('边界归一化拒收对象值，保留false和0，不把旧应答伪造成首页', () => {
    expect(normalizeFrontpageDisplay(undefined)).toBeUndefined()
    const result = normalizeFrontpageDisplay({
      groups: [
        {
          key: 'a',
          fields: [
            { key: 'missing', value: {} },
            { key: 'zero', value: 0 },
            { key: 'false', value: false },
          ],
        },
      ],
    })
    expect(result?.groups[0].fields.map((field) => field.value)).toEqual([null, '0', 'false'])
  })
})
