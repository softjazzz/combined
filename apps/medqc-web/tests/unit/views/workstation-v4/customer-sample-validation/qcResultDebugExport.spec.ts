import { describe, expect, it, vi } from 'vitest'

import {
  buildQcResultDebugText,
  copyQcResultDebugText,
} from '@/views/workstation-v4/customer-sample-validation/qcResultDebugExport'

describe('qcResultDebugExport', () => {
  it('exports conclusion, controlled facts, criteria, data gaps and evidence without reinterpreting them', () => {
    const result = buildQcResultDebugText(
      [
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
              source_ref: 'exam-safe-1',
              source_type: 'exam_master',
              source_label: 'CT检查主记录',
              record_time: '2026-08-19 10:00:00',
              field_path: 'exam_master.report_time',
              evidence_excerpt: '腹部CT检查完成。',
              excerpt_kind: '字段级依据',
            },
          ],
        },
      ],
      {
        instituteId: 'H1',
        patientId: 'P001',
        visitId: 'V001',
        recordRef: 'record-safe-1',
        jobId: 'job-safe-1',
        ruleSetKey: 'luxian_0609_qc_v1',
        ruleSetVersion: '2026.08.27',
        resultSchemaVersion: 'lx0609-single-record-result-v1',
        expectedRuleCount: 75,
        resultRuleCount: 75,
        isComplete: true,
      },
    )

    expect(result).toContain('格式版本：medqc-qc-debug-v2')
    expect(result).toContain('机构ID：H1')
    expect(result).toContain('患者ID：P001')
    expect(result).toContain('就诊ID：V001')
    expect(result).toContain('质控任务ID：job-safe-1')
    expect(result).toContain('规则集版本：2026.08.27')
    expect(result).toContain('结果完整性：完整')
    expect(result).toContain('- data_gap：1')
    expect(result).toContain('LX0609-011 CT/MRI 报告后病程记录')
    expect(result).toContain('原始状态：data_gap')
    expect(result).toContain('原因码：required_time_unavailable')
    expect(result).toContain('质控结论：缺少可用于时序核对的病程记录时间。')
    expect(result).toContain('受控判定事实 customer_display_facts')
    expect(result).toContain('daily_course_record.record_time')
    expect(result).toContain('关键证据 evidence（1 条）')
    expect(result).toContain('安全引用：exam-safe-1')
    expect(result).toContain('字段路径：exam_master.report_time')
    expect(result).toContain('关键原文摘要：腹部CT检查完成。')
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
