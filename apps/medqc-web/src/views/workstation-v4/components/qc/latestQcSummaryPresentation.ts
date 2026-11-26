/**
 * 病历最新质控摘要的展示口径（运行/终末病历质控列表与病历池预览共用）。
 * 只把后端 latest_qc_summary 的状态计数翻译为界面文案，不重新判定状态。
 */
import { CAPTURE_FAILED_NOTICE, MATERIAL_PREPARATION_FAILED_LABEL } from '../../customer-sample-validation/single-record-result-model'
import { QC_RESULT_STATUS_LABELS } from '../../utils/qcResultStatusLabels'
import { parseQcTaskTime, shanghaiQcTaskTimeParts } from '../../utils/qcTaskTime'
import type { QcSummaryLoadState, RecordLatestQcSummary } from '../../types'
import type { QcRecordResultRow } from './QcRecordResultTable.vue'

export function statusCount(statusCounts: Record<string, number>, status: string): number {
  const value = Number(statusCounts[status] || 0)
  return Number.isFinite(value) && value > 0 ? value : 0
}

export function formatQcCompletedAt(value?: string | null): string {
  const date = parseQcTaskTime(value)
  if (!date) return '—'
  const { year, month, day, hour, minute } = shanghaiQcTaskTimeParts(date)
  return `${year}-${month}-${day} ${hour}:${minute}`
}

export interface ResolveResultPresentationOptions {
  confirmedOnly?: boolean
}

export function resolveResultPresentation(
  summary?: RecordLatestQcSummary,
  summaryState?: QcSummaryLoadState,
  options?: ResolveResultPresentationOptions,
): Pick<QcRecordResultRow, 'resultStatus' | 'resultLabel' | 'issueSummary' | 'latestQcTime'> {
  const confirmedOnly = options?.confirmedOnly === true
  if (!summary) {
    if (summaryState === 'pending') {
      return {
        resultStatus: 'unknown',
        resultLabel: '质控摘要加载中',
        issueSummary: '质控摘要加载中',
        latestQcTime: '—',
      }
    }
    if (summaryState === 'unavailable') {
      return {
        resultStatus: 'unknown',
        resultLabel: '质控摘要暂不可用',
        issueSummary: '质控摘要暂不可用',
        latestQcTime: '—',
      }
    }
    return {
      resultStatus: 'not-run',
      resultLabel: '未质控',
      issueSummary: '暂无结果',
      latestQcTime: '—',
    }
  }

  if (confirmedOnly) {
    if (summary.status === 'not_run' || !summary.status) {
      return {
        resultStatus: 'not-run',
        resultLabel: '未质控',
        issueSummary: '暂无结果',
        latestQcTime: '—',
      }
    }
    const confirmedIssues = statusCount(summary.statusCounts || {}, 'non_compliant')
    if (confirmedIssues > 0) {
      return {
        resultStatus: 'priority',
        resultLabel: '需优先复核',
        issueSummary: `有 ${confirmedIssues} 项确定问题`,
        latestQcTime: formatQcCompletedAt(summary.completedAt),
      }
    }
    if (summary.status === 'ready') {
      return {
        resultStatus: 'completed',
        resultLabel: '已完成',
        issueSummary: '未发现确定问题',
        latestQcTime: formatQcCompletedAt(summary.completedAt),
      }
    }
    return {
      resultStatus: 'not-run',
      resultLabel: '未质控',
      issueSummary: '暂无结果',
      latestQcTime: '—',
    }
  }

  if (summary.status === 'failed' || summary.executionStatus === 'failed') {
    return {
      resultStatus: 'technical-error', resultLabel: '执行失败',
      issueSummary: `执行失败 · ${summary.failedRuleCount || 0} 项失败，尚无有效结果`,
      latestQcTime: formatQcCompletedAt(summary.completedAt),
    }
  }
  if (summary.status === 'technical_error') {
    if (summary.failureStage) {
      return {
        resultStatus: 'technical-error',
        resultLabel: MATERIAL_PREPARATION_FAILED_LABEL,
        issueSummary: CAPTURE_FAILED_NOTICE,
        latestQcTime: formatQcCompletedAt(summary.completedAt),
      }
    }
    return {
      resultStatus: 'technical-error',
      resultLabel: QC_RESULT_STATUS_LABELS.technical_error,
      issueSummary: '请复核结果交付',
      latestQcTime: '—',
    }
  }
  if (summary.status !== 'ready') {
    return {
      resultStatus: 'not-run',
      resultLabel: '未质控',
      issueSummary: '暂无结果',
      latestQcTime: '—',
    }
  }

  const statusCounts = summary.statusCounts || {}
  const nonCompliant = statusCount(statusCounts, 'non_compliant')
  const dataGap = statusCount(statusCounts, 'data_gap')
  const uncertain = statusCount(statusCounts, 'uncertain')
  if (summary.executionStatus === 'partial_failed') {
    return {
      resultStatus: 'technical-error', resultLabel: '部分执行失败',
      issueSummary: [
        '部分执行失败',
        `${summary.totalRuleCount || 0} 项有效结果`,
        `${summary.failedRuleCount || 0} 项失败`,
        nonCompliant ? `${QC_RESULT_STATUS_LABELS.non_compliant} ${nonCompliant}` : '',
        dataGap ? `待核实 ${dataGap}` : '',
        uncertain ? `${QC_RESULT_STATUS_LABELS.uncertain} ${uncertain}` : '',
      ].filter(Boolean).join(' · '),
      latestQcTime: formatQcCompletedAt(summary.completedAt),
    }
  }
  const issueSummary =
    [
      nonCompliant > 0 ? `${QC_RESULT_STATUS_LABELS.non_compliant} ${nonCompliant}` : '',
      dataGap > 0 ? `待核实 ${dataGap}` : '',
      uncertain > 0 ? `${QC_RESULT_STATUS_LABELS.uncertain} ${uncertain}` : '',
    ]
      .filter(Boolean)
      .join(' · ') || '未发现确定问题'

  if (nonCompliant > 0) {
    return {
      resultStatus: 'priority',
      resultLabel: '需优先复核',
      issueSummary,
      latestQcTime: formatQcCompletedAt(summary.completedAt),
    }
  }
  if (dataGap > 0) {
    return {
      resultStatus: 'data-gap',
      resultLabel: QC_RESULT_STATUS_LABELS.data_gap,
      issueSummary,
      latestQcTime: formatQcCompletedAt(summary.completedAt),
    }
  }
  if (uncertain > 0) {
    return {
      resultStatus: 'uncertain',
      resultLabel: QC_RESULT_STATUS_LABELS.uncertain,
      issueSummary,
      latestQcTime: formatQcCompletedAt(summary.completedAt),
    }
  }
  return {
    resultStatus: 'completed',
    resultLabel: '已完成',
    issueSummary,
    latestQcTime: formatQcCompletedAt(summary.completedAt),
  }
}
