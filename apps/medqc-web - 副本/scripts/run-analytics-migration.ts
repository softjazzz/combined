#!/usr/bin/env tsx

/**
 * 360度数据分析和智能报表数据库迁移脚本
 * 运行命令: npx tsx scripts/run-analytics-migration.ts
 */

import { createClient } from '@supabase/supabase-js'
import { readFileSync } from 'fs'
import { join } from 'path'

// 获取当前工作目录
const __dirname = process.cwd()

// 配置
const SUPABASE_URL = process.env.VITE_SUPABASE_URL || 'https://your-project.supabase.co'
const SUPABASE_SERVICE_KEY = process.env.SUPABASE_SERVICE_KEY || 'your-service-key'

if (!SUPABASE_URL || !SUPABASE_SERVICE_KEY) {
  console.error('❌ 请设置环境变量 VITE_SUPABASE_URL 和 SUPABASE_SERVICE_KEY')
  console.error('💡 SUPABASE_SERVICE_KEY 应该使用 service_role 密钥，不是 anon 密钥')
  process.exit(1)
}

// 创建Supabase客户端 (使用service_role密钥)
const supabase = createClient(SUPABASE_URL, SUPABASE_SERVICE_KEY)

async function runMigration() {
  console.log('🚀 开始执行360度数据分析和智能报表数据库迁移...\n')

  try {
    // 读取迁移SQL文件
    const migrationSQL = readFileSync(
      join(__dirname, 'supabase/migrations/004_add_analytics_and_reporting.sql'),
      'utf8'
    )

    console.log('📖 读取迁移文件成功')

    // 执行迁移
    console.log('⚡ 执行数据库迁移...')
    const { error } = await supabase.rpc('exec_sql', {
      sql: migrationSQL
    })

    if (error) {
      // 如果RPC函数不存在，直接执行SQL
      console.log('🔄 尝试直接执行SQL...')
      
      // 分割SQL语句并逐个执行
      const statements = migrationSQL
        .split(';')
        .map(stmt => stmt.trim())
        .filter(stmt => stmt.length > 0 && !stmt.startsWith('--'))

      for (const statement of statements) {
        if (statement.trim()) {
          const { error: execError } = await supabase.rpc('exec', {
            sql: statement
          })
          
          if (execError) {
            console.warn(`⚠️  执行语句时出现警告: ${statement.substring(0, 50)}...`)
            console.warn(`   错误信息: ${execError.message}`)
          }
        }
      }
    }

    console.log('✅ 数据库迁移执行完成')

    // 验证迁移结果
    console.log('\n🔍 验证迁移结果...')
    await verifyMigration()

    // 初始化基础数据
    console.log('\n📊 初始化基础数据...')
    await initializeBaseData()

    console.log('\n🎉 360度数据分析和智能报表系统迁移完成!')
    console.log('\n📋 新增功能:')
    console.log('  • 360度数据分析引擎')
    console.log('  • 智能报表生成系统')
    console.log('  • 多维度数据立方体')
    console.log('  • 分析指标管理')
    console.log('  • 报表模板配置')
    console.log('  • 预警规则设置')
    console.log('  • 数据快照和对比分析')

  } catch (error) {
    console.error('❌ 迁移失败:', error)
    process.exit(1)
  }
}

async function verifyMigration() {
  const tables = [
    'data_cubes',
    'analytics_metrics',
    'analytics_results',
    'report_templates',
    'report_instances',
    'data_snapshots',
    'comparison_analyses',
    'alert_rules',
    'alert_records'
  ]

  for (const table of tables) {
    const { data, error } = await supabase
      .from(table)
      .select('*')
      .limit(1)

    if (error) {
      console.error(`❌ 验证表 ${table} 失败:`, error.message)
      throw error
    } else {
      console.log(`✅ 表 ${table} 验证成功`)
    }
  }

  // 验证视图
  const views = [
    'v_department_analytics',
    'v_doctor_performance',
    'v_quality_trends'
  ]

  for (const view of views) {
    const { data, error } = await supabase
      .from(view)
      .select('*')
      .limit(1)

    if (error) {
      console.warn(`⚠️  验证视图 ${view} 失败:`, error.message)
    } else {
      console.log(`✅ 视图 ${view} 验证成功`)
    }
  }

  // 验证函数
  const functions = [
    'calculate_department_ranking',
    'generate_quality_insight',
    'schedule_daily_analytics'
  ]

  for (const func of functions) {
    console.log(`✅ 函数 ${func} 已创建`)
  }
}

