/**
 * Mock 数据服务
 * 用于前端开发阶段，模拟后端 API 响应
 */

import type { LoginRequest } from '@/types'

interface MockUser {
  id: string
  email: string
  password: string
  full_name: string
  role: string
  department_id: string
  department_name: string
  avatar_url: string
  phone: string
  created_at: string
  last_login: string
}

interface MockLoginResponse {
  user: {
    id: string
    email: string
    full_name: string
    role: string
    department_id: string
    avatar_url: string
  }
  tokens: {
    access_token: string
    refresh_token: string
    expires_in: number
  }
}

interface MockUserProfile {
  id: string
  email: string
  full_name: string
  role: string
  department_id: string
  department_name: string
  avatar_url: string
  phone: string
  created_at: string
  last_login: string
}

interface MockMedicalRecord {
  id: string
  record_number: string
  patient_name: string
  patient_id: string
  admission_date: string
  discharge_date: string | null
  department_id: string
  department_name: string
  doctor_id: string
  doctor_name: string
  diagnosis_primary: string
  diagnosis_secondary: string[]
  status: 'draft' | 'completed' | 'archived' | 'pending'
  qc_status: string | null
  qc_score: number | null
  qc_grade: 'A' | 'B' | 'C' | null
  created_at: string
  updated_at: string
}

interface MockQCIssue {
  id: string
  rule_id: string
  rule_name: string
  severity: 'minor' | 'major' | 'critical'
  category: string
  description: string
  location: string
  suggestion: string
}

interface MockQCSuggestion {
  id: string
  category: string
  title: string
  description: string
  priority: 'low' | 'medium' | 'high'
}

interface MockQCRuleResult {
  rule_id: string
  rule_name: string
  passed: boolean
  score: number
  details: string
}

interface MockQCResult {
  id: string
  record_id: string
  overall_score: number
  overall_grade: 'A' | 'B' | 'C' | 'D'
  analysis_date: string
  issues: MockQCIssue[]
  suggestions: MockQCSuggestion[]
  rule_results: MockQCRuleResult[]
}

interface MockSearchResult {
  record_id: string
  record_number: string
  patient_name: string
  diagnosis_primary: string
  content_snippet: string
  similarity_score: number
  highlight: string[]
}

interface MockDashboardData {
  summary: {
    total_records: number
    completed_records: number
    avg_qc_score: number
    grade_distribution: Record<string, number>
  }
  trends: Array<{
    date: string
    records_count: number
    avg_score: number
  }>
  department_stats: Array<{
    department_id: string
    department_name: string
    records_count: number
    avg_score: number
    grade_a_rate: number
  }>
}

const delay = (ms: number = 500) => new Promise(resolve => setTimeout(resolve, ms))

const mockUsers: MockUser[] = [
  {
    id: '1',
    email: 'admin@medqc.com',
    password: 'admin123',
    full_name: '系统管理员',
    role: 'admin',
    department_id: '1',
    department_name: '信息科',
    avatar_url: 'https://api.dicebear.com/7.x/avataaars/svg?seed=admin',
    phone: '13800138001',
    created_at: '2024-01-01T00:00:00Z',
    last_login: '2024-12-25T09:00:00Z'
  },
  {
    id: '2',
    email: 'doctor@medqc.com',
    password: 'doctor123',
    full_name: '张医生',
    role: 'doctor',
    department_id: '2',
    department_name: '内科',
    avatar_url: 'https://api.dicebear.com/7.x/avataaars/svg?seed=doctor',
    phone: '13800138002',
    created_at: '2024-01-01T00:00:00Z',
    last_login: '2024-12-25T08:30:00Z'
  },
  {
    id: '3',
    email: 'qc@medqc.com',
    password: 'qc123',
    full_name: '李质控',
    role: 'qc_manager',
    department_id: '3',
    department_name: '质控科',
    avatar_url: 'https://api.dicebear.com/7.x/avataaars/svg?seed=qc',
    phone: '13800138003',
    created_at: '2024-01-01T00:00:00Z',
    last_login: '2024-12-25T08:45:00Z'
  }
]

