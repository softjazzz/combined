import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import ReadonlyMedicalDocumentContent from '@/views/workstation-v4/customer-sample-validation/ReadonlyMedicalDocumentContent.vue'
import { normalizeFrontpageDisplay } from '@/views/workstation-v4/customer-sample-validation/frontpageDisplay'
import FrontpageSheet from '@/views/workstation-v4/components/FrontpageSheet.vue'

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
    expect(wrapper.findComponent(FrontpageSheet).exists()).toBe(true)
    expect(wrapper.get('.fp-title').text().replace(/\s+/gu, '')).toBe('住院病案首页')
    expect(wrapper.find('.fp-evidence-section').exists()).toBe(false)
    expect(wrapper.text()).not.toContain('由 AI 自动提取生成')
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

  it('复用系统首页时完整保留23条诊断，不把首条未知类型诊断提升为主要诊断', () => {
    const value = display()
    if (!value) throw new Error('缺少测试首页')
    value.diagnoses.rows = Array.from({ length: 23 }, (_, index) => ({
      diagnosis_type: index === 0 ? null : '其他诊断',
      diagnosis_name: `合成诊断${String(index + 1).padStart(2, '0')}`,
      diagnosis_code: `TEST${index + 1}`,
      admission_condition: null,
    }))
    const before = JSON.stringify(value)
    const wrapper = mount(ReadonlyMedicalDocumentContent, {
      props: {
        document: {
          key: 'many',
          document_type: 'mr',
          title: '首页',
          content: '',
          frontpage_display: value,
        },
      },
    })
    const names = wrapper
      .findAll('.fp-diag-text')
      .map((item) => item.text())
      .filter(Boolean)
    expect(names).toHaveLength(23)
    for (let index = 1; index <= 23; index += 1) {
      expect(names.some((name) => name.includes(`合成诊断${String(index).padStart(2, '0')}`))).toBe(
        true,
      )
    }
    expect(names.some((name) => name.startsWith('主要诊断：'))).toBe(false)
    expect(JSON.stringify(value)).toBe(before)
  })

  it('只读源首页没有机构和国籍时如实显示未返回，零费用不丢失', () => {
    const wrapper = mount(FrontpageSheet, {
      props: {
        data: { basic: { document_id: '不是病案号' }, cost: { total_cost: 0, self_pay: 0 } },
        sourceReadonly: true,
      },
    })
    expect(wrapper.text()).not.toContain('泸县人民医院')
    expect(wrapper.text()).not.toContain('中国')
    expect(wrapper.text()).not.toContain('不是病案号')
    const costCells = wrapper
      .findAll('td')
      .filter((cell) => /住院总费用|自付金额/u.test(cell.text()))
    expect(costCells.map((cell) => cell.find('u').text())).toEqual(['0', '0'])
    expect(wrapper.text()).toContain('未返回')
  })

  it('未传只读模式时保留原系统首页默认值、诊断布局和证据入口', () => {
    const wrapper = mount(FrontpageSheet, {
      props: {
        data: {
          basic: {},
          diagnoses: [{ diagnosis_name: '合成诊断', diagnosis_type: '主要诊断' }],
        },
      },
      global: { stubs: { MainDiagnosisEvidenceModal: true } },
    })
    expect(wrapper.text()).toContain('泸县人民医院')
    expect(wrapper.text()).toContain('中国')
    expect(wrapper.text()).toContain('由 AI 自动提取生成')
    expect(wrapper.findAll('.fp-diag-text')).toHaveLength(20)
    expect(wrapper.find('.fp-evidence-section').exists()).toBe(true)
  })

  it('按源类型区分门诊、入院及出院诊断，主要诊断只认源端明确标记', () => {
    const diagnoses = [
      { diagnosis_type: '入院诊断', diagnosis_name: '合成入院诊断', diagnosis_code: 'IN' },
      { diagnosis_type: '门诊诊断', diagnosis_name: '合成门诊诊断', diagnosis_code: 'OUT' },
      ...Array.from({ length: 21 }, (_, index) => ({
        diagnosis_type: '出院诊断',
        diagnosis_main: index === 20 ? '是' : '否',
        diagnosis_name: `合成出院${index + 1}`,
        diagnosis_code: `DX${index + 1}`,
      })),
    ]
    const wrapper = mount(FrontpageSheet, { props: { data: { diagnoses }, sourceReadonly: true } })
    expect(wrapper.get('[data-testid="frontpage-outpatient-diagnosis"]').text()).toContain(
      '合成门诊诊断',
    )
    expect(wrapper.get('[data-testid="frontpage-outpatient-diagnosis"]').text()).not.toContain(
      '合成入院诊断',
    )
    expect(wrapper.get('[data-testid="frontpage-admission-diagnosis"]').text()).toContain(
      '合成入院诊断',
    )
    const cells = wrapper
      .findAll('.fp-diag-text')
      .map((cell) => cell.text())
      .filter(Boolean)
    expect(cells).toHaveLength(21)
    expect(cells[0]).toBe('主要诊断：合成出院21')
    expect(cells.some((cell) => /合成入院|合成门诊/u.test(cell))).toBe(false)
  })
})
