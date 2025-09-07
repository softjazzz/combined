// 运行病历相关API服务

import type { 
  QueryConditions, 
  FilterConditions, 
  MedicalRecord, 
  DefectRecord, 
  FilterTemplate,
  BatchOperationResult,
  ExportParams,
  ListResponse,
  ApiResponse
} from '@/types/running-records'

// 模拟API基础URL
const API_BASE_URL = '/api/running-records'

// 模拟延迟函数
const delay = (ms: number) => new Promise(resolve => setTimeout(resolve, ms))

// 模拟数据
const mockRecords: MedicalRecord[] = [
  {
    id: '1',
    registrationNo: '2024001234',
    serialNo: '20240101001',
    caseNo: 'A001234567',
    patientName: '张三',
    department: '内科',
    doctor: '李医生',
    auditStatus: 'pending',
    score: 85.5,
    scoringStandard: '标准评分1',
    defectCount: 2,
    createTime: '2024-01-15 10:30:00',
    updateTime: '2024-01-15 14:20:00',
    isUrgent: false
  },
  {
    id: '2',
    registrationNo: '2024001235',
    serialNo: '20240101002',
    caseNo: 'A001234568',
    patientName: '李四',
    department: '外科',
    doctor: '王医生',
    auditStatus: 'reviewing',
    score: 92.0,
    scoringStandard: '标准评分2',
    defectCount: 1,
    createTime: '2024-01-15 11:00:00',
    updateTime: '2024-01-15 15:30:00',
    isUrgent: true
  },
  {
    id: '3',
    registrationNo: '2024001236',
    serialNo: '20240101003',
    caseNo: 'A001234569',
    patientName: '王五',
    department: '儿科',
    doctor: '赵医生',
    auditStatus: 'passed',
    score: 96.5,
    scoringStandard: '标准评分1',
    defectCount: 0,
    createTime: '2024-01-15 12:00:00',
    updateTime: '2024-01-15 16:00:00',
    isUrgent: false
  }
]

const mockDefects: DefectRecord[] = [
  {
    id: '1',
    registrationNo: '2024001234',
    serialNo: '20240101001',
    caseNo: 'A001234567',
    patientName: '张三',
    department: '内科',
    doctor: '李医生',
    defectType: '诊断不完整',
    defectDescription: '主要诊断缺少具体分型',
    defectStatus: 'pending',
    priority: 'high',
    createTime: '2024-01-15 10:30:00',
    updateTime: '2024-01-15 14:20:00',
    score: 85.5,
    scoringStandard: '标准评分1'
  },
  {
    id: '2',
    registrationNo: '2024001235',
    serialNo: '20240101002',
    caseNo: 'A001234568',
    patientName: '李四',
    department: '外科',
    doctor: '王医生',
    defectType: '用药记录',
    defectDescription: '抗生素使用未记录过敏史',
    defectStatus: 'rectified',
    priority: 'medium',
    createTime: '2024-01-15 11:00:00',
    updateTime: '2024-01-15 15:30:00',
    score: 92.0,
    scoringStandard: '标准评分2'
  }
]

// 查询病历列表
export const queryRecords = async (
  conditions: QueryConditions & FilterConditions,
  page: number = 1,
  pageSize: number = 10
): Promise<ApiResponse<ListResponse<MedicalRecord>>> => {
  await delay(800) // 模拟网络延迟
  
  // 模拟筛选逻辑
  let filteredRecords = [...mockRecords]
  
  // 根据查询条件筛选
  if (conditions.searchValue && conditions.searchType) {
    filteredRecords = filteredRecords.filter(record => {
      const value = record[conditions.searchType as keyof MedicalRecord]
      return String(value).toLowerCase().includes(conditions.searchValue.toLowerCase())
    })
  }
  
  // 根据审核状态筛选
  if (conditions.auditStatus && conditions.auditStatus.length > 0) {
    filteredRecords = filteredRecords.filter(record => 
      conditions.auditStatus!.includes(record.auditStatus)
    )
  }
  
  // 根据科室筛选
  if (conditions.department && conditions.department.length > 0) {
    filteredRecords = filteredRecords.filter(record => 
      conditions.department!.includes(record.department)
    )
  }
  
  // 分页
  const total = filteredRecords.length
  const start = (page - 1) * pageSize
  const end = start + pageSize
  const list = filteredRecords.slice(start, end)
  
  return {
    code: 200,
    message: 'success',
    success: true,
    data: {
      list,
      pagination: {
        current: page,
        pageSize,
        total
      }
    }
  }
}

