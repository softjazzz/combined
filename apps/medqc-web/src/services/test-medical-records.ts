// @ts-nocheck
/**
 * 测试病历模块服务层（模拟实现）
 * 提供列表查询、详情、批量操作以及筛选模板等基础能力
 */
import type {
  ApiResponse,
  BatchActionPayload,
  FilterTemplate,
  PaginationState,
  QuickFilterTag,
  RecordListResponse,
  RecordSearchConditions,
  TestMedicalRecordDetail,
  TestMedicalRecordSummary
} from '@/types/test-medical-records'

const delay = (ms: number) => new Promise(resolve => setTimeout(resolve, ms))

const mockRecords: TestMedicalRecordDetail[] = [
  {
    id: 'rec-001',
    recordCode: 'TEST-REC-2024-001',
    name: '胸痛患者入院记录（复杂）',
    type: 'admission',
    department: '心内科',
    diseaseCategory: '心血管系统',
    complexity: 'complex',
    createdAt: '2024-12-01T08:00:00Z',
    updatedAt: '2024-12-15T10:30:00Z',
    createdBy: 'qc_admin',
    status: 'verified',
    relatedRuleCount: 12,
    passRate: 0.86,
    tags: ['高风险', '胸痛中心'],
    description: '用于验证胸痛中心质控流程的标准入院病历，包含完整的诊疗路径与检查记录。',
    expectedGrade: 'A',
    expectedScoreRange: [90, 100],
    expectedDefectTypes: ['诊疗路径缺失', '关键检查遗漏'],
    expectedDefectCount: 0,
    checkpoints: [
      {
        id: 'cp-01',
        title: '首诊接诊记录完整性',
        description: '包含发病时间、发病经过、既往史、首诊医师签名等关键字段',
        priority: 'high'
      },
      {
        id: 'cp-02',
        title: '关键检查结果记录',
        description: '心电图、肌钙蛋白等结果与时间戳齐全',
        priority: 'medium'
      }
    ],
    content: '【病史摘要】患者男性，58岁，胸痛3小时入院……'
  },
  {
    id: 'rec-002',
    recordCode: 'TEST-REC-2024-002',
    name: '剖宫产术后病程记录（中等）',
    type: 'progress',
    department: '妇产科',
    diseaseCategory: '产科',
    complexity: 'medium',
    createdAt: '2024-12-05T09:20:00Z',
    updatedAt: '2024-12-06T16:45:00Z',
    createdBy: 'ob_gyn_editor',
    status: 'ready',
    relatedRuleCount: 8,
    passRate: 0.72,
    tags: ['围产期', '典型案例'],
    expectedGrade: 'B',
    expectedScoreRange: [80, 95],
    expectedDefectTypes: ['用药记录不完整'],
    expectedDefectCount: 1,
    checkpoints: [
      {
        id: 'cp-11',
        title: '术后监测记录完整',
        description: '生命体征、出血量、子宫收缩情况记录齐全',
        priority: 'high'
      }
    ],
    content: '【术后记录】患者女性，32岁，因胎位异常行剖宫产术……'
  },
  {
    id: 'rec-003',
    recordCode: 'TEST-REC-2024-003',
    name: '慢阻肺患者出院总结（简单）',
    type: 'discharge',
    department: '呼吸内科',
    diseaseCategory: '呼吸系统',
    complexity: 'simple',
    createdAt: '2024-11-28T13:00:00Z',
    updatedAt: '2024-12-01T09:00:00Z',
    createdBy: 'respiratory_qc',
    status: 'archived',
    relatedRuleCount: 5,
    passRate: 0.94,
    tags: ['示范', '慢病管理'],
    expectedGrade: 'A',
    expectedScoreRange: [88, 98],
    content: '【出院总结】患者男性，65岁……'
  },
  {
    id: 'rec-004',
    recordCode: 'TEST-REC-2024-004',
    name: '糖尿病足病例测试集',
    type: 'admission',
    department: '内分泌科',
    diseaseCategory: '内分泌',
    complexity: 'very_complex',
    createdAt: '2024-12-10T07:50:00Z',
    updatedAt: '2024-12-19T18:10:00Z',
    createdBy: 'endocrine_specialist',
    status: 'draft',
    relatedRuleCount: 15,
    passRate: 0.58,
    tags: ['重点关注', '多学科'],
    expectedGrade: 'C',
    expectedScoreRange: [70, 85],
    expectedDefectTypes: ['会诊记录缺失', '护理评估缺失'],
    expectedDefectCount: 3,
    checkpoints: [
      {
        id: 'cp-21',
        title: '多学科会诊记录齐全',
        description: '包含内分泌、血管外科、康复科的会诊意见',
        priority: 'high'
      },
      {
        id: 'cp-22',
        title: '糖尿病足分级记录准确',
        description: '参照Wagner分级并记录相应处理措施',
        priority: 'high'
      }
    ],
    content: '【病例综述】患者男性，62岁，糖尿病足溃疡……'
  }
]

