export interface PatientRecord {
  id: string
  visitId?: string
  instituteId?: string
  patientId?: string
  bedNo: string
  name: string
  sex: string
  age: number
  insurance: string
  department: string
  admissionDate: string
  dischargeDate: string
  days: number
  cdmFrontpageEmpty?: boolean
  hasAdmission?: boolean
  hasFrontpageDraft?: boolean
  frontpageDraftUpdatedAt?: string
  hasFrontpageOfficial?: boolean
  hasSettlementOfficial?: boolean
  diagnosis: string
  diagnosisCode: string
  doctor: string
  status: 'pending' | 'processing' | 'completed' | 'warning' | 'has_defects'
}

export interface DeptInfo {
  name: string
  total: number
  warningCount: number
}

export interface DocItem {
  type: string
  label: string
  has_content: boolean
  content: string | null
  length: number
}

export type FrontpageFocusTarget = 'basic' | 'admission' | 'diagnosis' | 'procedure'

export type IcdApplyTarget = 'mainDiagnosis' | 'otherDiagnosis' | 'mainProcedure' | 'otherProcedure'

export interface QCIssueLike {
  id?: string
  record_id?: string
  category?: 'form' | 'coding' | 'cost' | string
  group?: string
  status?: string
  severity?: string
  rule_name?: string
  description?: string
  suggestion?: string
  evidence?: string
  dismissed?: boolean
}

export interface NotificationVM {
  id: string
  record_id: string
  title: string
  content: string
  message: string
  created_at: string
  is_read: boolean
  level?: string
  type?: string
}
