import { RULES_CONFIG } from '@/config/rules-config'

// 验证结果接口
export interface ValidationResult {
  isValid: boolean
  errors: string[]
  warnings: string[]
}

// 规则数据接口
export interface RuleData {
  rule_code: string
  name: string
  description: string
  category: string
  rule_type: string
  severity: string
  max_score: number
  weight: number
  check_logic: Record<string, unknown>
  prompt_template?: string
  version: string
}

/**
 * 规则验证器类
 */
export class RulesValidator { /**
   * 验证规则编码格式
   */
  static validateRuleCode(ruleCode: string): ValidationResult {
    const result: ValidationResult = {
      isValid: true,
      errors:  [],
      warnings: []
    }

    // 检查是否为空
    if (!ruleCode || ruleCode.trim() === '') {
      result.isValid = false
      result.errors.push('规则编码不能为空')
      return result
    }

    // 检查格式：数字.数字.数字...
    const codePattern = /^\d+(\.\d+)*$/
    if (!codePattern.test(ruleCode)) {
      result.isValid = false
      result.errors.push('规则编码格式不正确，应为数字和点的组合，如: 1.1.1')
    }

    // 检查层级深度（建议不超过4级）
    const levels = ruleCode.split('.')
    if (levels.length > 4) {
      result.warnings.push('规则编码层级过深，建议不超过4级')
    }

    // 检查每个层级的数字范围
    for (const level of levels) {
      const num = parseInt(level)
      if (num < 1 || num > 999) {
        result.warnings.push(`规则编码层级 ${level} 超出建议范围(1-999)`)
      }
    }

    return result
  }

