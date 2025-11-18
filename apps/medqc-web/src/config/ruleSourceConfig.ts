/**
 * 质控规则来源配置
 * 为演示系统提供多规则源支持的配置基础
 */

export type RuleSource = 'sichuan' | 'platform' | 'traditional'

export interface RuleSourceConfig {
  source: RuleSource
  label: string
  description: string
  apiEndpoint: string
  ruleCount?: number
  icon: string
  color: string
  features: string[]
}

/**
 * 规则来源配置映射
 */
export const RULE_SOURCE_CONFIG: Record<RuleSource, RuleSourceConfig> = {
  sichuan: {
    source: 'sichuan',
    label: '四川省标准',
    description: '基于《四川省住院病历质量评定标准（2023年版）》',
    apiEndpoint: '/api/v1/qc/sichuan/rules',
    ruleCount: 146,
    icon: 'FileProtectOutlined',
    color: 'blue',
    features: [
      '政府权威标准',
      'LLM优化提示词',
      '完整规则库（146条）',
      '多维度评估'
    ]
  },
  platform: {
    source: 'platform',
    label: '平台语义规则',
    description: '平台自定义的语义质控规则库',
    apiEndpoint: '/api/v1/semantic-rules',
    icon: 'CloudOutlined',
    color: 'green',
    features: [
      '平台自定义',
      '语义分析',
      '可动态扩展',
      'AI智能评估'
    ]
  },
  traditional: {
    source: 'traditional',
    label: '传统质控规则',
    description: '基于结构化逻辑的传统质控规则库',
    apiEndpoint: '/api/qc-rules',
    icon: 'SettingOutlined',
    color: 'orange',
    features: [
      '结构化检查',
      '字段验证',
      '快速执行',
      '确定性结果'
    ]
  }
}

/**
 * 默认使用的规则来源
 */
export const DEFAULT_RULE_SOURCE: RuleSource = 'sichuan'

/**
 * 获取规则来源配置
 */
export function getRuleSourceConfig(source: RuleSource): RuleSourceConfig {
  return RULE_SOURCE_CONFIG[source]
}

/**
 * 获取所有可用的规则来源
 */
export function getAllRuleSources(): RuleSourceConfig[] {
  return Object.values(RULE_SOURCE_CONFIG)
}

/**
 * 验证规则来源是否有效
 */
export function isValidRuleSource(source: string): source is RuleSource {
  return source in RULE_SOURCE_CONFIG
}