const mockRecords: MockMedicalRecord[] = [
  {
    id: '1',
    record_number: 'MR20241225001',
    patient_name: '王小明',
    patient_id: 'P001',
    admission_date: '2024-12-20',
    discharge_date: '2024-12-24',
    department_id: '2',
    department_name: '内科',
    doctor_id: '2',
    doctor_name: '张医生',
    diagnosis_primary: '急性胃炎',
    diagnosis_secondary: ['消化不良', '胃溃疡'],
    status: 'completed',
    qc_status: 'reviewed',
    qc_score: 85,
    qc_grade: 'B',
    created_at: '2024-12-20T10:00:00Z',
    updated_at: '2024-12-24T16:00:00Z'
  },
  {
    id: '2',
    record_number: 'MR20241225002',
    patient_name: '李小红',
    patient_id: 'P002',
    admission_date: '2024-12-22',
    discharge_date: '2024-12-25',
    department_id: '2',
    department_name: '内科',
    doctor_id: '2',
    doctor_name: '张医生',
    diagnosis_primary: '高血压',
    diagnosis_secondary: ['糖尿病'],
    status: 'completed',
    qc_status: 'pending',
    qc_score: 92,
    qc_grade: 'A',
    created_at: '2024-12-22T09:00:00Z',
    updated_at: '2024-12-25T14:00:00Z'
  },
  {
    id: '3',
    record_number: 'MR20241225003',
    patient_name: '赵小刚',
    patient_id: 'P003',
    admission_date: '2024-12-23',
    discharge_date: null,
    department_id: '2',
    department_name: '内科',
    doctor_id: '2',
    doctor_name: '张医生',
    diagnosis_primary: '肺炎',
    diagnosis_secondary: [],
    status: 'draft',
    qc_status: null,
    qc_score: null,
    qc_grade: null,
    created_at: '2024-12-23T11:00:00Z',
    updated_at: '2024-12-25T10:00:00Z'
  }
]

const mockQCResults: MockQCResult[] = [
  {
    id: '1',
    record_id: '1',
    overall_score: 85,
    overall_grade: 'B',
    analysis_date: '2024-12-24T16:00:00Z',
    issues: [
      {
        id: '1',
        rule_id: 'R001',
        rule_name: '诊断完整性检查',
        severity: 'minor',
        category: '完整性',
        description: '主要诊断描述不够详细',
        location: '诊断部分',
        suggestion: '建议补充详细的诊断描述和依据'
      },
      {
        id: '2',
        rule_id: 'R002',
        rule_name: '用药合理性检查',
        severity: 'major',
        category: '准确性',
        description: '用药剂量可能过大',
        location: '用药记录',
        suggestion: '建议复核用药剂量，参考标准用药指南'
      }
    ],
    suggestions: [
      {
        id: '1',
        category: '诊断优化',
        title: '完善诊断描述',
        description: '建议在主要诊断中添加更详细的病理描述',
        priority: 'medium'
      },
      {
        id: '2',
        category: '用药安全',
        title: '复核用药剂量',
        description: '建议根据患者体重和病情调整用药剂量',
        priority: 'high'
      }
    ],
    rule_results: [
      {
        rule_id: 'R001',
        rule_name: '诊断完整性检查',
        passed: false,
        score: 75,
        details: '诊断描述不够完整'
      },
      {
        rule_id: 'R002',
        rule_name: '用药合理性检查',
        passed: false,
        score: 60,
        details: '用药剂量超出推荐范围'
      }
    ]
  }
]

export class MockService {
  static async login(request: LoginRequest): Promise<MockLoginResponse> {
    await delay(800)

    const user = mockUsers.find(u =>
      u.email === request.email &&
      u.password === request.password &&
      u.role === request.role
    )

    if (!user) {
      throw new Error('邮箱、密码或角色不正确')
    }

    return {
      user: {
        id: user.id,
        email: user.email,
        full_name: user.full_name,
        role: user.role,
        department_id: user.department_id,
        avatar_url: user.avatar_url
      },
      tokens: {
        access_token: `mock_token_${user.id}_${Date.now()}`,
        refresh_token: `mock_refresh_${user.id}_${Date.now()}`,
        expires_in: 3600
      }
    }
  }

  static async getProfile(userId: string): Promise<MockUserProfile> {
    await delay(300)

    const user = mockUsers.find(u => u.id === userId)
    if (!user) {
      throw new Error('用户不存在')
    }

    return {
      id: user.id,
      email: user.email,
      full_name: user.full_name,
      role: user.role,
      department_id: user.department_id,
      department_name: user.department_name,
      avatar_url: user.avatar_url,
      phone: user.phone,
      created_at: user.created_at,
      last_login: user.last_login
    }
  }

  static async getRecords(params: unknown = {}): Promise<{
    records: MockMedicalRecord[]
    pagination: {
      total: number
      page: number
      limit: number
      pages: number
    }
  }> {
    await delay(600)

    const query = typeof params === 'object' && params !== null ? params as Record<string, unknown> : {}
    const page = typeof query.page === 'number' ? query.page : 1
    const limit = typeof query.limit === 'number' ? query.limit : 10
    const search = typeof query.search === 'string' ? query.search : ''
    const status = typeof query.status === 'string' ? query.status : ''

    let filteredRecords = [...mockRecords]

    if (search) {
      filteredRecords = filteredRecords.filter(record =>
        record.patient_name.includes(search) ||
        record.record_number.includes(search) ||
        record.diagnosis_primary.includes(search)
      )
    }

    if (status) {
      filteredRecords = filteredRecords.filter(record => record.status === status)
    }

    const total = filteredRecords.length
    const pages = Math.ceil(total / limit)
    const start = (page - 1) * limit
    const end = start + limit

    return {
      records: filteredRecords.slice(start, end),
      pagination: {
        total,
        page,
        limit,
        pages
      }
    }
  }

