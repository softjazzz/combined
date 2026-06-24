export type WorkstationLaunchAction =
  | 'open_record'
  | 'generate_frontpage'
  | 'qc_coding'
  | 'qc_frontpage'
  | 'qc_settlement'

export interface WorkstationLaunchContext {
  record_id: string
  task_id?: string
  action: WorkstationLaunchAction
  source: 'dashboard'
  from_stage?: WorkflowStageKey
}

export type WorkflowStageKey = 'frontpage_generate' | 'coding_qc' | 'frontpage_qc' | 'settlement_qc'

export type QueueStatusCode = 'unknown' | 'pending' | 'running' | 'succeeded' | 'failed'

export type QueueStatusSource = 'backfill' | 'runtime'