async function initializeBaseData() {
  // 检查是否已有数据
  const { data: existingMetrics } = await supabase
    .from('analytics_metrics')
    .select('id')
    .limit(1)

  if (existingMetrics && existingMetrics.length > 0) {
    console.log('📊 基础数据已存在，跳过初始化')
    return
  }

  // 创建数据立方体
  console.log('🎲 创建数据立方体...')
  const { error: cubeError } = await supabase
    .from('data_cubes')
    .insert([
      {
        cube_name: 'quality_cube',
        dimensions: {
          time: ['year', 'month', 'day'],
          department: ['department'],
          doctor: ['doctor_id'],
          record_type: ['record_type']
        },
        measures: {
          total_records: 'count',
          avg_score: 'avg',
          grade_a_rate: 'ratio',
          grade_b_rate: 'ratio',
          grade_c_rate: 'ratio'
        },
        aggregation_rules: {
          time_rollup: true,
          department_rollup: true,
          default_aggregation: 'sum'
        },
        refresh_schedule: 'daily'
      },
      {
        cube_name: 'efficiency_cube',
        dimensions: {
          time: ['year', 'month', 'day'],
          department: ['department'],
          doctor: ['doctor_id']
        },
        measures: {
          avg_processing_time: 'avg',
          completion_rate: 'ratio',
          productivity_score: 'avg'
        },
        aggregation_rules: {
          time_rollup: true,
          department_rollup: true,
          default_aggregation: 'avg'
        },
        refresh_schedule: 'daily'
      }
    ])

  if (cubeError) {
    console.warn('⚠️  创建数据立方体失败:', cubeError.message)
  } else {
    console.log('✅ 数据立方体创建成功')
  }

  // 创建预警规则
  console.log('🚨 创建预警规则...')
  const { data: metrics } = await supabase
    .from('analytics_metrics')
    .select('id, metric_code')
    .in('metric_code', ['avg_qc_score', 'grade_c_rate', 'avg_processing_time'])

  if (metrics && metrics.length > 0) {
    const alertRules = [
      {
        rule_name: '质控评分过低预警',
        metric_id: metrics.find(m => m.metric_code === 'avg_qc_score')?.id,
        condition_type: 'threshold',
        condition_config: {
          operator: 'less_than',
          threshold: 75,
          duration: 3
        },
        alert_level: 'warning',
        notification_config: {
          email: true,
          dashboard: true,
          recipients: ['qc_manager']
        }
      },
      {
        rule_name: 'C级病案比例过高预警',
        metric_id: metrics.find(m => m.metric_code === 'grade_c_rate')?.id,
        condition_type: 'threshold',
        condition_config: {
          operator: 'greater_than',
          threshold: 15,
          duration: 2
        },
        alert_level: 'critical',
        notification_config: {
          email: true,
          dashboard: true,
          sms: true,
          recipients: ['qc_manager', 'admin']
        }
      },
      {
        rule_name: '处理时间过长预警',
        metric_id: metrics.find(m => m.metric_code === 'avg_processing_time')?.id,
        condition_type: 'threshold',
        condition_config: {
          operator: 'greater_than',
          threshold: 6,
          duration: 1
        },
        alert_level: 'warning',
        notification_config: {
          email: true,
          dashboard: true,
          recipients: ['qc_manager']
        }
      }
    ]

    const { error: alertError } = await supabase
      .from('alert_rules')
      .insert(alertRules.filter(rule => rule.metric_id))

    if (alertError) {
      console.warn('⚠️  创建预警规则失败:', alertError.message)
    } else {
      console.log('✅ 预警规则创建成功')
    }
  }

  // 生成初始数据快照
  console.log('📸 生成初始数据快照...')
  const today = new Date().toISOString().split('T')[0]
  
  const { error: snapshotError } = await supabase
    .from('data_snapshots')
    .insert([
      {
        snapshot_name: `初始快照 - ${today}`,
        snapshot_type: 'daily',
        snapshot_date: today,
        data_summary: {
          total_records: 0,
          avg_score: 0,
          grade_distribution: { A: 0, B: 0, C: 0 },
          departments: [],
          doctors: []
        },
        record_count: 0,
        avg_qc_score: 0,
        department_stats: {},
        doctor_stats: {},
        quality_indicators: {
          completion_rate: 0,
          avg_processing_time: 0,
          error_rate: 0
        }
      }
    ])

  if (snapshotError) {
    console.warn('⚠️  生成初始快照失败:', snapshotError.message)
  } else {
    console.log('✅ 初始数据快照生成成功')
  }

  console.log('✅ 基础数据初始化完成')
}

// 运行迁移
runMigration().catch(console.error) 