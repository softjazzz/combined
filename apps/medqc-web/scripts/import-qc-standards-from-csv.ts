#!/usr/bin/env node
/**
 * 质控标准CSV导入工具
 * 基于住院质量评定标准CSV文件自动生成质控规则
 */

import { createClient } from '@supabase/supabase-js'
import { readFileSync } from 'fs'
import { parse } from 'csv-parse/sync'
import { config } from 'dotenv'

// 加载环境变量
config()

// 质控规则接口
interface StandardQCRule {
  standard_code: string
  category: string
  subcategory?: string
  rule_name: string
  rule_description: string
  check_points: string[]
  scoring_criteria: {
    max_score: number
    deduction_rules: Array<{
      condition: string
      deduction: number
      description: string
    }>
  }
  severity_level: 'critical' | 'major' | 'minor'
  applicable_record_types: string[]
  check_method: 'manual' | 'auto' | 'hybrid'
  ai_prompt_template?: string
}

// CSV行数据接口
interface CSVRow {
  [key: string]: string
}

export class QCStandardImporter {
  private supabase
  
  constructor() {
    const supabaseUrl = process.env.VITE_SUPABASE_URL!
    const supabaseKey = process.env.VITE_SUPABASE_ANON_KEY!
    this.supabase = createClient(supabaseUrl, supabaseKey)
  }

  /**
   * 从CSV文件导入质控标准
   */
  async importFromCSV(csvPath: string): Promise<{
    success: boolean
    importedCount: number
    errors: string[]
  }> {
    console.log(`🚀 开始导入质控标准: ${csvPath}`)
    
    try {
      // 1. 读取和解析CSV文件
      const csvData = this.parseCSVFile(csvPath)
      console.log(`📄 解析到 ${csvData.length} 行数据`)

      // 2. 转换为标准化规则
      const standardizedRules = await this.transformToStandardRules(csvData)
      console.log(`🔄 转换为 ${standardizedRules.length} 条标准化规则`)

      // 3. 验证规则
      const validationResult = this.validateRules(standardizedRules)
      if (!validationResult.isValid) {
        return {
          success: false,
          importedCount: 0,
          errors: validationResult.errors
        }
      }

      // 4. 导入到数据库
      const importResult = await this.importToDatabase(standardizedRules)
      
      // 5. 生成规则文档
      await this.generateRuleDocumentation(standardizedRules)

      console.log(`✅ 成功导入 ${importResult.importedCount} 条规则`)
      
      return {
        success: true,
        importedCount: importResult.importedCount,
        errors: importResult.errors
      }

    } catch (error) {
      console.error('❌ 导入失败:', error)
      return {
        success: false,
        importedCount: 0,
        errors: [error instanceof Error ? error.message : String(error)]
      }
    }
  }

  /**
   * 解析CSV文件
   */
  private parseCSVFile(csvPath: string): CSVRow[] {
    try {
      const fileContent = readFileSync(csvPath, 'utf-8')
      
      // 解析CSV，自动检测分隔符
      const records = parse(fileContent, {
        columns: true,
        skip_empty_lines: true,
        trim: true,
        delimiter: [',', ';', '\t'], // 自动检测分隔符
        encoding: 'utf8'
      })

      return records as CSVRow[]
    } catch (error) {
      throw new Error(`CSV文件解析失败: ${error instanceof Error ? error.message : String(error)}`)
    }
  }

  /**
   * 转换为标准化规则
   */
  private async transformToStandardRules(csvData: CSVRow[]): Promise<StandardQCRule[]> {
    const rules: StandardQCRule[] = []
    
    for (const row of csvData) {
      try {
        // 根据CSV列名映射数据
        const rule = this.mapCSVRowToRule(row)
        if (rule) {
          rules.push(rule)
        }
      } catch (error) {
        console.warn(`跳过无效行:`, error)
      }
    }

    return rules
  }

  /**
   * 映射CSV行到规则对象
   */
  private mapCSVRowToRule(row: CSVRow): StandardQCRule | null {
    // 根据实际CSV文件的列名进行映射
    // 这里需要根据实际的CSV文件结构调整
    
    const ruleCode = row['规则编码'] || row['code'] || row['标准编码']
    const ruleName = row['规则名称'] || row['name'] || row['检查项目']
    const description = row['规则描述'] || row['description'] || row['检查内容']
    const category = row['分类'] || row['category'] || this.inferCategory(ruleName)
    
    if (!ruleCode || !ruleName) {
      return null // 跳过无效行
    }

    // 推断严重程度
    const severity = this.inferSeverity(ruleName, description)
    
    // 推断检查方法
    const checkMethod = this.inferCheckMethod(description)
    
    // 构建评分标准
    const scoringCriteria = this.buildScoringCriteria(row)
    
    // 生成AI提示词模板
    const aiPromptTemplate = this.generateAIPromptTemplate(ruleName, description, category)

    return {
      standard_code: ruleCode,
      category: category,
      subcategory: row['子分类'] || row['subcategory'],
      rule_name: ruleName,
      rule_description: description,
      check_points: this.extractCheckPoints(description),
      scoring_criteria: scoringCriteria,
      severity_level: severity,
      applicable_record_types: ['inpatient'], // 默认住院病历
      check_method: checkMethod,
      ai_prompt_template: aiPromptTemplate
    }
  }

