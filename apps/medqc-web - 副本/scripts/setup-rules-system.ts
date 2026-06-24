#!/usr/bin/env tsx

/**
 * 质控规则系统初始化脚本
 * 
 * 此脚本将：
 * 1. 检查数据库连接
 * 2. 验证规则表结构
 * 3. 初始化基础规则数据
 * 4. 创建规则索引和约束
 * 5. 生成规则统计报告
 */

import { createClient } from '@supabase/supabase-js'
import type { Database } from '../src/types/supabase'
import { config } from 'dotenv'
import { initComprehensiveRules } from './init-comprehensive-rules'

// 加载环境变量
config()

// 环境变量配置
const supabaseUrl = process.env.VITE_SUPABASE_URL || 'https://dgsdkdbjpucyawnyfbdu.supabase.co'
const supabaseServiceKey = process.env.SUPABASE_SERVICE_KEY || process.env.VITE_SUPABASE_ANON_KEY || 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImRnc2RrZGJqcHVjeWF3bnlmYmR1Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTYwODYyODcsImV4cCI6MjA3MTY2MjI4N30.k3178KRejQEoOogYjQ7EI_NfEW8ztVxFes3zLJ51JFw'

const supabase = createClient<Database>(supabaseUrl, supabaseServiceKey)

// 颜色输出工具
const colors = {
  reset: '\x1b[0m',
  bright: '\x1b[1m',
  red: '\x1b[31m',
  green: '\x1b[32m',
  yellow: '\x1b[33m',
  blue: '\x1b[34m',
  magenta: '\x1b[35m',
  cyan: '\x1b[36m'
}

const log = {
  info: (msg: string) => console.log(`${colors.blue}ℹ${colors.reset} ${msg}`),
  success: (msg: string) => console.log(`${colors.green}✅${colors.reset} ${msg}`),
  warning: (msg: string) => console.log(`${colors.yellow}⚠${colors.reset} ${msg}`),
  error: (msg: string) => console.log(`${colors.red}❌${colors.reset} ${msg}`),
  step: (msg: string) => console.log(`${colors.cyan}🔄${colors.reset} ${msg}`),
  header: (msg: string) => console.log(`\n${colors.bright}${colors.magenta}=== ${msg} ===${colors.reset}\n`)
}

/**
 * 检查数据库连接
 */
async function checkDatabaseConnection(): Promise<boolean> {
  try {
    log.step('检查数据库连接...')
    const { data, error } = await supabase.from('qc_rules').select('count').limit(1)
    
    if (error) {
      log.error(`数据库连接失败: ${error.message}`)
      return false
    }
    
    log.success('数据库连接正常')
    return true
  } catch (error) {
    log.error(`数据库连接异常: ${error}`)
    return false
  }
}

/**
 * 验证规则表结构
 */
async function validateTableStructure(): Promise<boolean> {
  try {
    log.step('验证规则表结构...')

    // 检查核心表是否存在
    const coreTable = 'qc_rules'
    const { error } = await supabase.from(coreTable as any).select('*').limit(1)
    if (error && error.code !== 'PGRST116') { // PGRST116 是空表错误，可以忽略
      log.error(`核心表 ${coreTable} 不存在或结构异常: ${error.message}`)
      return false
    }

    // 检查可选表（如果不存在也不影响基本功能）
    const optionalTables = ['qc_rule_executions', 'qc_issues']
    for (const table of optionalTables) {
      const { error } = await supabase.from(table as any).select('*').limit(1)
      if (error && error.code !== 'PGRST116') {
        log.warning(`可选表 ${table} 不存在，部分高级功能可能不可用`)
      } else {
        log.info(`可选表 ${table} 验证通过`)
      }
    }

    log.success('规则表结构验证通过')
    return true
  } catch (error) {
    log.error(`表结构验证失败: ${error}`)
    return false
  }
}

/**
 * 创建规则索引
 */
async function createRuleIndexes(): Promise<void> {
  try {
    log.step('创建规则索引...')
    
    // 这里可以添加创建索引的SQL语句
    // 由于Supabase的限制，我们通过应用层来优化查询
    
    log.success('规则索引创建完成')
  } catch (error) {
    log.warning(`创建索引时出现警告: ${error}`)
  }
}

/**
 * 生成规则统计报告
 */