let filterTemplates: FilterTemplate[] = [
  {
    id: 'tpl-high-risk',
    name: '高风险重点病历',
    conditions: {
      complexity: ['complex', 'very_complex'],
      status: ['ready', 'verified'],
      tags: ['高风险', '重点关注']
    },
    createdAt: '2024-12-15T09:00:00Z',
    updatedAt: '2024-12-15T09:00:00Z'
  },
  {
    id: 'tpl-ready-release',
    name: '待发布病历',
    conditions: {
      status: ['ready'],
      passRateGreaterThan: undefined
    } as RecordSearchConditions,
    createdAt: '2024-12-20T12:30:00Z',
    updatedAt: '2024-12-20T12:30:00Z'
  }
]

export const quickFilterTags: QuickFilterTag[] = [
  {
    key: 'recent-updated',
    label: '近7日更新',
    conditions: {
      createdTimeRange: [
        new Date(Date.now() - 7 * 24 * 60 * 60 * 1000).toISOString(),
        new Date().toISOString()
      ]
    }
  },
  {
    key: 'ready-release',
    label: '待发布',
    conditions: {
      status: ['ready']
    }
  },
  {
    key: 'high-risk',
    label: '高风险测试集',
    conditions: {
      tags: ['高风险', '重点关注']
    }
  }
]

const paginate = (items: TestMedicalRecordSummary[], pagination: PaginationState): RecordListResponse => {
  const start = (pagination.current - 1) * pagination.pageSize
  const end = start + pagination.pageSize

  return {
    items: items.slice(start, end),
    pagination: {
      ...pagination,
      total: items.length
    }
  }
}

const matchesConditions = (record: TestMedicalRecordSummary, conditions: RecordSearchConditions): boolean => {
  if (conditions.keyword && conditions.keywordType) {
    const key = conditions.keywordType === 'id' ? record.recordCode
      : conditions.keywordType === 'name' ? record.name
      : record.createdBy
    if (!key.toLowerCase().includes(conditions.keyword.toLowerCase())) {
      return false
    }
  }

  if (conditions.recordType?.length && !conditions.recordType.includes(record.type)) {
    return false
  }

  if (conditions.departments?.length && !conditions.departments.includes(record.department)) {
    return false
  }

  if (conditions.diseaseCategories?.length && !conditions.diseaseCategories.includes(record.diseaseCategory)) {
    return false
  }

  if (conditions.complexity?.length && !conditions.complexity.includes(record.complexity)) {
    return false
  }

  if (conditions.status?.length && !conditions.status.includes(record.status)) {
    return false
  }

  if (conditions.tags?.length && !conditions.tags.some(tag => record.tags.includes(tag))) {
    return false
  }

  if (conditions.createdTimeRange) {
    const [start, end] = conditions.createdTimeRange
    if (start && new Date(record.createdAt) < new Date(start)) return false
    if (end && new Date(record.createdAt) > new Date(end)) return false
  }

  if (
    typeof conditions.passRateGreaterThan === 'number' &&
    record.passRate < conditions.passRateGreaterThan
  ) {
    return false
  }

  if (
    typeof conditions.passRateLessThan === 'number' &&
    record.passRate > conditions.passRateLessThan
  ) {
    return false
  }

  return true
}

