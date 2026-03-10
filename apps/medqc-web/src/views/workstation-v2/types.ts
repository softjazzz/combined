export interface PatientRecord {
  id: string
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
  diagnosis: string
  diagnosisCode: string
  doctor: string
  status: 'pending' | 'processing' | 'completed' | 'warning'
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
  category?: 'form' | 'coding' | 'cost' | string
  group?: string
  description?: string
  suggestion?: string
  evidence?: string
}
