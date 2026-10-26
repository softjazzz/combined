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
  it('计划开始优先于开嘱时间，分别保留计划结束和实际停止', () => {
    const row = normalizeOrderRow(
      makeOrderDoc('病危', {
        planned_start_datetime: '2026-05-31T05:20:19Z',
        order_start_time: '2026-05-31 13:21:54',
        order_planned_end_time: '2026-06-03T03:30:42Z',
        source_fields: [
          { source_field: 'canceled_datetime', raw_value_preview: '2026-06-02 08:00:00' },
        ],
      }),
      0,
    )
    expect(row.startTime).toBe('2026-05-31 13:20:19')
    expect(row.plannedEndTime).toBe('2026-06-03 11:30:42')
    expect(row.stopTime).toBe('')
    expect(row.searchText).toContain('2026-06-03 11:30:42')
  })

  it('兼容旧文书受控来源字段；无时区的开始时间不按浏览器时区偏移', () => {
    const row = normalizeOrderRow(
      makeOrderDoc('病危', {
        source_fields: [
          { source_field: 'prescribed_datetime', raw_value_preview: '2026-06-03 12:09:54' },
          { source_field: 'planned_start_datetime', raw_value_preview: '2026-06-03 12:09:51' },
          { source_field: 'planned_end_datetime', raw_value_preview: '2026-06-08 09:19:22+08:00' },
          { source_field: 'stop_time', raw_value_preview: '2026-06-08T02:00:00Z' },
        ],
      }),
      0,
    )
    expect(row.startTime).toBe('2026-06-03 12:09:51')
    expect(row.plannedEndTime).toBe('2026-06-08 09:19:22')
    expect(row.stopTime).toBe('2026-06-08 10:00:00')
    const legacy = normalizeOrderRow(
      makeOrderDoc('护理', {
        source_fields: [
          { source_field: 'prescribed_datetime', raw_value_preview: '2026-06-03 12:09:54' },
        ],
      }),
      1,
    )
    expect(legacy.startTime).toBe('2026-06-03 12:09:54')
    expect(legacy.plannedEndTime).toBe('')
    expect(legacy.stopTime).toBe('')
  })

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
