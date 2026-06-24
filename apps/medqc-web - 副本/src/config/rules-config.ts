/**
 * 质控规则配置文件
 * 定义规则分类、严重程度、类型等配置信息
 */

// 规则分类配置
export const RULE_CATEGORIES = {
  completeness: {
    key: 'completeness',
    label: '完整性',
    description: '检查病历记录的完整性，确保必要信息不缺失',
    color: 'blue',
    icon: 'FileTextOutlined',
    weight: 1.0
  },
  consistency: {
    key: 'consistency',
    label: '一致性',
    description: '检查病历内容的一致性，确保信息前后呼应',
    color: 'green',
    icon: 'CheckCircleOutlined',
    weight: 1.2
  },
  rationality: {
    key: 'rationality',
    label: '合理性',
    description: '检查医疗行为的合理性，确保符合医学规范',
    color: 'orange',
    icon: 'BulbOutlined',
    weight: 1.5
  },
  timeliness: {
    key: 'timeliness',
    label: '及时性',
    description: '检查医疗行为的及时性，确保符合时间要求',
    color: 'purple',
    icon: 'ClockCircleOutlined',
    weight: 1.1
  }
} as const

// 严重程度配置
export const RULE_SEVERITIES = {
  critical: {
    key: 'critical',
    label: '严重',
    description: '严重问题，可能影响医疗安全或质量',
    color: 'red',
    score_range: [0, 0], // 通常为单否项
    priority: 1
  },
  major: {
    key: 'major',
    label: '重要',
    description: '重要问题，需要重点关注和改进',
    color: 'orange',
    score_range: [5, 20],
    priority: 2
  },
  minor: {
    key: 'minor',
    label: '轻微',
    description: '轻微问题，建议改进但不影响整体质量',
    color: 'blue',
    score_range: [1, 10],
    priority: 3
  }
} as const

// 规则类型配置
export const RULE_TYPES = {
  objective: {
    key: 'objective',
    label: '客观规则',
    description: '基于明确标准的客观检查规则',
    color: 'cyan',
    automation_level: 'high',
    requires_ai: false
  },
  subjective: {
    key: 'subjective',
    label: '主观规则',
    description: '需要专业判断的主观评估规则',
    color: 'geekblue',
    automation_level: 'low',
    requires_ai: true
  },
  hybrid: {
    key: 'hybrid',
    label: '混合规则',
    description: '结合客观检查和主观判断的综合规则',
    color: 'purple',
    automation_level: 'medium',
    requires_ai: true
  }
} as const

// 规则模板配置
export const RULE_TEMPLATES = { // 完整性检查模板
  completeness_check: {
    name: '完整性检查模板',
    category: 'completeness',
    check_logic_template: {
      type: 'field_validation',
      required_fields:  [],
      validation_rules: {},
      conditional_requirements: {}
    },
    prompt_template: '请检查以下字段是否完整填写：{fields}。每个字段都应有实质性内容，不能为空或过于简单。'
  },
  
  // 一致性检查模板
  consistency_check: { name: '一致性检查模板',
    category: 'consistency',
    check_logic_template: {
      type: 'consistency_validation',
      comparison_fields:  [],
      consistency_rules: {},
      tolerance_threshold: 0.8
    },
    prompt_template: '请检查以下字段之间的一致性：{fields}。内容应该逻辑一致，不能相互矛盾。'
  },
  
  // 合理性检查模板
  rationality_check: {
    name: '合理性检查模板',
    category: 'rationality',
    check_logic_template: {
      type: 'rationality_analysis',
      medical_logic_check: true,
      guideline_compliance: true,
      evidence_based: true
    },
    prompt_template: '请从医学专业角度分析以下内容的合理性：{content}。检查是否符合医学规范和临床指南。'
  },
  
  // 及时性检查模板
  timeliness_check: {
    name: '及时性检查模板',
    category: 'timeliness',
    check_logic_template: {
      type: 'timing_validation',
      time_requirements: {},
      sequence_check: true,
      interval_limits: {}
    },
    prompt_template: '请检查以下时间节点是否符合规定：{timepoints}。时间间隔应该合理，顺序应该正确。'
  }
} as const

