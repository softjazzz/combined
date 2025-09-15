/**
 * 医保病历管理API服务
 */
import type { 
  MedicalRecord, 
  CreateMedicalRecordRequest,
  MedicalRecordStats,
  SearchParams,
  PaginationParams
} from '@/types/medical-records'

// 模拟数据生成器
function generateMockRecord(id: number): MedicalRecord {
  const departments = ['心内科', '神经内科', '呼吸内科', '消化内科', '骨科', '妇产科', '儿科']
  const insuranceTypes = ['basic', 'commercial', 'government', 'self_pay'] as const
  const statuses = ['pending', 'reviewing', 'approved', 'rejected', 'reimbursed'] as const
  const riskLevels = ['low', 'medium', 'high', 'critical'] as const
  const genders = ['M', 'F'] as const
  
  const totalCost = Math.floor(Math.random() * 50000) + 1000
  const insuranceCost = Math.floor(totalCost * (0.6 + Math.random() * 0.3))
  const selfPayCost = totalCost - insuranceCost
  
  return {
    id: `record_${id}`,
    patient_name: `患者${id.toString().padStart(3, '0')}`,
    patient_age: Math.floor(Math.random() * 80) + 18,
    patient_gender: genders[Math.floor(Math.random() * genders.length)],
    patient_id_card: `${Math.floor(Math.random() * 900000) + 100000}19${Math.floor(Math.random() * 50) + 50}0101${Math.floor(Math.random() * 9000) + 1000}`,
    insurance_type: insuranceTypes[Math.floor(Math.random() * insuranceTypes.length)],
    insurance_number: `INS${Math.floor(Math.random() * 900000) + 100000}`,
    department: departments[Math.floor(Math.random() * departments.length)],
    doctor_name: `医生${Math.floor(Math.random() * 100) + 1}`,
    admission_date: new Date(Date.now() - Math.floor(Math.random() * 30) * 24 * 60 * 60 * 1000).toISOString().split('T')[0],
    discharge_date: Math.random() > 0.3 ? new Date(Date.now() - Math.floor(Math.random() * 10) * 24 * 60 * 60 * 1000).toISOString().split('T')[0] : undefined,
    record_type: ['inpatient', 'outpatient', 'emergency'][Math.floor(Math.random() * 3)] as any,
    diagnosis_primary: ['高血压', '糖尿病', '冠心病', '脑梗死', '肺炎', '胃炎', '骨折'][Math.floor(Math.random() * 7)],
    diagnosis_secondary: Math.random() > 0.5 ? ['高血脂', '动脉硬化'] : undefined,
    total_cost: totalCost,
    insurance_cost: insuranceCost,
    self_pay_cost: selfPayCost,
    violation_risk: riskLevels[Math.floor(Math.random() * riskLevels.length)],
    violation_reasons: Math.random() > 0.7 ? ['药品费用超标', '检查项目重复'] : undefined,
    content: `患者${id}的详细病历内容...`,
    status: statuses[Math.floor(Math.random() * statuses.length)],
    created_at: new Date(Date.now() - Math.floor(Math.random() * 30) * 24 * 60 * 60 * 1000).toISOString(),
    updated_at: new Date().toISOString(),
    qc_score: Math.floor(Math.random() * 40) + 60,
    qc_grade: ['A', 'B', 'C', 'D'][Math.floor(Math.random() * 4)] as any
  }
}

// 生成模拟数据
const mockRecords: MedicalRecord[] = Array.from({ length: 150 }, (_, i) => generateMockRecord(i + 1))

/**
 * 获取医保病历列表
 */