// 查询缺陷列表
export const queryDefects = async (
  conditions: QueryConditions & FilterConditions,
  page: number = 1,
  pageSize: number = 10
): Promise<ApiResponse<ListResponse<DefectRecord>>> => {
  await delay(800)
  
  let filteredDefects = [...mockDefects]
  
  // 根据查询条件筛选
  if (conditions.searchValue && conditions.searchType) {
    filteredDefects = filteredDefects.filter(defect => {
      const value = defect[conditions.searchType as keyof DefectRecord]
      return String(value).toLowerCase().includes(conditions.searchValue.toLowerCase())
    })
  }
  
  // 根据缺陷状态筛选
  if (conditions.defectStatus && conditions.defectStatus.length > 0) {
    filteredDefects = filteredDefects.filter(defect => 
      conditions.defectStatus!.includes(defect.defectStatus)
    )
  }
  
  // 根据优先级筛选
  if (conditions.priority && conditions.priority.length > 0) {
    filteredDefects = filteredDefects.filter(defect => 
      conditions.priority!.includes(defect.priority)
    )
  }
  
  const total = filteredDefects.length
  const start = (page - 1) * pageSize
  const end = start + pageSize
  const list = filteredDefects.slice(start, end)
  
  return {
    code: 200,
    message: 'success',
    success: true,
    data: {
      list,
      pagination: {
        current: page,
        pageSize,
        total
      }
    }
  }
}

// 批量催办
export const batchUrge = async (ids: string[]): Promise<ApiResponse<BatchOperationResult>> => {
  await delay(1500)
  
  // 模拟部分失败的情况
  const failedItems = ids.length > 5 ? [
    { id: ids[0], reason: '该记录已被催办' }
  ] : []
  
  return {
    code: 200,
    message: 'success',
    success: true,
    data: {
      total: ids.length,
      success: ids.length - failedItems.length,
      failed: failedItems.length,
      failedItems
    }
  }
}

// 批量重新质控
export const batchRecheck = async (ids: string[]): Promise<ApiResponse<BatchOperationResult>> => {
  await delay(2000)
  
  return {
    code: 200,
    message: 'success',
    success: true,
    data: {
      total: ids.length,
      success: ids.length,
      failed: 0,
      failedItems: []
    }
  }
}

// 批量通过
export const batchPass = async (ids: string[]): Promise<ApiResponse<BatchOperationResult>> => {
  await delay(1200)
  
  return {
    code: 200,
    message: 'success',
    success: true,
    data: {
      total: ids.length,
      success: ids.length,
      failed: 0,
      failedItems: []
    }
  }
}

// 导出数据
export const exportData = async (params: ExportParams): Promise<ApiResponse<{ downloadUrl: string }>> => {
  await delay(2000)
  
  // 模拟生成下载链接
  const downloadUrl = `/api/download/export_${params.type}_${Date.now()}.xlsx`
  
  return {
    code: 200,
    message: 'success',
    success: true,
    data: {
      downloadUrl
    }
  }
}

// 获取筛选模板
export const getFilterTemplates = async (): Promise<ApiResponse<FilterTemplate[]>> => {
  await delay(300)
  
  const templates: FilterTemplate[] = [
    {
      id: '1',
      name: '待审核病历',
      conditions: { auditStatus: ['pending'] },
      createTime: '2024-01-10 10:00:00',
      updateTime: '2024-01-10 10:00:00'
    },
    {
      id: '2',
      name: '高优先级缺陷',
      conditions: { priority: ['high'] },
      createTime: '2024-01-10 11:00:00',
      updateTime: '2024-01-10 11:00:00'
    },
    {
      id: '3',
      name: '本周新增',
      conditions: { timeRange: 'recent7' },
      createTime: '2024-01-10 12:00:00',
      updateTime: '2024-01-10 12:00:00'
    }
  ]
  
  return {
    code: 200,
    message: 'success',
    success: true,
    data: templates
  }
}

// 保存筛选模板
export const saveFilterTemplate = async (
  name: string, 
  conditions: FilterConditions
): Promise<ApiResponse<FilterTemplate>> => {
  await delay(500)
  
  const template: FilterTemplate = {
    id: Date.now().toString(),
    name,
    conditions,
    createTime: new Date().toLocaleString(),
    updateTime: new Date().toLocaleString()
  }
  
  return {
    code: 200,
    message: 'success',
    success: true,
    data: template
  }
}

// 获取病历详情
export const getRecordDetail = async (id: string): Promise<ApiResponse<any>> => {
  await delay(600)
  
  const record = mockRecords.find(r => r.id === id)
  if (!record) {
    return {
      code: 404,
      message: '记录不存在',
      success: false,
      data: null
    }
  }
  
  return {
    code: 200,
    message: 'success',
    success: true,
    data: {
      ...record,
      defects: mockDefects.filter(d => d.registrationNo === record.registrationNo),
      documents: [
        {
          id: '1',
          name: '入院记录',
          type: 'admission',
          content: '<p>患者因"胸痛3小时"入院...</p>',
          defects: []
        }
      ],
      operationHistory: [
        {
          id: '1',
          type: 'audit',
          operator: '质控医生A',
          operateTime: '2024-01-15 14:30:00',
          description: '进行质控审核',
          result: '发现缺陷'
        }
      ]
    }
  }
}
