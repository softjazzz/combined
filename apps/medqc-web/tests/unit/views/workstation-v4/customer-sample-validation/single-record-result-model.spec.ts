import { describe, expect, it } from 'vitest'
import {
  buildSingleRecordQcResultItems,
  type SingleRecordQcResultItem,
} from '@/views/workstation-v4/customer-sample-validation/single-record-result-model'

describe('single-record-result-model canonical 直通展示', () => {
  it('保持引擎返回的业务字段，不用前端受控事实重写结论', () => {
    const source: SingleRecordQcResultItem = {
      rule_id: 'LX0609-025',
      rule_name: '植入物记录完整性',
      status: 'non_compliant',
      reason_code: 'implant_information_incomplete',
      conclusion: '引擎原始结论',
      detail: '引擎原始明细',
      suggestion: '引擎原始建议',
      customer_display_facts: {
        failure_kind: 'implant_information_incomplete',
        source_label: '手术记录',
        missing_fields: ['implant_barcode'],
      },
      evidence: [{ source_ref: 'src_001', source_type: 'operation_record' }],
    }

    const [rendered] = buildSingleRecordQcResultItems([source])

    expect(rendered).toMatchObject(source)
    expect(rendered?.conclusionText).toBe('引擎原始结论')
    expect(rendered?.status).toBe('non_compliant')
    expect(rendered?.reason_code).toBe('implant_information_incomplete')
    expect(rendered?.evidence).toEqual(source.evidence)
  })

  it('保持 Canonical Envelope 的条目顺序', () => {
    const items: SingleRecordQcResultItem[] = [
      {
        rule_id: 'LX0609-100',
        rule_name: '先返回的合规项',
        status: 'compliant',
        conclusion: '合规',
      },
      {
        rule_id: 'LX0609-001',
        rule_name: '后返回的问题项',
        status: 'non_compliant',
        conclusion: '不合规',
      },
    ]

    expect(buildSingleRecordQcResultItems(items).map((item) => item.rule_id)).toEqual([
      'LX0609-100',
      'LX0609-001',
    ])
  })

  it('运行时收到非数组 evidence 时不崩溃，并按空证据渲染', () => {
    const malformed = {
      rule_id: 'LX0609-003',
      rule_name: '手术记录及时性',
      status: 'not_applicable',
      conclusion: '本次不适用。',
      evidence: '完整适用性证据未触发本质控点。',
    } as unknown as SingleRecordQcResultItem

    expect(() => buildSingleRecordQcResultItems([malformed])).not.toThrow()
    expect(buildSingleRecordQcResultItems([malformed])[0]?.evidence).toEqual([])
  })
})
