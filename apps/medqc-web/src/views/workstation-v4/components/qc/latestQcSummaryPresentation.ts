/**
 * 病历最新质控摘要的展示口径（运行/终末病历质控列表与病历池预览共用）。
 * 只把后端 latest_qc_summary 的状态计数翻译为界面文案，不重新判定状态。
 */
import type { RecordLatestQcSummary } from '../../types'
import type { QcRecordResultRow } from './QcRecordResultTable.vue'

export function statusCount(statusCounts: Record<string, number>, status: string): number {
  const value = Number(statusCounts[status] || 0)
  return Number.isFinite(value) && value > 0 ? value : 0
}

const beijingQcTimeFormatter = new Intl.DateTimeFormat('zh-CN', {
  timeZone: 'Asia/Shanghai',
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
  hour: '2-digit',
  minute: '2-digit',
  hourCycle: 'h23',
})

export function formatQcCompletedAt(value?: string | null): string {
  const text = String(value || '').trim()
  if (!text) return '—'
  const normalized = text.replace(' ', 'T')
  // 工作区任务时间由 datetime.utcnow() 产生，历史值没有时区后缀，但语义为 UTC。
  const timestamp = /(?:Z|[+-]\d{2}:\d{2})$/iu.test(normalized) ? normalized : `${normalized}Z`
  const date = new Date(timestamp)
  if (Number.isNaN(date.getTime())) return '—'
  const parts = Object.fromEntries(
    beijingQcTimeFormatter
      .formatToParts(date)
      .filter((part) => part.type !== 'literal')
      .map((part) => [part.type, part.value]),
  )
  return `${parts.year}-${parts.month}-${parts.day} ${parts.hour}:${parts.minute}`
}

export function resolveResultPresentation(
  summary?: RecordLatestQcSummary,
): Pick<QcRecordResultRow, 'resultStatus' | 'resultLabel' | 'issueSummary' | 'latestQcTime'> {
  if (summary?.status === 'failed' || summary?.executionStatus === 'failed') {
    return {
      resultStatus: 'technical-error', resultLabel: '执行失败',
      issueSummary: `执行失败 · ${summary.failedRuleCount || 0} 项失败，尚无有效结果`,
      latestQcTime: formatQcCompletedAt(summary.completedAt),
    }
  }
  if (summary?.status === 'technical_error') {
    return {
      resultStatus: 'technical-error',
      resultLabel: '结果校验异常',
      issueSummary: '请复核结果交付',
      latestQcTime: '—',
    }
  }
  if (summary?.status !== 'ready') {
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
        nonCompliant ? `确定问题 ${nonCompliant}` : '',
        dataGap ? `待核实 ${dataGap}` : '',
        uncertain ? `待判断 ${uncertain}` : '',
      ].filter(Boolean).join(' · '),
      latestQcTime: formatQcCompletedAt(summary.completedAt),
    }
  }
  const issueSummary =
    [
      nonCompliant > 0 ? `确定问题 ${nonCompliant}` : '',
      dataGap > 0 ? `待核实 ${dataGap}` : '',
      uncertain > 0 ? `待判断 ${uncertain}` : '',
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
      resultLabel: '资料待核实',
      issueSummary,
      latestQcTime: formatQcCompletedAt(summary.completedAt),
    }
  }
  if (uncertain > 0) {
    return {
      resultStatus: 'uncertain',
      resultLabel: '待判断',
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
