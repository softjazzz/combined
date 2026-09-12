import type { SingleRecordQcResultItem } from './single-record-result-model'

export type ExamEventTone = 'danger' | 'success' | 'warning' | 'neutral'

export interface ExamEventPresentationRow {
  eventPosition: number
  reportTime: string
  positive: boolean
  eventStatus: string
  tone: ExamEventTone
  statusLabel: string
  description: string
}

export interface ExamLabEventPresentation {
  headline: string
  totalLabel: string
  positiveLabel: string
  issueLabel: string
  events: ExamEventPresentationRow[]
}

export function buildExamLabEventPresentation(
  item: SingleRecordQcResultItem,
): ExamLabEventPresentation | null {
  if (!['LX0609-012', 'LX0609-015'].includes(item.rule_id)) return null
  const facts = item.customer_display_facts
  if (
    facts?.requirement !== 'positive_result_analysis_within_24h' ||
    (facts.subject !== 'ct_mri' && facts.subject !== 'culture_susceptibility') ||
    facts.threshold_hours !== 24 ||
    !Array.isArray(facts.event_results) ||
    !facts.event_results.length ||
    facts.event_results.length > 50 ||
    facts.event_count !== facts.event_results.length
  ) {
    return null
  }

  const events: ExamEventPresentationRow[] = []
  for (const [index, candidate] of facts.event_results.entries()) {
    if (!candidate || typeof candidate !== 'object' || Array.isArray(candidate)) return null
    const event = candidate as Record<string, unknown>
    const eventPosition = event.event_position
    const reportTime = event.report_time
    const positiveState = event.positive_state
    const eventStatus = typeof event.event_status === 'string' ? event.event_status : ''
    const responseRecordCount = event.response_record_count
    if (
      eventPosition !== index + 1 ||
      typeof reportTime !== 'string' ||
      !/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$/.test(reportTime) ||
      (positiveState !== 'positive' &&
        positiveState !== 'negative' &&
        positiveState !== 'unknown') ||
      ![
        'non_compliant',
        'compliant',
        'not_applicable',
        'data_gap',
        'evaluation_unknown',
        'uncertain',
        'technical_error',
      ].includes(eventStatus) ||
      !Number.isInteger(responseRecordCount) ||
      Number(responseRecordCount) < 0
    ) {
      return null
    }

    const positive = positiveState === 'positive'
    if (eventStatus === 'not_applicable') {
      events.push({
        eventPosition,
        reportTime,
        positive,
        eventStatus,
        tone: 'neutral',
        statusLabel: '不适用',
        description:
          positiveState === 'positive'
            ? '报告后 24 小时评价窗口尚未届满，暂不判定'
            : positiveState === 'negative'
              ? '按报告结果判定为未检出需分析的阳性结果，本项不适用'
              : '未确认本次检查为需分析的目标事件，本项不适用',
      })
      continue
    }
    if (eventStatus === 'non_compliant') {
      events.push({
        eventPosition,
        reportTime,
        positive,
        eventStatus,
        tone: 'danger',
        statusLabel: '未完成分析',
        description: '阳性结果未在 24 小时内找到临床分析记录',
      })
      continue
    }
    if (eventStatus === 'compliant') {
      events.push({
        eventPosition,
        reportTime,
        positive,
        eventStatus,
        tone: 'success',
        statusLabel: '已完成分析',
        description: `阳性结果已找到 ${responseRecordCount} 条临床分析记录`,
      })
      continue
    }
    events.push({
      eventPosition,
      reportTime,
      positive,
      eventStatus,
      tone: 'warning',
      statusLabel: '待核实',
      description: '当前资料不足，暂无法完成分析记录核对',
    })
  }

  const subject = facts.subject === 'ct_mri' ? 'CT/MRI' : '细菌培养及药敏'
  const positiveCount = events.filter((event) => event.positive).length
  const issueCount = events.filter((event) => event.eventStatus === 'non_compliant').length
  return {
    headline: `共核对 ${events.length} 次 ${subject} 检查；${positiveCount} 次阳性结果中，${issueCount} 次未在 24 小时内完成分析。`,
    totalLabel: `检查 ${events.length} 次`,
    positiveLabel: `阳性 ${positiveCount} 次`,
    issueLabel: `未完成分析 ${issueCount} 次`,
    events,
  }
}