// 检查逻辑配置模式
export const CHECK_LOGIC_SCHEMAS = {
  // 字段验证模式
  field_validation: {
    type: 'object',
    properties: {
      required_fields: {
        type: 'array',
        items: { type: 'string' },
        description: '必填字段列表'
      },
      validation_rules: {
        type: 'object',
        description: '字段验证规则',
        additionalProperties: {
          type: 'object',
          properties: {
            min_length: { type: 'number' },
            max_length: { type: 'number' },
            pattern: { type: 'string' },
            enum: { type: 'array' },
            type: { type: 'string' }
          }
        }
      },
      conditional_requirements: {
        type: 'object',
        description: '条件性要求',
        properties: {
          condition: { type: 'string' },
          required_fields: { type: 'array', items: { type: 'string' } }
        }
      }
    }
  },
  
  // 一致性验证模式
  consistency_validation: {
    type: 'object',
    properties: {
      comparison_fields: {
        type: 'array',
        items: { type: 'string' },
        description: '需要比较的字段'
      },
      consistency_rules: {
        type: 'object',
        description: '一致性规则'
      },
      tolerance_threshold: {
        type: 'number',
        minimum: 0,
        maximum: 1,
        description: '容忍阈值'
      }
    }
  },
  
  // 时间验证模式
  timing_validation: {
    type: 'object',
    properties: {
      time_requirements: {
        type: 'object',
        description: '时间要求'
      },
      sequence_check: {
        type: 'boolean',
        description: '是否检查时间序列'
      },
      interval_limits: {
        type: 'object',
        description: '时间间隔限制'
      }
    }
  }
} as const

// 提示模板变量
export const PROMPT_VARIABLES = {
  '{fields}': '字段列表',
  '{content}': '检查内容',
  '{timepoints}': '时间节点',
  '{diagnosis}': '诊断信息',
  '{patient_info}': '患者信息',
  '{medical_records}': '病历记录',
  '{medications}': '药物信息',
  '{examinations}': '检查检验',
  '{procedures}': '操作记录'
} as const

// 规则权重计算配置
export const WEIGHT_CALCULATION = {
  base_weights: {
    completeness: 1.0,
    consistency: 1.2,
    rationality: 1.5,
    timeliness: 1.1
  },
  severity_multipliers: {
    critical: 2.0,
    major: 1.5,
    minor: 1.0
  },
  type_adjustments: {
    objective: 1.0,
    subjective: 1.2,
    hybrid: 1.1
  }
} as const

// 规则执行配置
export const EXECUTION_CONFIG = {
  // 批量执行配置
  batch_size: 50,
  max_concurrent: 5,
  timeout_seconds: 30,
  
  // 重试配置
  max_retries: 3,
  retry_delay_ms: 1000,
  
  // 缓存配置
  cache_enabled: true,
  cache_ttl_minutes: 60,
  
  // AI分析配置
  ai_analysis: {
    model: 'gpt-4',
    temperature: 0.1,
    max_tokens: 2000,
    timeout_seconds: 30
  }
} as const

// 质量等级配置
export const QUALITY_GRADES = {
  A: {
    label: '甲级',
    score_range: [90, 100],
    color: 'green',
    description: '优秀，符合质量要求'
  },
  B: {
    label: '乙级',
    score_range: [75, 89],
    color: 'orange',
    description: '良好，存在轻微问题'
  },
  C: {
    label: '丙级',
    score_range: [0, 74],
    color: 'red',
    description: '不合格，存在严重问题'
  }
} as const

// 导出所有配置
export const RULES_CONFIG = {
  categories: RULE_CATEGORIES,
  severities: RULE_SEVERITIES,
  types: RULE_TYPES,
  templates: RULE_TEMPLATES,
  schemas: CHECK_LOGIC_SCHEMAS,
  variables: PROMPT_VARIABLES,
  weights: WEIGHT_CALCULATION,
  execution: EXECUTION_CONFIG,
  grades: QUALITY_GRADES
} as const

// 工具函数
export const getRuleCategoryLabel = (key: string) => {
  return RULE_CATEGORIES[key as keyof typeof RULE_CATEGORIES]?.label || key
}

export const getRuleSeverityLabel = (key: string) => {
  return RULE_SEVERITIES[key as keyof typeof RULE_SEVERITIES]?.label || key
}

export const getRuleTypeLabel = (key: string) => {
  return RULE_TYPES[key as keyof typeof RULE_TYPES]?.label || key
}

export const calculateRuleWeight = (
  category: string,
  severity: string,
  type: string
): number => {
  const baseWeight = WEIGHT_CALCULATION.base_weights[category as keyof typeof WEIGHT_CALCULATION.base_weights] || 1.0
  const severityMultiplier = WEIGHT_CALCULATION.severity_multipliers[severity as keyof typeof WEIGHT_CALCULATION.severity_multipliers] || 1.0
  const typeAdjustment = WEIGHT_CALCULATION.type_adjustments[type as keyof typeof WEIGHT_CALCULATION.type_adjustments] || 1.0
  
  return baseWeight * severityMultiplier * typeAdjustment
}

export const getQualityGrade = (score: number): string => {
  for (const [grade, config] of Object.entries(QUALITY_GRADES)) {
    if (score >= config.score_range[0] && score <= config.score_range[1]) {
      return grade
    }
  }
  return 'C' // 默认为丙级
}
