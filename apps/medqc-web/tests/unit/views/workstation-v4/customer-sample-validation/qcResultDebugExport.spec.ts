import { describe, expect, it, vi } from 'vitest'

import {
  buildQcResultDebugText,
  copyQcResultDebugText,
} from '@/views/workstation-v4/customer-sample-validation/qcResultDebugExport'

describe('qcResultDebugExport', () => {
  it('exports conclusion, controlled facts, criteria, data gaps and evidence without reinterpreting them', () => {
    const result = buildQcResultDebugText([
      {
        rule_id: 'LX0609-011',
        rule_name: 'CT/MRI 报告后病程记录',
        status: 'data_gap',
        display_status: '数据不足',
        reason_code: 'required_time_unavailable',
        conclusion: '缺少可用于时序核对的病程记录时间。',
        customer_display_facts: { report_time: '2026-08-19 10:00:00' },
        criterion_results: [
          {
            criterion_id: 'time_window',
            kind: 'date_interval',
            status: 'unknown',
            reason_code: 'required_time_unavailable',
          },
        ],
        data_gap_details: { missing_fields: ['daily_course_record.record_time'] },
        evidence: [
          {
            source_ref: 'exam-1',
            source_type: 'exam_master',
            record_time: '2026-08-19 10:00:00',
          },
        ],
      },
    ])

    expect(result).toContain('格式版本：medqc-qc-debug-v1')
    expect(result).toContain('LX0609-011 CT/MRI 报告后病程记录')
    expect(result).toContain('原始状态：data_gap')
    expect(result).toContain('原因码：required_time_unavailable')
    expect(result).toContain('质控结论：缺少可用于时序核对的病程记录时间。')
    expect(result).toContain('受控判定事实 customer_display_facts')
    expect(result).toContain('daily_course_record.record_time')
    expect(result).toContain('"source_ref": "exam-1"')
  })

  it('copies the generated text through the browser clipboard', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined)
    Object.defineProperty(navigator, 'clipboard', {
      configurable: true,
      value: { writeText },
    })

    await expect(copyQcResultDebugText('调试内容')).resolves.toBe(true)
    expect(writeText).toHaveBeenCalledWith('调试内容')
  })
})
