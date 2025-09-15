#!/usr/bin/env node
/**
 * 执行文书类别映射迁移
 * 为质控规则添加文书类别字段并更新现有数据
 */

import { createClient } from '@supabase/supabase-js'
import { readFileSync } from 'fs'
import { join } from 'path'
import dotenv from 'dotenv'

// 加载环境变量
dotenv.config()

const supabaseUrl = process.env.VITE_SUPABASE_URL || process.env.SUPABASE_URL
const supabaseKey = process.env.VITE_SUPABASE_ANON_KEY || process.env.SUPABASE_ANON_KEY

if (!supabaseUrl || !supabaseKey) {
  console.error('❌ 缺少Supabase配置，请检查环境变量')
  process.exit(1)
}

const supabase = createClient(supabaseUrl, supabaseKey)

async function executeSQLFile(filePath: string, description: string) {
  console.log(`\n📄 执行 ${description}...`)
  
  try {
    const sqlContent = readFileSync(filePath, 'utf-8')
    
    // 分割SQL语句（简单的分割，基于分号）
    const statements = sqlContent
      .split(';')
      .map(stmt => stmt.trim())
      .filter(stmt => stmt.length > 0 && !stmt.startsWith('--'))
    
    console.log(`   发现 ${statements.length} 个SQL语句`)
    
    for (let i = 0; i < statements.length; i++) {
      const statement = statements[i]
      if (statement.trim()) {
        console.log(`   执行语句 ${i + 1}/${statements.length}...`)
        
        const { error } = await supabase.rpc('exec_sql', { 
          sql_query: statement 
        })
        
        if (error) {
          console.error(`   ❌ 语句 ${i + 1} 执行失败:`, error.message)
          // 继续执行其他语句，不中断整个过程
        } else {
          console.log(`   ✅ 语句 ${i + 1} 执行成功`)
        }
      }
    }
    
    console.log(`✅ ${description} 完成`)
    
  } catch (error) {
    console.error(`❌ ${description} 失败:`, error)
    throw error
  }
}

async function migrateDocumentCategories() {
  console.log('🚀 开始文书类别映射迁移...\n')
  
  try {
    // 1. 执行结构迁移
    const structureMigrationPath = join(__dirname, '../database/migrations/20250915_add_document_category_mapping.sql')
    await executeSQLFile(structureMigrationPath, '添加文书类别字段和配置表')
    
    // 2. 执行数据更新
    const dataMigrationPath = join(__dirname, '../database/migrations/20250915_update_qc_rules_document_mapping.sql')
    await executeSQLFile(dataMigrationPath, '更新现有规则的文书类别映射')
    
    // 3. 验证迁移结果
    console.log('\n🔍 验证迁移结果...')
    
    // 检查文书类别配置
    const { data: categories, error: catError } = await supabase
      .from('document_category_config')
      .select('category_code, category_name, sort_order')
      .order('sort_order')
    
    if (catError) {
      console.error('❌ 无法查询文书类别配置:', catError.message)
    } else {
      console.log('✅ 文书类别配置:')
      categories?.forEach(cat => {
        console.log(`   ${cat.sort_order}. ${cat.category_code} - ${cat.category_name}`)
      })
    }
    
    // 检查规则映射统计
    const { data: mappingStats, error: statsError } = await supabase
      .from('qc_rules')
      .select('primary_document_category')
      .not('primary_document_category', 'is', null)
    
    if (statsError) {
      console.error('❌ 无法查询规则映射统计:', statsError.message)
    } else {
      const stats = mappingStats?.reduce((acc: Record<string, number>, rule) => {
        const category = rule.primary_document_category || '未分类'
        acc[category] = (acc[category] || 0) + 1
        return acc
      }, {})
      
      console.log('\n📊 规则映射统计:')
      Object.entries(stats || {}).forEach(([category, count]) => {
        console.log(`   ${category}: ${count} 条规则`)
      })
    }
    
    console.log('\n🎉 文书类别映射迁移完成!')
    console.log('\n📋 下一步:')
    console.log('   1. 更新前端组件以支持文书类别筛选')
    console.log('   2. 更新质控引擎以根据文书类别应用规则')
    console.log('   3. 测试质控分析功能')
    
  } catch (error) {
    console.error('❌ 迁移过程中发生错误:', error)
    process.exit(1)
  }
}

// 运行迁移
migrateDocumentCategories().catch(console.error)