  /**
   * 验证规则名称
   */
  static validateRuleName(name: string): ValidationResult { const result: ValidationResult = {
      isValid: true,
      errors:  [],
      warnings: []
    }

    if (!name || name.trim() === '') {
      result.isValid = false
      result.errors.push('规则名称不能为空')
      return result
    }

    const trimmedName = name.trim()
    
    // 长度检查
    if (trimmedName.length < 2) {
      result.isValid = false
      result.errors.push('规则名称长度不能少于2个字符')
    }

    if (trimmedName.length > 100) {
      result.isValid = false
      result.errors.push('规则名称长度不能超过100个字符')
    }

    // 内容检查
    if (trimmedName.length < 5) {
      result.warnings.push('规则名称过短，建议使用更具描述性的名称')
    }

    // 特殊字符检查
    const invalidChars = /[<>\"'&]/
    if (invalidChars.test(trimmedName)) {
      result.isValid = false
      result.errors.push('规则名称包含无效字符')
    }

    return result
  }

  /**
   * 验证规则描述
   */
  static validateRuleDescription(description: string): ValidationResult { const result: ValidationResult = {
      isValid: true,
      errors:  [],
      warnings: []
    }

    if (!description || description.trim() === '') {
      result.isValid = false
      result.errors.push('规则描述不能为空')
      return result
    }

    const trimmedDesc = description.trim()
    
    // 长度检查
    if (trimmedDesc.length < 10) {
      result.isValid = false
      result.errors.push('规则描述长度不能少于10个字符')
    }

    if (trimmedDesc.length > 500) {
      result.isValid = false
      result.errors.push('规则描述长度不能超过500个字符')
    }

    // 内容质量检查
    if (trimmedDesc.length < 20) {
      result.warnings.push('规则描述过短，建议提供更详细的说明')
    }

    return result
  }

  /**
   * 验证规则分类
   */
  static validateRuleCategory(category: string): ValidationResult { const result: ValidationResult = {
      isValid: true,
      errors:  [],
      warnings: []
    }

    if (!category) {
      result.isValid = false
      result.errors.push('规则分类不能为空')
      return result
    }

    const validCategories = Object.keys(RULES_CONFIG.categories)
    if (!validCategories.includes(category)) {
      result.isValid = false
      result.errors.push(`无效的规则分类: ${category}，有效值为: ${validCategories.join(', ')}`)
    }

    return result
  }

  /**
   * 验证规则类型
   */
  static validateRuleType(ruleType: string): ValidationResult { const result: ValidationResult = {
      isValid: true,
      errors:  [],
      warnings: []
    }

    if (!ruleType) {
      result.isValid = false
      result.errors.push('规则类型不能为空')
      return result
    }

    const validTypes = Object.keys(RULES_CONFIG.types)
    if (!validTypes.includes(ruleType)) {
      result.isValid = false
      result.errors.push(`无效的规则类型: ${ruleType}，有效值为: ${validTypes.join(', ')}`)
    }

    return result
  }

  /**
   * 验证严重程度
   */
  static validateRuleSeverity(severity: string): ValidationResult { const result: ValidationResult = {
      isValid: true,
      errors:  [],
      warnings: []
    }

    if (!severity) {
      result.isValid = false
      result.errors.push('严重程度不能为空')
      return result
    }

    const validSeverities = Object.keys(RULES_CONFIG.severities)
    if (!validSeverities.includes(severity)) {
      result.isValid = false
      result.errors.push(`无效的严重程度: ${severity}，有效值为: ${validSeverities.join(', ')}`)
    }

    return result
  }

  /**
   * 验证最大扣分
   */
  static validateMaxScore(maxScore: number, severity: string): ValidationResult { const result: ValidationResult = {
      isValid: true,
      errors:  [],
      warnings: []
    }

    if (maxScore === undefined || maxScore === null) {
      result.isValid = false
      result.errors.push('最大扣分不能为空')
      return result
    }

    // 范围检查
    if (maxScore < 0 || maxScore > 100) {
      result.isValid = false
      result.errors.push('最大扣分必须在0-100之间')
      return result
    }

    // 与严重程度的一致性检查
    if (severity && RULES_CONFIG.severities[severity as keyof typeof RULES_CONFIG.severities]) {
      const severityConfig = RULES_CONFIG.severities[severity as keyof typeof RULES_CONFIG.severities]
      const [minScore, maxScoreRange] = severityConfig.score_range
      
      if (maxScore !== 0 && (maxScore < minScore || maxScore > maxScoreRange)) {
        result.warnings.push(`最大扣分 ${maxScore} 与严重程度 ${severity} 不匹配，建议范围: ${minScore}-${maxScoreRange}`)
      }
    }

    return result
  }

  /**
   * 验证权重
   */
  static validateWeight(weight: number): ValidationResult { const result: ValidationResult = {
      isValid: true,
      errors:  [],
      warnings: []
    }

    if (weight === undefined || weight === null) {
      result.isValid = false
      result.errors.push('权重不能为空')
      return result
    }

    if (weight < 0.1 || weight > 5.0) {
      result.isValid = false
      result.errors.push('权重必须在0.1-5.0之间')
    }

    if (weight > 3.0) {
      result.warnings.push('权重过高，可能会过度影响总分')
    }

    return result
  }

  /**
   * 验证检查逻辑
   */
  static validateCheckLogic(checkLogic: Record<string, unknown>): ValidationResult { const result: ValidationResult = {
      isValid: true,
      errors:  [],
      warnings: []
    }

    if (!checkLogic || Object.keys(checkLogic).length === 0) {
      result.warnings.push('检查逻辑为空，建议添加具体的检查配置')
      return result
    }

    // 检查必要的字段
    if (!checkLogic.type) {
      result.warnings.push('建议在检查逻辑中指定类型字段')
    }

    // 验证JSON结构
    try {
      JSON.stringify(checkLogic)
    } catch (error) {
      result.isValid = false
      result.errors.push('检查逻辑JSON格式无效')
    }

    return result
  }

  /**
   * 验证提示模板
   */
  static validatePromptTemplate(template?: string): ValidationResult { const result: ValidationResult = {
      isValid: true,
      errors:  [],
      warnings: []
    }

    if (!template || template.trim() === '') {
      result.warnings.push('建议添加提示模板以提高AI分析质量')
      return result
    }

    const trimmedTemplate = template.trim()
    
    // 长度检查
    if (trimmedTemplate.length < 20) {
      result.warnings.push('提示模板过短，建议提供更详细的指导')
    }

    if (trimmedTemplate.length > 2000) {
      result.warnings.push('提示模板过长，可能影响AI处理效率')
    }

    // 检查是否包含变量占位符
    const variables = Object.keys(RULES_CONFIG.variables)
    const hasVariables = variables.some(variable => trimmedTemplate.includes(variable))
    
    if (!hasVariables) {
      result.warnings.push('提示模板中未使用变量占位符，建议使用动态内容')
    }

    return result
  }

  /**
   * 验证版本号
   */
  static validateVersion(version: string): ValidationResult { const result: ValidationResult = {
      isValid: true,
      errors:  [],
      warnings: []
    }

    if (!version || version.trim() === '') {
      result.isValid = false
      result.errors.push('版本号不能为空')
      return result
    }

    // 简单的版本号格式检查
    const versionPattern = /^\d+\.\d+(\.\d+)?$/
    if (!versionPattern.test(version)) {
      result.warnings.push('版本号格式建议使用 x.y 或 x.y.z 格式')
    }

    return result
  }

  /**
   * 综合验证规则
   */
  static validateRule(rule: RuleData): ValidationResult { const result: ValidationResult = {
      isValid: true,
      errors:  [],
      warnings: []
    }

    // 验证各个字段
    const validations = [
      this.validateRuleCode(rule.rule_code),
      this.validateRuleName(rule.name),
      this.validateRuleDescription(rule.description),
      this.validateRuleCategory(rule.category),
      this.validateRuleType(rule.rule_type),
      this.validateRuleSeverity(rule.severity),
      this.validateMaxScore(rule.max_score, rule.severity),
      this.validateWeight(rule.weight),
      this.validateCheckLogic(rule.check_logic),
      this.validatePromptTemplate(rule.prompt_template),
      this.validateVersion(rule.version)
    ]

    // 合并验证结果
    for (const validation of validations) {
      if (!validation.isValid) {
        result.isValid = false
      }
      result.errors.push(...validation.errors)
      result.warnings.push(...validation.warnings)
    }

    return result
  }

  /**
   * 批量验证规则
   */
  static validateRules(rules: RuleData[]): { [ruleCode: string]: ValidationResult } {
    const results: { [ruleCode: string]: ValidationResult } = {}
    const ruleCodes = new Set<string>()

    for (const rule of rules) {
      // 检查重复的规则编码
      if (ruleCodes.has(rule.rule_code)) {
        results[rule.rule_code] = {
          isValid: false,
          errors: ['规则编码重复'],
          warnings: []
        }
      } else {
        ruleCodes.add(rule.rule_code)
        results[rule.rule_code] = this.validateRule(rule)
      }
    }

    return results
  }
}
