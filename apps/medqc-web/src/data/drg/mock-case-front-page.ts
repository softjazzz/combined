/**
 * DRG 病案首页 Mock 数据
 * 用于前端开发阶段的快速原型验证
 */

export interface CaseFrontPage {
  front_page_id: number
  admission_id: string
  patient_id: string

  // 患者基本信息
  patient_name: string
  patient_age: number
  patient_gender: 'M' | 'F'
  admission_weight: number | null

  // 主诊断
  primary_diagnosis_code: string
  primary_diagnosis_name: string

  // 主要手术操作
  main_procedure_code: string | null
  main_procedure_name: string | null
  main_procedure_date: string | null

  // 其他信息
  admission_route: string
  discharge_status: string
  total_hospital_days: number | null
  total_cost: number

  // 编码工作追踪
  coder_id: string | null
  coding_started_at: string | null
  coding_completed_at: string | null
  coding_status: 'draft' | 'completed' | 'reviewed'

  // 审核追踪
  reviewer_id: string | null
  reviewed_at: string | null
  review_status: 'pending' | 'approved' | 'rejected'

  // 审计
  created_at: string
  updated_at: string
}

export interface CaseFrontPageDiagnosis {
  id: number
  front_page_id: number
  diagnosis_code: string
  diagnosis_name: string
  sequence: number
  is_complication: boolean
  created_at: string
}

export interface CaseFrontPageProcedure {
  id: number
  front_page_id: number
  procedure_code: string
  procedure_name: string
  procedure_date: string
  sequence: number
  created_at: string
}

// Mock 数据：病案首页
export const mockCaseFrontPages: CaseFrontPage[] = [
  {
    front_page_id: 1,
    admission_id: 'ADM20250104001',
    patient_id: 'P123456',

    patient_name: '张三',
    patient_age: 65,
    patient_gender: 'M',
    admission_weight: null,

    primary_diagnosis_code: 'I21.001',
    primary_diagnosis_name: '急性前壁ST段抬高型心肌梗死',

    main_procedure_code: '36.0700',
    main_procedure_name: '经皮冠状动脉介入术',
    main_procedure_date: '2025-01-05T10:30:00Z',

    admission_route: '急诊',
    discharge_status: '治愈',
    total_hospital_days: 12,
    total_cost: 58500.00,

    coder_id: 'CODER001',
    coding_started_at: '2025-01-04T14:00:00Z',
    coding_completed_at: '2025-01-04T15:30:00Z',
    coding_status: 'completed',

    reviewer_id: 'REVIEWER001',
    reviewed_at: '2025-01-04T16:00:00Z',
    review_status: 'approved',

    created_at: '2025-01-04T09:00:00Z',
    updated_at: '2025-01-04T16:00:00Z'
  },
  {
    front_page_id: 2,
    admission_id: 'ADM20250104002',
    patient_id: 'P123457',

    patient_name: '李四',
    patient_age: 48,
    patient_gender: 'F',
    admission_weight: null,

    primary_diagnosis_code: 'J18.901',
    primary_diagnosis_name: '肺炎，未特指病原体',

    main_procedure_code: null,
    main_procedure_name: null,
    main_procedure_date: null,

    admission_route: '门诊',
    discharge_status: '好转',
    total_hospital_days: 7,
    total_cost: 12800.00,

    coder_id: 'CODER002',
    coding_started_at: '2025-01-04T10:00:00Z',
    coding_completed_at: null,
    coding_status: 'draft',

    reviewer_id: null,
    reviewed_at: null,
    review_status: 'pending',

    created_at: '2025-01-04T09:30:00Z',
    updated_at: '2025-01-04T10:15:00Z'
  }
]

// Mock 数据：次诊断
export const mockCaseFrontPageDiagnoses: CaseFrontPageDiagnosis[] = [
  {
    id: 1,
    front_page_id: 1,
    diagnosis_code: 'I10.x01',
    diagnosis_name: '高血压3级（极高危）',
    sequence: 1,
    is_complication: false,
    created_at: '2025-01-04T14:30:00Z'
  },
  {
    id: 2,
    front_page_id: 1,
    diagnosis_code: 'E11.901',
    diagnosis_name: '2型糖尿病',
    sequence: 2,
    is_complication: false,
    created_at: '2025-01-04T14:30:00Z'
  },
  {
    id: 3,
    front_page_id: 1,
    diagnosis_code: 'I50.001',
    diagnosis_name: '心力衰竭',
    sequence: 3,
    is_complication: true,
    created_at: '2025-01-04T14:45:00Z'
  },
  {
    id: 4,
    front_page_id: 2,
    diagnosis_code: 'J44.101',
    diagnosis_name: '慢性阻塞性肺疾病伴急性下呼吸道感染',
    sequence: 1,
    is_complication: false,
    created_at: '2025-01-04T10:15:00Z'
  }
]

// Mock 数据：手术操作
export const mockCaseFrontPageProcedures: CaseFrontPageProcedure[] = [
  {
    id: 1,
    front_page_id: 1,
    procedure_code: '37.6100',
    procedure_name: '主动脉内球囊反搏（IABP）',
    procedure_date: '2025-01-05T12:00:00Z',
    sequence: 1,
    created_at: '2025-01-04T14:50:00Z'
  }
]

// 辅助函数：根据 front_page_id 获取次诊断
export function getDiagnosesByFrontPageId(frontPageId: number): CaseFrontPageDiagnosis[] {
  return mockCaseFrontPageDiagnoses.filter(d => d.front_page_id === frontPageId)
}

// 辅助函数：根据 front_page_id 获取手术操作
export function getProceduresByFrontPageId(frontPageId: number): CaseFrontPageProcedure[] {
  return mockCaseFrontPageProcedures.filter(p => p.front_page_id === frontPageId)
}

// 辅助函数：根据 admission_id 获取完整病案首页数据
export function getCaseFrontPageByAdmissionId(admissionId: string) {
  const frontPage = mockCaseFrontPages.find(fp => fp.admission_id === admissionId)
  if (!frontPage) return null

  return {
    ...frontPage,
    diagnoses: getDiagnosesByFrontPageId(frontPage.front_page_id),
    procedures: getProceduresByFrontPageId(frontPage.front_page_id)
  }
}