export async function getMedicalRecords(
  searchParams?: SearchParams,
  pagination?: PaginationParams
): Promise<{ data: MedicalRecord[], total: number }> {
  // 模拟API延迟
  await new Promise(resolve => setTimeout(resolve, 300))
  
  let filteredRecords = [...mockRecords]
  
  // 应用搜索过滤
  if (searchParams) {
    if (searchParams.keyword) {
      const keyword = searchParams.keyword.toLowerCase()
      filteredRecords = filteredRecords.filter(record => 
        record.patient_name.toLowerCase().includes(keyword) ||
        record.department.toLowerCase().includes(keyword) ||
        record.diagnosis_primary.toLowerCase().includes(keyword)
      )
    }
    
    if (searchParams.status) {
      filteredRecords = filteredRecords.filter(record => record.status === searchParams.status)
    }
    
    if (searchParams.department) {
      filteredRecords = filteredRecords.filter(record => record.department === searchParams.department)
    }
    
    if (searchParams.insurance_type) {
      filteredRecords = filteredRecords.filter(record => record.insurance_type === searchParams.insurance_type)
    }
    
    if (searchParams.violation_risk) {
      filteredRecords = filteredRecords.filter(record => record.violation_risk === searchParams.violation_risk)
    }
  }
  
  const total = filteredRecords.length
  
  // 应用分页
  if (pagination) {
    const start = (pagination.page - 1) * pagination.pageSize
    const end = start + pagination.pageSize
    filteredRecords = filteredRecords.slice(start, end)
  }
  
  return { data: filteredRecords, total }
}

/**
 * 获取医保病历详情
 */
export async function getMedicalRecordById(id: string): Promise<MedicalRecord | null> {
  await new Promise(resolve => setTimeout(resolve, 200))
  return mockRecords.find(record => record.id === id) || null
}

/**
 * 创建医保病历
 */
export async function createMedicalRecord(data: CreateMedicalRecordRequest): Promise<MedicalRecord> {
  await new Promise(resolve => setTimeout(resolve, 500))
  
  const newRecord: MedicalRecord = {
    id: `record_${Date.now()}`,
    ...data,
    violation_risk: 'low',
    status: 'pending',
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    qc_score: 85,
    qc_grade: 'B'
  }
  
  mockRecords.unshift(newRecord)
  return newRecord
}

/**
 * 更新医保病历
 */
export async function updateMedicalRecord(id: string, data: Partial<MedicalRecord>): Promise<MedicalRecord> {
  await new Promise(resolve => setTimeout(resolve, 300))
  
  const index = mockRecords.findIndex(record => record.id === id)
  if (index === -1) {
    throw new Error('记录不存在')
  }
  
  mockRecords[index] = {
    ...mockRecords[index],
    ...data,
    updated_at: new Date().toISOString()
  }
  
  return mockRecords[index]
}

/**
 * 删除医保病历
 */
export async function deleteMedicalRecord(id: string): Promise<void> {
  await new Promise(resolve => setTimeout(resolve, 200))
  
  const index = mockRecords.findIndex(record => record.id === id)
  if (index === -1) {
    throw new Error('记录不存在')
  }
  
  mockRecords.splice(index, 1)
}

/**
 * 获取医保病历统计信息
 */
export async function getMedicalRecordStats(): Promise<MedicalRecordStats> {
  await new Promise(resolve => setTimeout(resolve, 200))
  
  const totalRecords = mockRecords.length
  const pendingReview = mockRecords.filter(r => r.status === 'pending').length
  const approvedRecords = mockRecords.filter(r => r.status === 'approved').length
  const rejectedRecords = mockRecords.filter(r => r.status === 'rejected').length
  const totalCost = mockRecords.reduce((sum, r) => sum + r.total_cost, 0)
  const insuranceCost = mockRecords.reduce((sum, r) => sum + r.insurance_cost, 0)
  const selfPayCost = mockRecords.reduce((sum, r) => sum + r.self_pay_cost, 0)
  const violationCount = mockRecords.filter(r => r.violation_risk === 'high' || r.violation_risk === 'critical').length
  const averageScore = mockRecords.reduce((sum, r) => sum + (r.qc_score || 0), 0) / totalRecords
  
  return {
    totalRecords,
    pendingReview,
    approvedRecords,
    rejectedRecords,
    totalCost,
    insuranceCost,
    selfPayCost,
    violationCount,
    averageScore: Math.round(averageScore * 10) / 10
  }
}

/**
 * 批量审核医保病历
 */
export async function batchReviewRecords(ids: string[], status: 'approved' | 'rejected', notes?: string): Promise<void> {
  await new Promise(resolve => setTimeout(resolve, 1000))
  
  ids.forEach(id => {
    const index = mockRecords.findIndex(record => record.id === id)
    if (index !== -1) {
      mockRecords[index] = {
        ...mockRecords[index],
        status,
        reviewed_at: new Date().toISOString(),
        reviewer_notes: notes,
        updated_at: new Date().toISOString()
      }
    }
  })
}
