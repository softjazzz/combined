/**
 * DRG 分组结果 Mock 数据
 */

export interface DRGGrouping {
  grouping_id: number
  admission_id: string
  region: string
  adrg_code: string
  adrg_name: string
  drg_code: string
  drg_name: string
  weight: number
  baseline_payment: number
  actual_cost: number | null
  profit_margin: number | null
  grouped_at: string
  version: number
  is_latest: boolean
}

export interface CodingSuggestion {
  suggestion_id: number
  admission_id: string
  suggestion_type: 'missing_diagnosis' | 'procedure_missing' | 'complication_marking' | 'logic_conflict'
  diagnosis_code: string | null
  diagnosis_name: string | null
  message: string
  evidence: string
  severity: 'info' | 'warning' | 'error'
  status: 'pending' | 'accepted' | 'rejected'
  created_at: string
  handled_at: string | null
  handled_by: string | null
}

export interface DRGAlert {
  alert_id: number
  admission_id: string
  alert_type: 'cost_overrun' | 'los_long' | 'coding_abnormal' | 'profit_loss'
  alert_level: 'info' | 'warning' | 'critical'
  message: string
  triggered_at: string
  handled_by: string | null
  handled_at: string | null
  status: 'pending' | 'acknowledged' | 'resolved'
}

// Mock 数据：DRG 分组结果
export const mockDRGGroupings: DRGGrouping[] = [
  {
    grouping_id: 1,
    admission_id: 'ADM20250104001',
    region: 'sichuan',
    adrg_code: 'FB1',
    adrg_name: '急性心肌梗死',
    drg_code: 'FB19',
    drg_name: '急性心肌梗死伴重大合并症与伴随病',
    weight: 2.8653,
    baseline_payment: 28500.00,
    actual_cost: 58500.00,
    profit_margin: -30000.00,
    grouped_at: '2025-01-04T15:30:00Z',
    version: 1,
    is_latest: true
  },
  {
    grouping_id: 2,
    admission_id: 'ADM20250104002',
    region: 'sichuan',
    adrg_code: 'RB1',
    adrg_name: '肺炎',
    drg_code: 'RB13',
    drg_name: '肺炎伴合并症与伴随病',
    weight: 1.2341,
    baseline_payment: 12800.00,
    actual_cost: null,
    profit_margin: null,
    grouped_at: '2025-01-04T10:15:00Z',
    version: 1,
    is_latest: true
  }
]

// Mock 数据：编码建议
export const mockCodingSuggestions: CodingSuggestion[] = [
  {
    suggestion_id: 1,
    admission_id: 'ADM20250104001',
    suggestion_type: 'missing_diagnosis',
    diagnosis_code: 'I50.001',
    diagnosis_name: '心力衰竭',
    message: '病程记录中提到\'心力衰竭\'，建议补充次诊断：I50.001（心力衰竭）',
    evidence: '病程记录第3天：患者出现呼吸困难，双肺底湿啰音，考虑心力衰竭...',
    severity: 'info',
    status: 'accepted',
    created_at: '2025-01-04T14:35:00Z',
    handled_at: '2025-01-04T14:45:00Z',
    handled_by: 'CODER001'
  },
  {
    suggestion_id: 2,
    admission_id: 'ADM20250104002',
    suggestion_type: 'complication_marking',
    diagnosis_code: 'J96.001',
    diagnosis_name: '急性呼吸衰竭',
    message: '术后出现呼吸衰竭，建议标记为并发症',
    evidence: '术后第2天记录：患者出现呼吸困难，血氧饱和度下降至85%...',
    severity: 'warning',
    status: 'pending',
    created_at: '2025-01-04T11:00:00Z',
    handled_at: null,
    handled_by: null
  }
]

// Mock 数据：预警信息
export const mockDRGAlerts: DRGAlert[] = [
  {
    alert_id: 1,
    admission_id: 'ADM20250104001',
    alert_type: 'cost_overrun',
    alert_level: 'critical',
    message: '费用消耗率已达205%，超出基准支付¥30,000',
    triggered_at: '2025-01-06T10:00:00Z',
    handled_by: 'DEPT_HEAD_001',
    handled_at: '2025-01-06T11:30:00Z',
    status: 'acknowledged'
  },
  {
    alert_id: 2,
    admission_id: 'ADM20250104002',
    alert_type: 'los_long',
    alert_level: 'warning',
    message: '住院天数已达7天，预计超出标准住院日（5-6天）',
    triggered_at: '2025-01-10T08:00:00Z',
    handled_by: null,
    handled_at: null,
    status: 'pending'
  }
]

// 辅助函数：根据 admission_id 获取最新分组结果
export function getLatestGroupingByAdmissionId(admissionId: string): DRGGrouping | null {
  return mockDRGGroupings.find(
    g => g.admission_id === admissionId && g.is_latest
  ) || null
}

// 辅助函数：根据 admission_id 获取编码建议
export function getSuggestionsByAdmissionId(admissionId: string): CodingSuggestion[] {
  return mockCodingSuggestions.filter(s => s.admission_id === admissionId)
}

// 辅助函数：根据 admission_id 获取预警信息
export function getAlertsByAdmissionId(admissionId: string): DRGAlert[] {
  return mockDRGAlerts.filter(a => a.admission_id === admissionId)
}

// 辅助函数：计算费用消耗率
export function calculateCostConsumptionRate(grouping: DRGGrouping): number | null {
  if (!grouping.actual_cost || !grouping.baseline_payment) return null
  return (grouping.actual_cost / grouping.baseline_payment) * 100
}
