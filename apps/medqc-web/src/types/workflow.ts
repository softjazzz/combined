export type WorkstationLaunchAction =
  | 'open_record'
  | 'generate_frontpage'
  | 'qc_frontpage'
  | 'qc_settlement'

export interface WorkstationLaunchContext {
  record_id: string
  task_id?: string
  action: WorkstationLaunchAction
  source: 'dashboard'
  from_stage?: WorkflowStageKey
}

export type WorkflowStageKey =
  | 'frontpage_generate'
  | 'frontpage_qc'
  | 'settlement_qc'

