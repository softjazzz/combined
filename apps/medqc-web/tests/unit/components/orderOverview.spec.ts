import { describe, expect, it } from 'vitest'
import { normalizeOrderRow, type OrderDocLike } from '@/components/qc/orderOverview'

function makeOrderDoc(content: string, extra: Partial<OrderDocLike> = {}): OrderDocLike {
  return {
    doc_key: `order-${content}`,
    doc_type: 'inpat_drug_order',
    doc_name: content,
    document_title: content,
    content,
    source_table: 'inpat_drug_order',
    group_key: 'orders',
    source_fields: [],
    ...extra,
  }
}

describe('orderOverview', () => {
  it('不把今日出院/明日出院归为药品医嘱', () => {
    expect(normalizeOrderRow(makeOrderDoc('今日出院'), 0).category).toBe('discharge_admin')
    expect(normalizeOrderRow(makeOrderDoc('明日出院'), 1).category).toBe('discharge_admin')
  })

  it('不把抗体测定类医嘱归为药品医嘱', () => {
    expect(normalizeOrderRow(makeOrderDoc('甲肝抗体两项测定'), 0).category).toBe('exam_lab')
    expect(normalizeOrderRow(makeOrderDoc('戊肝抗体两项测定'), 1).category).toBe('exam_lab')
  })

  it('有明确剂量频次用法的医嘱仍归为药品', () => {
    const row = normalizeOrderRow(
      makeOrderDoc('阿莫西林胶囊', {
        source_fields: [
          { source_field: 'order_name', raw_value_preview: '阿莫西林胶囊' },
          { source_field: 'dosage', raw_value_preview: '0.5g' },
          { source_field: 'frequency', raw_value_preview: 'tid' },
          { source_field: 'usage', raw_value_preview: '口服' },
        ],
      }),
      0,
    )
    expect(row.category).toBe('drug')
    expect(row.doseUsage).toBe('0.5g / tid / 口服')
  })

  it('来源表含 inpat_drug_order 但内容明显非药品时不误判为药品', () => {
    const row = normalizeOrderRow(
      makeOrderDoc('心电图检查', {
        source_table: 'inpat_drug_order',
        doc_type: 'inpat_drug_order',
      }),
      0,
    )
    expect(row.category).toBe('exam_lab')
  })
})
