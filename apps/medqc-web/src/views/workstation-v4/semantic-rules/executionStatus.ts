import type { SemanticRuleItem } from './types'

/** 仅投影总表状态，不据规则编号推断执行资格。 */
export function executionStatus(rule: SemanticRuleItem): string {
  if (rule.phase_status === 'pending_definition') return '暂停'
  if (rule.release_scope === 'acceptance_only') return '仅供验证'
  if (rule.release_scope === 'default') {
    if (rule.phase_status === 'phase_1_partial') return '部分启用'
    if (rule.phase_status === 'phase_1_target') return '默认启用'
  }
  return '状态未提供'
}

export function executionStatusHint(rule: SemanticRuleItem): string {
  const state = executionStatus(rule)
  if (state === '暂停') return rule.pending_definition_note || '不参与正式判定'
  if (state === '仅供验证') return '不参与默认质控，仅支持客户样本显式验证'
  if (state === '部分启用') return '仅执行已确认的部分检查内容'
  return state === '默认启用' ? '纳入新建默认质控任务，适用性仍按病例判断' : '接口未提供执行状态'
}