  /**
   * 推断规则分类
   */
  private inferCategory(ruleName: string): string {
    const categoryKeywords = {
      'completeness': ['完整', '缺失', '必填', '必要', '齐全'],
      'consistency': ['一致', '矛盾', '符合', '匹配', '对应'],
      'rationality': ['合理', '逻辑', '适当', '正确', '准确'],
      'timeliness': ['及时', '时间', '期限', '延迟', '超时']
    }

    for (const [category, keywords] of Object.entries(categoryKeywords)) {
      if (keywords.some(keyword => ruleName.includes(keyword))) {
        return category
      }
    }

    return 'completeness' // 默认分类
  }

  /**
   * 推断严重程度
   */
  private inferSeverity(ruleName: string, description: string): 'critical' | 'major' | 'minor' {
    const text = `${ruleName} ${description}`.toLowerCase()
    
    const criticalKeywords = ['严重', '危险', '致命', '必须', '禁止', '违法']
    const majorKeywords = ['重要', '关键', '主要', '显著', '明显']
    
    if (criticalKeywords.some(keyword => text.includes(keyword))) {
      return 'critical'
    } else if (majorKeywords.some(keyword => text.includes(keyword))) {
      return 'major'
    } else {
      return 'minor'
    }
  }

  /**
   * 推断检查方法
   */
  private inferCheckMethod(description: string): 'manual' | 'auto' | 'hybrid' {
    const autoKeywords = ['自动', '计算', '统计', '格式', '长度', '数字']
    const manualKeywords = ['判断', '评估', '分析', '理解', '解释']
    
    const hasAuto = autoKeywords.some(keyword => description.includes(keyword))
    const hasManual = manualKeywords.some(keyword => description.includes(keyword))
    
    if (hasAuto && hasManual) return 'hybrid'
    if (hasAuto) return 'auto'
    return 'manual'
  }

  /**
   * 构建评分标准
   */
  private buildScoringCriteria(row: CSVRow): StandardQCRule['scoring_criteria'] {
    const maxScore = parseInt(row['满分'] || row['max_score'] || '10')
    const deduction = parseInt(row['扣分'] || row['deduction'] || '5')
    
    return {
      max_score: maxScore,
      deduction_rules: [
        {
          condition: '违反规则',
          deduction: deduction,
          description: row['扣分说明'] || row['deduction_desc'] || '不符合质控要求'
        }
      ]
    }
  }

  /**
   * 提取检查要点
   */
  private extractCheckPoints(description: string): string[] {
    // 简单的检查要点提取逻辑
    const points = description.split(/[；;。]/).filter(point => point.trim().length > 0)
    return points.map(point => point.trim())
  }

  /**
   * 生成AI提示词模板
   */
  private generateAIPromptTemplate(ruleName: string, description: string, category: string): string {
    return `
请分析以下病历内容是否符合质控规则：

规则名称：${ruleName}
规则描述：${description}
检查分类：${category}

病历内容：{content}

请严格按照以下JSON格式返回分析结果：
{
  "hasViolation": boolean,
  "confidence": number (0-1),
  "evidence": string[],
  "reasoning": "详细分析原因",
  "location": "具体位置（可选）",
  "suggestions": string[]
}

分析要求：
1. 仔细检查病历内容是否符合规则要求
2. 提供具体的证据支持判断
3. 给出详细的推理过程
4. 如有违反，提供改进建议
`.trim()
  }

  /**
   * 验证规则
   */
  private validateRules(rules: StandardQCRule[]): { isValid: boolean; errors: string[] } {
    const errors: string[] = []
    
    for (const rule of rules) {
      if (!rule.standard_code) {
        errors.push(`规则缺少标准编码: ${rule.rule_name}`)
      }
      
      if (!rule.rule_name) {
        errors.push(`规则缺少名称: ${rule.standard_code}`)
      }
      
      if (!rule.rule_description) {
        errors.push(`规则缺少描述: ${rule.standard_code}`)
      }
      
      if (!['critical', 'major', 'minor'].includes(rule.severity_level)) {
        errors.push(`规则严重程度无效: ${rule.standard_code}`)
      }
    }

    return {
      isValid: errors.length === 0,
      errors
    }
  }

