import { describe, expect, it } from 'vitest'
import {
  buildSingleRecordQcPresentation,
  buildSingleRecordQcResultItems,
  buildSingleRecordQcStatusTabs,
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

  it('解释不足原因不能驱动前端重算服务端最终状态', () => {
    const items: SingleRecordQcResultItem[] = [
      {
        rule_id: 'LX0609-029',
        rule_name: '术前小结',
        status: 'non_compliant',
        reason_code: 'customer_explanation_incomplete',
        conclusion: '服务端仍交付为确定问题',
        evidence: [],
      },
      {
        rule_id: 'LX0609-040',
        rule_name: '术前多学科讨论',
        status: 'uncertain',
        reason_code: 'customer_explanation_incomplete',
        conclusion: '服务端已终结为待确认',
        evidence: [],
      },
    ]

    const rendered = buildSingleRecordQcResultItems(items)
    const tabs = buildSingleRecordQcStatusTabs(rendered)

    expect(rendered[0]).toMatchObject({
      status: 'non_compliant',
      reason_code: 'customer_explanation_incomplete',
      displayStatus: '确定问题',
      tone: 'danger',
    })
    expect(rendered[1]).toMatchObject({
      status: 'uncertain',
      reason_code: 'customer_explanation_incomplete',
      displayStatus: '待确认',
      tone: 'warning',
    })
    expect(tabs.find((item) => item.key === 'non_compliant')?.count).toBe(1)
    expect(tabs.find((item) => item.key === 'pending')?.count).toBe(1)
  })
})

describe('single-record-result-model 病历质控报告分组', () => {
  it('按权威来源文书稳定分组，并保持 Envelope 条目顺序', () => {
    const items: SingleRecordQcResultItem[] = [
      {
        rule_id: 'LX0609-025',
        rule_name: '植入物相关记录',
        source_document: '手术记录',
        qc_point: '未记录植入物种类及数量',
        status: 'non_compliant',
      },
      {
        rule_id: 'LX0609-020',
        rule_name: '会诊意见执行情况',
        source_document: '会诊记录',
        qc_point: '后续病程未记录会诊意见执行情况',
        status: 'data_gap',
      },
      {
        rule_id: 'LX0609-031',
        rule_name: '手术记录签名',
        source_document: '手术记录',
        qc_point: '手术记录签名不规范',
        status: 'uncertain',
      },
    ]

    const presentation = buildSingleRecordQcPresentation(items)

    expect(presentation.sectionsByTab.all).toHaveLength(2)
    expect(presentation.sectionsByTab.all.map((group) => group.sourceDocument)).toEqual([
      '手术记录',
      '会诊记录',
    ])
    expect(presentation.sectionsByTab.all[0]?.items.map((item) => item.rule_id)).toEqual([
      'LX0609-025',
      'LX0609-031',
    ])
    expect(presentation.sectionsByTab.non_compliant[0]?.items[0]).toMatchObject({
      rule_id: 'LX0609-025',
      source_document: '手术记录',
      qc_point: '未记录植入物种类及数量',
      status: 'non_compliant',
    })
  })

  it('缺失或重复规则身份失败关闭，不静默去重或合并结论', () => {
    const items: SingleRecordQcResultItem[] = [
      {
        rule_id: 'LX0609-025',
        rule_name: '植入物相关记录',
        source_document: '手术记录',
        status: 'non_compliant',
      },
      {
        rule_id: 'lx0609-025',
        rule_name: '植入物相关记录',
        source_document: '病程记录',
        status: 'data_gap',
      },
    ]

    expect(() => buildSingleRecordQcPresentation(items)).toThrowError(
      '单病历质控结果存在重复规则：LX0609-025',
    )
    expect(() =>
      buildSingleRecordQcPresentation([
        { rule_id: ' ', rule_name: '缺少规则身份', status: 'non_compliant' },
      ]),
    ).toThrowError('单病历质控结果缺少规则身份')
  })

  it('严格拆分确定问题、资料待核实、待判断、合规、不适用、系统异常和其他结果', () => {
    const statuses: SingleRecordQcResultItem['status'][] = [
      'non_compliant',
      'data_gap',
      'uncertain',
      'evaluation_unknown',
      'ai_suggested_non_compliant',
      'technical_error',
      'compliant',
      'not_applicable',
      'not_executed',
      'ai_suggested_compliant',
    ]
    const items = statuses.map((status, index) => ({
      rule_id: `LX0609-${String(index + 1).padStart(3, '0')}`,
      rule_name: `规则${index + 1}`,
      source_document: '病程记录',
      status,
    }))

    const presentation = buildSingleRecordQcPresentation(items)

    expect(presentation.counts).toEqual({
      nonCompliant: 1,
      dataGap: 1,
      uncertain: 3,
      compliant: 1,
      notApplicable: 1,
      technicalError: 1,
      other: 2,
    })
    expect(
      presentation.sectionsByTab.non_compliant
        .flatMap((group) => group.items)
        .map((item) => item.status),
    ).toEqual(['non_compliant'])
    expect(
      presentation.sectionsByTab.data_gap
        .flatMap((group) => group.items)
        .map((item) => item.status),
    ).toEqual(['data_gap'])
    expect(
      presentation.sectionsByTab.uncertain
        .flatMap((group) => group.items)
        .map((item) => item.status),
    ).toEqual(['uncertain', 'evaluation_unknown', 'ai_suggested_non_compliant'])
    expect(
      presentation.sectionsByTab.compliant
        .flatMap((group) => group.items)
        .map((item) => item.status),
    ).toEqual(['compliant'])
    expect(
      presentation.sectionsByTab.not_applicable
        .flatMap((group) => group.items)
        .map((item) => item.status),
    ).toEqual(['not_applicable'])
    expect(
      presentation.sectionsByTab.all.flatMap((group) => group.items).map((item) => item.status),
    ).toEqual(statuses)
  })

  it('缺少来源文书时只进入其他质控点，不根据规则编号或证据猜测分组', () => {
    const presentation = buildSingleRecordQcPresentation([
      {
        rule_id: 'LX0609-066',
        rule_name: '术后首次病程记录',
        source_document: '   ',
        status: 'non_compliant',
        evidence: [{ source_ref: 'src_066', source_type: 'postoperative_course' }],
      },
    ])

    expect(presentation.sectionsByTab.all).toEqual([
      expect.objectContaining({
        sourceDocument: '其他质控点',
        items: [expect.objectContaining({ rule_id: 'LX0609-066' })],
      }),
    ])
  })
})