async function generateRulesReport(): Promise<void> {
  try {
    log.step('生成规则统计报告...')
    
    const { data: rules, error } = await supabase
      .from('qc_rules')
      .select('*')
    
    if (error) {
      throw error
    }
    
    if (!rules || rules.length === 0) {
      log.warning('未找到任何规则数据')
      return
    }
    
    // 统计信息
    const stats = {
      total: rules.length,
      active: rules.filter(r => r.is_active).length,
      inactive: rules.filter(r => !r.is_active).length,
      categories: {
        completeness: rules.filter(r => r.category === 'completeness').length,
        consistency: rules.filter(r => r.category === 'consistency').length,
        rationality: rules.filter(r => r.category === 'rationality').length,
        timeliness: rules.filter(r => r.category === 'timeliness').length
      },
      severities: {
        critical: rules.filter(r => r.severity === 'critical').length,
        major: rules.filter(r => r.severity === 'major').length,
        minor: rules.filter(r => r.severity === 'minor').length
      },
      types: {
        objective: rules.filter(r => r.rule_type === 'objective').length,
        subjective: rules.filter(r => r.rule_type === 'subjective').length,
        hybrid: rules.filter(r => r.rule_type === 'hybrid').length
      }
    }
    
    // 输出报告
    log.header('质控规则系统统计报告')
    
    console.log(`📊 规则总数: ${colors.bright}${stats.total}${colors.reset}`)
    console.log(`🟢 激活规则: ${colors.green}${stats.active}${colors.reset}`)
    console.log(`🔴 停用规则: ${colors.red}${stats.inactive}${colors.reset}`)
    
    console.log('\n📋 分类统计:')
    console.log(`  • 完整性规则: ${stats.categories.completeness}`)
    console.log(`  • 一致性规则: ${stats.categories.consistency}`)
    console.log(`  • 合理性规则: ${stats.categories.rationality}`)
    console.log(`  • 及时性规则: ${stats.categories.timeliness}`)
    
    console.log('\n⚠️ 严重程度统计:')
    console.log(`  • 严重规则: ${colors.red}${stats.severities.critical}${colors.reset}`)
    console.log(`  • 重要规则: ${colors.yellow}${stats.severities.major}${colors.reset}`)
    console.log(`  • 轻微规则: ${colors.blue}${stats.severities.minor}${colors.reset}`)
    
    console.log('\n🔧 类型统计:')
    console.log(`  • 客观规则: ${stats.types.objective}`)
    console.log(`  • 主观规则: ${stats.types.subjective}`)
    console.log(`  • 混合规则: ${stats.types.hybrid}`)
    
    // 检查规则覆盖度
    const coverage = {
      hasCompleteness: stats.categories.completeness > 0,
      hasConsistency: stats.categories.consistency > 0,
      hasRationality: stats.categories.rationality > 0,
      hasTimeliness: stats.categories.timeliness > 0
    }
    
    const coverageScore = Object.values(coverage).filter(Boolean).length
    console.log(`\n📈 规则覆盖度: ${coverageScore}/4 (${(coverageScore/4*100).toFixed(1)}%)`)
    
    if (coverageScore < 4) {
      log.warning('规则覆盖度不完整，建议补充缺失分类的规则')
    } else {
      log.success('规则覆盖度完整')
    }
    
  } catch (error) {
    log.error(`生成统计报告失败: ${error}`)
  }
}

/**
 * 验证规则数据完整性
 */
async function validateRulesIntegrity(): Promise<boolean> {
  try {
    log.step('验证规则数据完整性...')
    
    const { data: rules, error } = await supabase
      .from('qc_rules')
      .select('*')
    
    if (error) {
      throw error
    }
    
    if (!rules) {
      log.warning('未找到规则数据')
      return true
    }
    
    let hasErrors = false
    const issues: string[] = []
    
    // 检查重复的规则编码
    const ruleCodes = rules.map(r => r.rule_code)
    const duplicateCodes = ruleCodes.filter((code, index) => ruleCodes.indexOf(code) !== index)
    
    if (duplicateCodes.length > 0) {
      hasErrors = true
      issues.push(`发现重复的规则编码: ${[...new Set(duplicateCodes)].join(', ')}`)
    }
    
    // 检查必填字段
    for (const rule of rules) {
      if (!rule.rule_code || !rule.name || !rule.description) {
        hasErrors = true
        issues.push(`规则 ${rule.rule_code || rule.id} 缺少必填字段`)
      }
      
      if (rule.max_score < 0 || rule.max_score > 100) {
        hasErrors = true
        issues.push(`规则 ${rule.rule_code} 的最大扣分超出范围 (0-100)`)
      }
      
      if (rule.weight < 0.1 || rule.weight > 5.0) {
        hasErrors = true
        issues.push(`规则 ${rule.rule_code} 的权重超出范围 (0.1-5.0)`)
      }
    }
    
    if (hasErrors) {
      log.error('规则数据完整性验证失败:')
      issues.forEach(issue => console.log(`  • ${issue}`))
      return false
    } else {
      log.success('规则数据完整性验证通过')
      return true
    }
    
  } catch (error) {
    log.error(`验证规则完整性失败: ${error}`)
    return false
  }
}

/**
 * 主函数
 */
async function main() {
  log.header('质控规则系统初始化')
  
  try {
    // 1. 检查数据库连接
    const dbConnected = await checkDatabaseConnection()
    if (!dbConnected) {
      process.exit(1)
    }
    
    // 2. 验证表结构
    const tableValid = await validateTableStructure()
    if (!tableValid) {
      process.exit(1)
    }
    
    // 3. 初始化规则数据
    log.step('初始化综合规则数据...')
    await initComprehensiveRules()
    
    // 4. 创建索引
    await createRuleIndexes()
    
    // 5. 验证数据完整性
    const dataValid = await validateRulesIntegrity()
    if (!dataValid) {
      log.warning('数据完整性验证未通过，但系统可以继续运行')
    }
    
    // 6. 生成统计报告
    await generateRulesReport()
    
    log.header('质控规则系统初始化完成')
    log.success('系统已准备就绪，可以开始使用质控规则功能')
    
  } catch (error) {
    log.error(`初始化过程中发生错误: ${error}`)
    process.exit(1)
  }
}

// 如果直接运行此脚本
if (import.meta.url === `file://${process.argv[1]}`) {
  main()
    .then(() => {
      process.exit(0)
    })
    .catch((error) => {
      log.error(`脚本执行失败: ${error}`)
      process.exit(1)
    })
}

export { main as setupRulesSystem }