export const TestMedicalRecordService = {
  async fetchList(
    conditions: RecordSearchConditions,
    pagination: PaginationState
  ): Promise<ApiResponse<RecordListResponse>> {
    await delay(400)

    const filtered = mockRecords.filter(record => matchesConditions(record, conditions))
    const summaryList: TestMedicalRecordSummary[] = filtered.map(record => ({
      id: record.id,
      recordCode: record.recordCode,
      name: record.name,
      type: record.type,
      department: record.department,
      diseaseCategory: record.diseaseCategory,
      complexity: record.complexity,
      createdAt: record.createdAt,
      updatedAt: record.updatedAt,
      createdBy: record.createdBy,
      status: record.status,
      relatedRuleCount: record.relatedRuleCount,
      passRate: record.passRate,
      tags: record.tags
    }))

    return {
      success: true,
      data: paginate(summaryList, pagination)
    }
  },

  async fetchDetail(id: string): Promise<ApiResponse<TestMedicalRecordDetail | null>> {
    await delay(200)
    const record = mockRecords.find(item => item.id === id)
    return {
      success: !!record,
      data: record ?? null,
      message: record ? undefined : '未找到对应病历'
    }
  },

  async performBatchAction(payload: BatchActionPayload): Promise<ApiResponse<{ succeeded: string[]; failed: string[] }>> {
    await delay(300)
    const knownIds = new Set(mockRecords.map(r => r.id))
    const succeeded = payload.recordIds.filter(id => knownIds.has(id))
    const failed = payload.recordIds.filter(id => !knownIds.has(id))

    // 模拟状态更新
    if (payload.action === 'updateStatus' && payload.targetStatus) {
      mockRecords.forEach(record => {
        if (succeeded.includes(record.id)) {
          record.status = payload.targetStatus!
          record.updatedAt = new Date().toISOString()
        }
      })
    }

    return {
      success: failed.length === 0,
      data: {
        succeeded,
        failed
      },
      message: failed.length
        ? `部分病历未找到：${failed.join(', ')}`
        : '批量操作执行成功'
    }
  },

  async fetchFilterTemplates(): Promise<ApiResponse<FilterTemplate[]>> {
    await delay(150)
    return {
      success: true,
      data: filterTemplates
    }
  },

  async saveFilterTemplate(template: Omit<FilterTemplate, 'id' | 'createdAt' | 'updatedAt'> & { id?: string }): Promise<ApiResponse<FilterTemplate>> {
    await delay(150)
    if (template.id) {
      const existing = filterTemplates.find(item => item.id === template.id)
      if (existing) {
        existing.name = template.name
        existing.conditions = template.conditions
        existing.updatedAt = new Date().toISOString()
        return {
          success: true,
          data: existing
        }
      }
    }

    const newTemplate: FilterTemplate = {
      id: `tpl-${Date.now()}`,
      name: template.name,
      conditions: template.conditions,
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString()
    }
    filterTemplates = [newTemplate, ...filterTemplates]
    return {
      success: true,
      data: newTemplate
    }
  },

  async deleteFilterTemplate(id: string): Promise<ApiResponse<boolean>> {
    await delay(120)
    const before = filterTemplates.length
    filterTemplates = filterTemplates.filter(item => item.id !== id)
    return {
      success: true,
      data: before !== filterTemplates.length
    }
  },

  getQuickFilters(): QuickFilterTag[] {
    return quickFilterTags
  }
}

