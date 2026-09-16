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

/**
 * `not_applicable` 三个互斥出口的客户文案（012/015 多事件卡片）。
 *
 * 真值源在后端 `backend/app/services/luxian_0609/customer_renderer.py`
 * 的多事件 `not_applicable` 分支（`conclusion = "..."`）。此处逐字复制用于前端渲染，
 * 并由 `__tests__/examLabEventPresentation.spec.ts` 的跨端一致性断言守护：
 * 任一端改字，测试即失败。
 */
export const NOT_APPLICABLE_WINDOW_NOT_MATURE_TEXT = '报告后 24 小时评价窗口尚未届满，暂不判定'
export const NOT_APPLICABLE_NEGATIVE_TEXT = '按报告结果判定为未检出需分析的阳性结果，本项不适用'
export const NOT_APPLICABLE_UNKNOWN_TEXT = '未确认本次检查为需分析的目标事件，本项不适用'

export function buildExamLabEventPresentation(
  item: SingleRecordQcResultItem,
): ExamLabEventPresentation | null {
  const analysisRule = ['LX0609-012', 'LX0609-015'].includes(item.rule_id)
  const recordingRule = ['LX0609-011', 'LX0609-014'].includes(item.rule_id)
  if (!analysisRule && !recordingRule) return null
  const facts = item.customer_display_facts
  const expectedRequirement = analysisRule
    ? 'positive_result_analysis_within_24h'
    : 'result_recording_within_24h'
  if (
    facts?.requirement !== expectedRequirement ||
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
      (analysisRule &&
        positiveState !== 'positive' &&
        positiveState !== 'negative' &&
        positiveState !== 'unknown') ||
      (recordingRule && positiveState !== 'not_relevant') ||
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
    const responseRecordTime =
      typeof event.response_record_time === 'string' ? event.response_record_time : ''
    const intervalHours =
      typeof event.interval_hours === 'number' && Number.isFinite(event.interval_hours)
        ? event.interval_hours
        : null
    if (recordingRule) {
      if (eventStatus === 'compliant') {
        const timing =
          responseRecordTime && intervalHours !== null
            ? `；最早相关病程 ${responseRecordTime}，间隔 ${intervalHours} 小时`
            : ''
        events.push({
          eventPosition,
          reportTime,
          positive: false,
          eventStatus,
          tone: 'success',
          statusLabel: '已记录',
          description: `已完成报告结果记录${timing}`,
        })
        continue
      }
      if (eventStatus === 'non_compliant') {
        events.push({
          eventPosition,
          reportTime,
          positive: false,
          eventStatus,
          tone: 'danger',
          statusLabel: '未记录',
          description: '报告后 24 小时内未找到报告结果记录',
        })
        continue
      }
      events.push({
        eventPosition,
        reportTime,
        positive: false,
        eventStatus,
        tone: eventStatus === 'not_applicable' ? 'neutral' : 'warning',
        statusLabel: eventStatus === 'not_applicable' ? '不适用' : '待核实',
        description:
          eventStatus === 'not_applicable'
            ? '本次事件不适用'
            : '资料待核实，暂无法确认报告结果是否已记录',
      })
      continue
    }
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
            ? NOT_APPLICABLE_WINDOW_NOT_MATURE_TEXT
            : positiveState === 'negative'
              ? NOT_APPLICABLE_NEGATIVE_TEXT
              : NOT_APPLICABLE_UNKNOWN_TEXT,
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
  const completedCount = events.filter((event) => event.eventStatus === 'compliant').length
  return {
    headline: recordingRule
      ? `共核对 ${events.length} 次 ${subject} 检查；${completedCount} 次已记录，${issueCount} 次未在 24 小时内记录。`
      : `共核对 ${events.length} 次 ${subject} 检查；${positiveCount} 次阳性结果中，${issueCount} 次未在 24 小时内完成分析。`,
    totalLabel: `检查 ${events.length} 次`,
    positiveLabel: recordingRule ? `已记录 ${completedCount} 次` : `阳性 ${positiveCount} 次`,
    issueLabel: recordingRule ? `未记录 ${issueCount} 次` : `未完成分析 ${issueCount} 次`,
    events,
  }
}
