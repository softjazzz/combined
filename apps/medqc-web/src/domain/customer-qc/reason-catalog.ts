import type { CustomerQcDecisionStatus, CustomerQcDisplay } from './result-model'
import { resolveCustomerQcStatusPresentation } from './status-policy'

export interface CustomerReasonDescriptor {
  ruleId?: string
  reasonCode?: string
  status?: CustomerQcDecisionStatus
  summary: string
  detail?: string
  requirement?: string
  suggestion?: string
}

const DEFAULT_SUGGESTION = '请按质控要求补充或修正记录。'
const DATA_GAP_SUGGESTION = '请补充或同步所需数据后重新评估。'

const REASON_CATALOG: CustomerReasonDescriptor[] = [
  {
    ruleId: 'LX0609-01-01-02',
    reasonCode: 'complaint_too_long',
    summary: '主诉超过20字上限；诊断指向子结论以本次语义判断结果为准。',
    detail: '长度与能否导出第一诊断是两个独立子结论。',
    requirement: '主诉应能导出第一诊断，且主诉长度应不超过20字。',
    suggestion: '请精简主诉并保留诊断指向信息，确保与第一诊断一致。',
  },
  {
    ruleId: 'LX0609-01-01-02',
    reasonCode: 'complaint_too_short',
    summary: '该结果来自旧版主诉长度口径，请重新质控。',
    detail: '新版口径为主诉不超过20字。',
    requirement: '主诉应能导出第一诊断，且主诉长度应不超过20字。',
    suggestion: '请重新质控以获得新版口径结果。',
  },
  {
    ruleId: 'LX0609-01-01-02',
    reasonCode: 'complaint_too_short_semantic_unknown',
    summary: '该结果来自旧版主诉长度口径，请重新质控。',
    detail: '新版口径为主诉不超过20字。',
    requirement: '主诉应能导出第一诊断，且主诉长度应不超过20字。',
    suggestion: '请重新质控以获得新版口径结果。',
  },
  {
    ruleId: 'LX0609-01-01-02',
    reasonCode: 'complaint_lacks_diagnostic_clue',
    summary: '主诉仅描述症状，缺少可导出第一诊断的诊断指向信息。',
    requirement: '主诉应能导出第一诊断，且主诉长度应不超过20字。',
    suggestion: '请补充有诊断指向的主诉，并确保与第一诊断一致。',
  },
  {
    ruleId: 'LX0609-01-01-02',
    reasonCode: 'complaint_primary_diagnosis_mismatch',
    summary: '主诉及现病史不能支持首页第一诊断。',
    requirement: '主诉应能导出第一诊断，且主诉长度应不超过20字。',
    suggestion: '请补充有诊断指向的主诉，并确保与第一诊断一致。',
  },
  {
    ruleId: 'LX0609-01-01-02',
    reasonCode: 'threshold_exceeded',
    summary: '主诉规范性或其与第一诊断的对应性未通过检查。',
    requirement: '主诉应能导出第一诊断，且主诉长度应不超过20字。',
    suggestion: '请补充有诊断指向的主诉，并确保与第一诊断一致。',
  },
  {
    ruleId: 'LX0609-01-01-02',
    reasonCode: 'complaint_or_primary_diagnosis_unavailable',
    summary: '现有资料不足，暂不能判断主诉是否可导出第一诊断。',
    detail: '未取得可用于核对的主诉或第一诊断。',
    requirement: '需取得入院记录中的主诉和第一诊断后，才能完成核对。',
    suggestion: '请补充或同步入院记录主诉及第一诊断后重新评估。',
  },
  {
    ruleId: 'LX0609-04-02-04',
    reasonCode: 'implant_information_incomplete',
    summary: '手术记录中的植入物信息不完整。',
    requirement: '植入物名称、种类、规格/型号、材质和数量应记录完整。',
    suggestion: '请核对并补充手术记录中的植入物信息。',
  },
  {
    ruleId: 'LX0609-04-02-04',
    summary: '手术记录中的植入物信息不完整。',
    detail: '本次结果未提供可展示的字段级缺失项，需结合原文核对具体缺项。',
    requirement: '植入物名称、种类、规格/型号、材质和数量应记录完整。',
    suggestion: '请核对并补充手术记录中的植入物信息。',
  },
]

/**
 * 当前已具备客户安全解释合同的规则。
 * 新旧展示切换只允许在此范围内发生，避免把没有受控事实的规则硬套进新面板。
 */
export function isCustomerQcDisplayRule(ruleId: string): boolean {
  return REASON_CATALOG.some((entry) => entry.ruleId === ruleId)
}

function matches(entry: CustomerReasonDescriptor, ruleId: string, reasonCode?: string): boolean {
  return entry.ruleId === ruleId && entry.reasonCode === reasonCode
}

/**
 * 唯一允许规则特例存在的位置。Vue 层不得按规则号解释原因码。
 */
export function resolveCustomerReason(
  ruleId: string,
  reasonCode: string | undefined,
  status: CustomerQcDecisionStatus,
): CustomerReasonDescriptor {
  const exact = REASON_CATALOG.find((entry) => matches(entry, ruleId, reasonCode))
  if (exact) return exact

  if (status === 'data_gap') {
    return {
      summary: '现有受控数据不足以形成确定结论。',
      detail: '缺少完成该质控点判断所需的受控来源或字段。',
      suggestion: DATA_GAP_SUGGESTION,
    }
  }
  if (status === 'technical_error') {
    return {
      summary: '本次质控暂未完成。',
      detail: '系统未能可靠完成本项判断。',
      suggestion: DATA_GAP_SUGGESTION,
    }
  }
  if (status === 'evaluation_unknown') {
    return {
      summary: '该结果需要人工复核后确认。',
      detail: '现有证据或自动判断尚不足以形成最终结论。',
      suggestion: '请由质控人员复核后确认。',
    }
  }
  if (status === 'not_applicable') {
    return {
      summary: '本项质控不适用于当前病历。',
      suggestion: '无需处理。',
    }
  }
  if (status === 'compliant') {
    return {
      summary: '该质控点符合要求。',
      suggestion: '无需处理。',
    }
  }
  const ruleDefault = REASON_CATALOG.find((entry) => entry.ruleId === ruleId && !entry.reasonCode)
  if (ruleDefault) return ruleDefault
  return {
    summary: '发现该质控点对应的明确问题。',
    suggestion: DEFAULT_SUGGESTION,
  }
}

export function buildCustomerDisplay(
  descriptor: CustomerReasonDescriptor,
  evidenceSources: CustomerQcDisplay['evidenceSources'],
  actualValue?: string,
  status?: CustomerQcDecisionStatus,
): CustomerQcDisplay {
  const statusPresentation = resolveCustomerQcStatusPresentation(status ?? 'evaluation_unknown')
  return {
    statusLabel: statusPresentation.label,
    statusTone: statusPresentation.tone,
    summary: descriptor.summary,
    ...(descriptor.detail ? { detail: descriptor.detail } : {}),
    ...(descriptor.requirement ? { requirement: descriptor.requirement } : {}),
    ...(actualValue ? { actualValue } : {}),
    evidenceSources,
    suggestion: descriptor.suggestion ?? DEFAULT_SUGGESTION,
  }
}
