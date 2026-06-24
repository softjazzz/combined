import type { QueueStatusCode, WorkstationLaunchAction, WorkflowStageKey } from '@/types/workflow'
import type { WorkstationWorklistItem } from './types'

export type StageStatusWorkflow = WorkstationWorklistItem['workflowType'] | 'frontpage_generate'

export const QUEUE_STATUS_LABEL_MAP: Record<
  StageStatusWorkflow,
  Record<QueueStatusCode, string>
> = {
  frontpage_generate: {
    unknown: '状态未知',
    pending: '待生成',
    running: '生成中',
    succeeded: '已生成',
    failed: '生成失败',
  },
  frontpage: {
    unknown: '状态未知',
    pending: '待首页质控',
    running: '质控中',
    succeeded: '质控完成',
    failed: '质控失败',
  },
  coding: {
    unknown: '状态未知',
    pending: '待编码质控',
    running: '质控中',
    succeeded: '质控完成',
    failed: '质控失败',
  },
  settlement: {
    unknown: '状态未知',
    pending: '待结算清单质控',
    running: '质控中',
    succeeded: '质控完成',
    failed: '质控失败',
  },
}

export const aggregatedStageWorkflows: Record<string, WorkstationWorklistItem['workflowType']> = {
  coding_qc: 'coding',
  frontpage_qc: 'frontpage',
  settlement_qc: 'settlement',
}

export const workflowLabelMap: Record<WorkstationWorklistItem['workflowType'], string> = {
  frontpage: '首页质控',
  coding: '编码质控',
  settlement: '结算清单质控',
}

export function getStageMeta(currentStageFilter: WorkflowStageKey | '') {
  if (currentStageFilter === 'frontpage_generate') {
    return {
      pageTitle: '参考首页生成队列',
      pageDesc: '面向医生与病案科的参考草稿，不写入正式首页数据表。',
      tableTitle: '待生成首页（参考草稿）',
      tableDesc: '口径：有住院记录即可进入；与正式首页数据表无关。',
      batchActionText: '批量生成参考首页',
      singleActionText: '查看首页',
      action: 'generate_frontpage' as WorkstationLaunchAction,
    }
  }
  if (currentStageFilter === 'coding_qc') {
    return {
      pageTitle: '编码质控队列',
      pageDesc: '针对主诊断、其他诊断与手术编码执行规则和一致性质控。',
      tableTitle: '待编码质控',
      tableDesc: '口径：正式首页数据存在即可进入编码质控队列。',
      batchActionText: '批量编码质控',
      singleActionText: '进入编码质控',
      action: 'qc_coding' as WorkstationLaunchAction,
    }
  }
  if (currentStageFilter === 'frontpage_qc') {
    return {
      pageTitle: '正式首页质控队列',
      pageDesc: '仅针对正式首页数据表执行质控，与草稿生成结果解耦。',
      tableTitle: '待首页质控（正式数据）',
      tableDesc: '口径：正式首页数据表存在即可进入。',
      batchActionText: '批量首页质控',
      singleActionText: '进入首页质控',
      action: 'qc_frontpage' as WorkstationLaunchAction,
    }
  }
  if (currentStageFilter === 'settlement_qc') {
    return {
      pageTitle: '正式结算清单质控队列',
      pageDesc: '仅针对正式结算清单数据执行质控，与首页草稿无关。',
      tableTitle: '待结算清单质控（正式数据）',
      tableDesc: '口径：正式结算清单数据表存在即可进入。',
      batchActionText: '批量结算质控',
      singleActionText: '进入结算质控',
      action: 'qc_settlement' as WorkstationLaunchAction,
    }
  }
  return {
    pageTitle: '病案工作台',
    pageDesc: '先筛高优先病历，再进入单案详情。',
    tableTitle: '批量扫读',
    tableDesc: '按当前筛选条件展示病历列表。',
    batchActionText: '批量处理',
    singleActionText: '查看详情',
    action: 'open_record' as WorkstationLaunchAction,
  }
}