  /**
   * 导入到数据库
   */
  private async importToDatabase(rules: StandardQCRule[]): Promise<{
    importedCount: number
    errors: string[]
  }> {
    let importedCount = 0
    const errors: string[] = []

    for (const rule of rules) {
      try {
        // 检查是否已存在
        const { data: existing } = await this.supabase
          .from('qc_rules')
          .select('id')
          .eq('rule_code', rule.standard_code)
          .single()

        if (existing) {
          // 更新现有规则
          const { error } = await this.supabase
            .from('qc_rules')
            .update({
              name: rule.rule_name,
              description: rule.rule_description,
              category: rule.category,
              severity: rule.severity_level,
              max_score: rule.scoring_criteria.max_score,
              check_logic: {
                check_points: rule.check_points,
                scoring_criteria: rule.scoring_criteria,
                ai_prompt_template: rule.ai_prompt_template
              },
              updated_at: new Date().toISOString()
            })
            .eq('rule_code', rule.standard_code)

          if (error) {
            errors.push(`更新规则失败 ${rule.standard_code}: ${error.message}`)
          } else {
            importedCount++
          }
        } else {
          // 插入新规则
          const { error } = await this.supabase
            .from('qc_rules')
            .insert({
              rule_code: rule.standard_code,
              name: rule.rule_name,
              description: rule.rule_description,
              category: rule.category,
              severity: rule.severity_level,
              max_score: rule.scoring_criteria.max_score,
              check_logic: {
                check_points: rule.check_points,
                scoring_criteria: rule.scoring_criteria,
                ai_prompt_template: rule.ai_prompt_template
              },
              is_active: true,
              created_at: new Date().toISOString()
            })

          if (error) {
            errors.push(`插入规则失败 ${rule.standard_code}: ${error.message}`)
          } else {
            importedCount++
          }
        }
      } catch (error) {
        errors.push(`处理规则失败 ${rule.standard_code}: ${error instanceof Error ? error.message : String(error)}`)
      }
    }

    return { importedCount, errors }
  }

  /**
   * 生成规则文档
   */
  private async generateRuleDocumentation(rules: StandardQCRule[]): Promise<void> {
    const fs = await import('fs/promises')
    
    let markdown = '# 质控规则文档\n\n'
    markdown += `生成时间: ${new Date().toISOString()}\n`
    markdown += `规则总数: ${rules.length}\n\n`

    // 按分类分组
    const rulesByCategory = rules.reduce((acc, rule) => {
      if (!acc[rule.category]) {
        acc[rule.category] = []
      }
      acc[rule.category].push(rule)
      return acc
    }, {} as Record<string, StandardQCRule[]>)

    for (const [category, categoryRules] of Object.entries(rulesByCategory)) {
      markdown += `## ${category}\n\n`
      
      for (const rule of categoryRules) {
        markdown += `### ${rule.rule_name}\n\n`
        markdown += `- **编码**: ${rule.standard_code}\n`
        markdown += `- **描述**: ${rule.rule_description}\n`
        markdown += `- **严重程度**: ${rule.severity_level}\n`
        markdown += `- **最高分**: ${rule.scoring_criteria.max_score}\n`
        markdown += `- **检查要点**: ${rule.check_points.join(', ')}\n\n`
      }
    }

    await fs.writeFile('docs/QC_RULES_DOCUMENTATION.md', markdown)
    console.log('📚 规则文档已生成: docs/QC_RULES_DOCUMENTATION.md')
  }
}

/**
 * 主函数
 */
async function main() {
  const csvPath = process.argv[2] || '（运行病历）住院质量评定标准_433377418703_2024-04-03_09-59-13.csv'
  
  if (!csvPath) {
    console.error('❌ 请提供CSV文件路径')
    process.exit(1)
  }

  const importer = new QCStandardImporter()
  const result = await importer.importFromCSV(csvPath)

  if (result.success) {
    console.log(`🎉 导入完成！成功导入 ${result.importedCount} 条规则`)
  } else {
    console.error('❌ 导入失败:')
    result.errors.forEach(error => console.error(`  - ${error}`))
    process.exit(1)
  }
}

// 运行脚本
if (require.main === module) {
  main().catch(error => {
    console.error('❌ 脚本执行失败:', error)
    process.exit(1)
  })
}

export { QCStandardImporter }
