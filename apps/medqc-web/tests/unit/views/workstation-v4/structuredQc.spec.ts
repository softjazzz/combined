import { describe, expect, it } from 'vitest'
import {
  createDefaultStructuredQCFilter,
  filterStructuredQCIssues,
  mapBatchJobToStructuredQC,
  mapSichuanEvaluationToStructuredQC,
} from '@/views/workstation-v4/utils/structuredQc'
import type {
  SichuanBatchJob,
  SichuanBatchJobDebugSnapshot,
} from '@/views/workstation-v4/semantic-rules/types'

describe('structuredQc mapper', () => {
  it('应将单病历 evaluate 结果映射为统一结构', () => {
    const result = mapSichuanEvaluationToStructuredQC(
      {
        evaluation_summary: {
          total_rules: 3,
          compliant_rules: 1,
          not_applicable: 1,
          uncertain_count: 0,
          issues_found: 1,
        },
        performance_metrics: {
          processing_time: 2.2,
        },
        evaluation_results: [
          {
            rule_id: 'SC-001',
            rule_code: 'SC-001',
            rule_name: '规则1',
            status: 'non_compliant',
            findings: '命中问题',
            evidence: '证据段落',
            suggestion: '整改建议',
            confidence: 0.91,
            document_type: '出院记录',
            execution_domain: 'discharge',
            defect_level: '严重缺陷',
            metadata: {
              trace_id: 'trace-1',
              cache_hit: true,
            },
          },
        ],
      },
      { docCount: 2 },
    )

    expect(result.overview.totalRules).toBe(3)
    expect(result.overview.issueCount).toBe(1)
    expect(result.overview.docCount).toBe(2)
    expect(result.issues).toHaveLength(1)
    expect(result.issues[0]?.ruleCode).toBe('SC-001')
    expect(result.issues[0]?.metadata.traceId).toBe('trace-1')
    expect(result.groups.some((group) => group.kind === 'document')).toBe(true)
  })

  it('batch 明细缺失时应回退 debug.recent_items 并归一状态', () => {
    const job: SichuanBatchJob = {
      id: 'job-1',
      rule_code: 'SC-BATCH',
      rule_name: '批量任务',
      scope: 'final',
      status: 'completed',
      summary: {
        total_records: 1,
        success_count: 1,
        failed_count: 0,
        issue_records: 1,
        compliant_records: 0,
        total_tokens: 0,
        total_processing_time: 3,
      },
      rule_results: [],
    }
    const debug: SichuanBatchJobDebugSnapshot = {
      job_id: 'job-1',
      status: 'completed',
      scope: 'final',
      rules: [],
      recent_items: [
        {
          rule_job_id: 'rule-job-1',
          rule_id: 'SC-023',
          rule_code: 'SC-023',
          record_id: 'MV2-REAL-001',
          status: 'uncertain',
          is_compliant: false,
          findings: '证据不足',
          evidence: '病历片段',
          prompt_version: 'p1',
          model_version: 'm1',
        },
      ],
      recent_failed_records: [],
    }

    const result = mapBatchJobToStructuredQC(job, debug)
    expect(result.issues).toHaveLength(1)
    expect(result.issues[0]?.ruleJobId).toBe('rule-job-1')
    expect(result.issues[0]?.status).toBe('uncertain')
    expect(result.issues[0]?.metadata.promptVersion).toBe('p1')
  })

  it('默认过滤应只保留问题项（不合规+AI判断）', () => {
    const mapped = mapSichuanEvaluationToStructuredQC({
      evaluation_summary: { total_rules: 3, issues_found: 2 },
      evaluation_results: [
        { rule_id: 'SC-001', status: 'non_compliant', findings: '问题1' },
        { rule_id: 'SC-002', status: 'uncertain', findings: '问题2' },
        { rule_id: 'SC-003', status: 'compliant', findings: '通过' },
      ],
    })
    const filtered = filterStructuredQCIssues(mapped.issues, createDefaultStructuredQCFilter())
    expect(filtered).toHaveLength(2)
    expect(filtered.every((item) => item.status !== 'compliant')).toBe(true)
  })
})
