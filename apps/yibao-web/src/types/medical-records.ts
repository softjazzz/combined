/**
 * 医保病历管理相关类型定义
 */

// 医保病历状态
export type MedicalRecordStatus = 'pending' | 'reviewing' | 'approved' | 'rejected' | 'reimbursed'

// 医保类型
export type InsuranceType = 'basic' | 'commercial' | 'government' | 'self_pay'

// 违规风险等级
export type ViolationRiskLevel = 'low' | 'medium' | 'high' | 'critical'

// 医保病历基础信息
export interface MedicalRecord {
  id: string
  patient_name: string
  patient_age: number
  patient_gender: 'M' | 'F' | 'U'
  patient_id_card: string
  insurance_type: InsuranceType
  insurance_number: string
  department: string
  doctor_name: string
  admission_date: string
  discharge_date?: string
  record_type: 'inpatient' | 'outpatient' | 'emergency'
  diagnosis_primary: string
  diagnosis_secondary?: string[]
  total_cost: number
  insurance_cost: number
  self_pay_cost: number
  violation_risk: ViolationRiskLevel
  violation_reasons?: string[]
  content: string
  file_url?: string
  file_name?: string
  file_size?: number
  status: MedicalRecordStatus
  created_at: string
  updated_at: string
  reviewed_at?: string
  reviewer_id?: string
  reviewer_notes?: string
  hospital_id?: string
  qc_score?: number
  qc_grade?: 'A' | 'B' | 'C' | 'D'
}

// 创建医保病历请求
export interface CreateMedicalRecordRequest {
  patient_name: string
  patient_age: number
  patient_gender: 'M' | 'F' | 'U'
  patient_id_card: string
  insurance_type: InsuranceType
  insurance_number: string
  department: string
  doctor_name: string
  admission_date: string
  discharge_date?: string
  record_type: 'inpatient' | 'outpatient' | 'emergency'
  diagnosis_primary: string
  diagnosis_secondary?: string[]
  total_cost: number
  insurance_cost: number
  self_pay_cost: number
  content: string
  file?: File
}

// 医保病历统计信息
export interface MedicalRecordStats {
  totalRecords: number
  pendingReview: number
  approvedRecords: number
  rejectedRecords: number
  totalCost: number
  insuranceCost: number
  selfPayCost: number
  violationCount: number
  averageScore: number
}

// 文件上传配置
export interface FileUploadConfig {
  maxSize: number // 最大文件大小（字节）
  allowedTypes: string[] // 允许的文件类型
  maxFiles: number // 最大文件数量
}

// 上传进度
export interface UploadProgress {
  loaded: number
  total: number
  percentage: number
}

// 科室列表
export const DEPARTMENTS = [
  '心内科',
  '心外科', 
  '神经内科',
  '神经外科',
  '呼吸内科',
  '消化内科',
  '肾内科',
  '内分泌科',
  '血液科',
  '肿瘤科',
  '骨科',
  '泌尿外科',
  '妇产科',
  '儿科',
  '眼科',
  '耳鼻喉科',
  '皮肤科',
  '急诊科',
  'ICU',
  '其他'
] as const

export type Department = typeof DEPARTMENTS[number]

// 记录类型选项
export const RECORD_TYPES = [
  { value: 'inpatient', label: '住院记录' },
  { value: 'outpatient', label: '门诊记录' },
  { value: 'emergency', label: '急诊记录' }
] as const

// 医保类型选项
export const INSURANCE_TYPES = [
  { value: 'basic', label: '基本医保' },
  { value: 'commercial', label: '商业保险' },
  { value: 'government', label: '公费医疗' },
  { value: 'self_pay', label: '自费' }
] as const

// 状态选项
export const STATUS_OPTIONS = [
  { value: 'pending', label: '待审核', color: '#faad14' },
  { value: 'reviewing', label: '审核中', color: '#1890ff' },
  { value: 'approved', label: '已通过', color: '#52c41a' },
  { value: 'rejected', label: '已拒绝', color: '#f5222d' },
  { value: 'reimbursed', label: '已报销', color: '#722ed1' }
] as const

// 违规风险等级选项
export const VIOLATION_RISK_OPTIONS = [
  { value: 'low', label: '低风险', color: '#52c41a' },
  { value: 'medium', label: '中风险', color: '#faad14' },
  { value: 'high', label: '高风险', color: '#fa8c16' },
  { value: 'critical', label: '严重风险', color: '#f5222d' }
] as const

// 搜索参数
export interface SearchParams {
  keyword?: string
  status?: MedicalRecordStatus
  department?: string
  insurance_type?: InsuranceType
  violation_risk?: ViolationRiskLevel
  date_range?: [string, string]
  cost_range?: [number, number]
}

// 分页参数
export interface PaginationParams {
  page: number
  pageSize: number
  total?: number
}
