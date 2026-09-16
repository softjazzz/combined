import { describe, expect, it } from 'vitest'
import {
  batchJobDiagnosticFilename,
  buildBatchJobDiagnosticText,
} from '@/views/workstation-v4/semantic-rules/batchJobDiagnosticExport'
import type {
  SichuanBatchJob,
  SichuanBatchJobDebugSnapshot,
} from '@/views/workstation-v4/semantic-rules/types'

describe('质控任务诊断包', () => {
  it('保留失败定位信息并移除身份、凭证和原始模型内容', () => {
    const job: SichuanBatchJob = {
      id: 'job-1',
      rule_code: 'LX0609',
      rule_name: '泸县质控',
      scope: 'running',
      status: 'failed',
      total_records: 2,
      success_count: 1,
      failed_count: 1,
      summary: {
        total_records: 2,
        success_count: 1,
        failed_count: 1,
        issue_records: 0,
        compliant_records: 1,
        total_tokens: 120,
        total_processing_time: 3,
        completed_rule_count: 1,
        failed_rule_count: 1,
        execution_status: 'partial_failed',
      },
      failed_records: [
        {
          visit_id: '2608958',
          patient_name: '真实姓名',
          rule_id: 'LX0609-011',
          reason_code: 'model_invalid_output',
          error_phase: 'result_status',
          error: '患者真实姓名（就诊号 2608958）Authorization=Bearer secret-token',
          trace_id: 'trace-1',
        },
      ],
    }
    const snapshot: SichuanBatchJobDebugSnapshot = {
      job_id: job.id,
      status: job.status,
      scope: job.scope,
      rules: [
        {
          rule_job_id: 'rule-job-1',
          rule_code: 'LX0609-011',
          rule_name: '检查记录',
          status: 'failed',
          debug: {
            trace_id: 'trace-1',
            raw_prompt: '完整病历原文',
            api_key: 'secret-key',
          },
        },
      ],
      recent_items: [
        {
          visit_id: '2608958',
          patient_name: '真实姓名',
          rule_id: 'LX0609-011',
          status: 'technical_error',
          is_compliant: null,
          llm_raw_output: '模型完整原始响应',
        },
      ],
      recent_failed_records: [],
    }

    const text = buildBatchJobDiagnosticText(job, snapshot, '2026-09-16T12:00:00.000Z')

    expect(text).toContain('model_invalid_output')
    expect(text).toContain('result_status')
    expect(text).toContain('trace-1')
    expect(text).toContain('病例-001')
    expect(text).not.toContain('2608958')
    expect(text).not.toContain('真实姓名')
    expect(text).not.toContain('secret-token')
    expect(text).not.toContain('secret-key')
    expect(text).not.toContain('完整病历原文')
    expect(text).not.toContain('模型完整原始响应')
    expect(batchJobDiagnosticFilename(job)).toBe('质控任务诊断包_job-1.md')
  })
})
