/**
 * 医疗记录相关类型定义
 */

// 医疗记录状态
export type MedicalRecordStatus = 'pending' | 'analyzing' | 'completed' | 'failed'

// 医疗记录基础信息
export interface MedicalRecord {
  id: string
  patient_name: string
  patient_age: number
  patient_gender: 'M' | 'F' | 'U'
  department: string
  admission_date: string
  record_type: 'inpatient' | 'outpatient' | 'emergency'
  content: string
  file_url?: string
  file_name?: string
  file_size?: number
  status: MedicalRecordStatus
  created_at: string
  updated_at: string
  hospital_id?: string
  doctor_id?: string
  qc_score?: number
  qc_grade?: 'A' | 'B' | 'C'
}

// 创建医疗记录请求
export interface CreateMedicalRecordRequest {
  patient_name: string
  patient_age: number
  patient_gender: 'M' | 'F' | 'U'
  department: string
  admission_date: string
  record_type: 'inpatient' | 'outpatient' | 'emergency'
  content: string
  file?: File
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