  static async getRecordDetail(recordId: string): Promise<MockMedicalRecord & {
    content: string
    attachments: Array<{
      id: string
      filename: string
      file_type: string
      file_size: number
      url: string
      uploaded_at: string
    }>
    qc_results?: MockQCResult[]
    history: Array<{
      id: string
      action: string
      user_name: string
      timestamp: string
      details: string
    }>
  }> {
    await delay(400)

    const record = mockRecords.find(r => r.id === recordId)
    if (!record) {
      throw new Error('记录不存在')
    }

    return {
      ...record,
      content: `患者${record.patient_name}，诊断为${record.diagnosis_primary}。

入院情况：患者因${record.diagnosis_primary}入院治疗。
现病史：患者近期出现相关症状，经检查确诊。
既往史：无特殊病史。
体格检查：生命体征平稳。
辅助检查：相关检查结果支持诊断。
诊断：${record.diagnosis_primary}${record.diagnosis_secondary.length ? '，' + record.diagnosis_secondary.join('，') : ''}
治疗方案：给予对症治疗。
出院情况：患者病情好转出院。`,
      attachments: [
        {
          id: '1',
          filename: '检查报告.pdf',
          file_type: 'application/pdf',
          file_size: 1024000,
          url: '/mock/files/report1.pdf',
          uploaded_at: '2024-12-20T10:30:00Z'
        }
      ],
      qc_results: recordId === '1' ? [mockQCResults[0]] : undefined,
      history: [
        {
          id: '1',
          action: '创建记录',
          user_name: record.doctor_name,
          timestamp: record.created_at,
          details: '创建医疗记录'
        },
        {
          id: '2',
          action: '更新记录',
          user_name: record.doctor_name,
          timestamp: record.updated_at,
          details: '更新诊断信息'
        }
      ]
    }
  }

  static async analyzeRecord(recordId: string): Promise<{
    task_id: string
    status: string
    estimated_time?: number
  }> {
    await delay(1000)

    return {
      task_id: `task_${recordId}_${Date.now()}`,
      status: 'processing',
      estimated_time: 30
    }
  }

  static async getQCResults(recordId: string): Promise<MockQCResult> {
    await delay(800)

    const result = mockQCResults.find(r => r.record_id === recordId)
    if (!result) {
      throw new Error('质控结果不存在')
    }

    return result
  }

  static async semanticSearch(query: string): Promise<MockSearchResult[]> {
    await delay(1200)

    const results: MockSearchResult[] = [
      {
        record_id: '1',
        record_number: 'MR20241225001',
        patient_name: '王小明',
        diagnosis_primary: '急性胃炎',
        content_snippet: '患者因急性胃炎入院，经治疗后症状缓解...',
        similarity_score: 0.95,
        highlight: ['急性胃炎', '症状缓解']
      },
      {
        record_id: '2',
        record_number: 'MR20241225002',
        patient_name: '李小红',
        diagnosis_primary: '高血压',
        content_snippet: '患者有高血压病史，本次因血压控制不佳入院...',
        similarity_score: 0.78,
        highlight: ['高血压', '血压控制']
      }
    ]

    return results.filter(r =>
      r.diagnosis_primary.includes(query) ||
      r.content_snippet.includes(query)
    )
  }

  static async getDashboardData(): Promise<MockDashboardData> {
    await delay(1000)

    return {
      summary: {
        total_records: 156,
        completed_records: 142,
        avg_qc_score: 87.5,
        grade_distribution: {
          A: 45,
          B: 67,
          C: 25,
          D: 5
        }
      },
      trends: [
        { date: '2024-12-18', records_count: 12, avg_score: 85.2 },
        { date: '2024-12-19', records_count: 15, avg_score: 87.1 },
        { date: '2024-12-20', records_count: 18, avg_score: 89.3 },
        { date: '2024-12-21', records_count: 14, avg_score: 86.7 },
        { date: '2024-12-22', records_count: 16, avg_score: 88.9 },
        { date: '2024-12-23', records_count: 13, avg_score: 87.4 },
        { date: '2024-12-24', records_count: 11, avg_score: 85.8 }
      ],
      department_stats: [
        {
          department_id: '1',
          department_name: '内科',
          records_count: 89,
          avg_score: 88.2,
          grade_a_rate: 0.32
        },
        {
          department_id: '2',
          department_name: '外科',
          records_count: 67,
          avg_score: 86.7,
          grade_a_rate: 0.28
        }
      ]
    }
  }
}

export default MockService
