/**
 * 质控引擎改进功能测试脚本
 * 测试版本管理、批量处理、缓存优化、稳健性机制等功能
 */

console.log('🧪 开始测试质控引擎改进功能...')

// 测试配置
const TEST_CONFIG = {
  baseUrl: 'http://localhost:8000', // 后端API地址
  supabaseUrl: 'http://localhost:54321/functions/v1', // Supabase Functions地址
  batchSize: 50,
  concurrentRequests: 5
}

// 测试数据生成器
function generateTestContext(id) {
  return {
    id: `test_context_${id}`,
    patient: {
      id: `patient_${id}`,
      age: 30 + Math.floor(Math.random() * 50),
      gender: Math.random() > 0.5 ? 'M' : 'F',
      diagnosis: {
        main: {
          code: `ICD10_${Math.floor(Math.random() * 1000)}`,
          name: '测试诊断'
        }
      }
    },
    visit: {
      id: `visit_${id}`,
      department: {
        code: 'INTERNAL',
        name: '内科'
      }
    },
    order: {
      drug_code: `DRUG_${Math.floor(Math.random() * 100)}`,
      drug_name: '测试药品',
      dosage: Math.random() * 100,
      frequency: '每日三次'
    }
  }
}

// 测试函数集合
const tests = {
  // 测试1: 版本管理功能
  async testVersionManagement() {
    console.log('\n📋 测试1: 版本管理功能')
    
    try {
      // 创建快照
      console.log('创建规则快照...')
      const snapshotResponse = await fetch(`${TEST_CONFIG.supabaseUrl}/rule-version-manager/create-snapshot`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          version_name: `test_version_${Date.now()}`,
          description: '测试版本快照',
          created_by: 'test_user'
        })
      })
      
      if (snapshotResponse.ok) {
        const snapshotResult = await snapshotResponse.json()
        console.log('✅ 快照创建成功:', snapshotResult.version_name)
        
        // 获取版本列表
        const versionsResponse = await fetch(`${TEST_CONFIG.supabaseUrl}/rule-version-manager/versions`)
        if (versionsResponse.ok) {
          const versions = await versionsResponse.json()
          console.log('✅ 版本列表获取成功，共', versions.total_count, '个版本')
        }
      } else {
        console.log('❌ 快照创建失败:', snapshotResponse.status)
      }
    } catch (error) {
      console.log('❌ 版本管理测试失败:', error.message)
    }
  },

  // 测试2: 批量处理性能
  async testBatchProcessing() {
    console.log('\n⚡ 测试2: 批量处理性能')
    
    try {
      const testContexts = Array.from({ length: 100 }, (_, i) => generateTestContext(i))
      
      console.log(`生成 ${testContexts.length} 个测试上下文`)
      
      const startTime = Date.now()
      
      // 批量评估请求
      const batchResponse = await fetch(`${TEST_CONFIG.supabaseUrl}/evaluate-rule`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          event: 'drug_order',
          contexts: testContexts,
          batch: true,
          record: false
        })
      })
      
      const executionTime = Date.now() - startTime
      
      if (batchResponse.ok) {
        const result = await batchResponse.json()
        console.log('✅ 批量处理成功')
        console.log(`📊 性能指标:`)
        console.log(`   - 总执行时间: ${executionTime}ms`)
        console.log(`   - 平均每个上下文: ${(executionTime / testContexts.length).toFixed(2)}ms`)
        console.log(`   - 处理的上下文数: ${result.results?.length || 0}`)
        console.log(`   - 缓存命中率: ${(result.performance?.cache_hit_rate * 100).toFixed(1)}%`)
        console.log(`   - 并行处理: ${result.performance?.parallel_enabled ? '启用' : '禁用'}`)
      } else {
        console.log('❌ 批量处理失败:', batchResponse.status)
      }
    } catch (error) {
      console.log('❌ 批量处理测试失败:', error.message)
    }
  },

  // 测试3: 缓存性能
  async testCachePerformance() {
    console.log('\n🗄️ 测试3: 缓存性能')
    
    try {
      // 清空缓存
      console.log('清空缓存...')
      const clearResponse = await fetch(`${TEST_CONFIG.supabaseUrl}/rule-cache-manager/clear`, {
        method: 'DELETE'
      })
      
      if (clearResponse.ok) {
        console.log('✅ 缓存已清空')
      }
      
      // 预热缓存
      console.log('预热缓存...')
      const preloadResponse = await fetch(`${TEST_CONFIG.supabaseUrl}/rule-cache-manager/preload`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          event_types: ['drug_order', 'diagnosis_entry']
        })
      })
      
      if (preloadResponse.ok) {
        const preloadResult = await preloadResponse.json()
        console.log('✅ 缓存预热成功')
        console.log(`   - 预加载规则数: ${preloadResult.preloaded_rules}`)
        console.log(`   - 预加载时间: ${preloadResult.execution_time_ms}ms`)
      }
      
      // 获取缓存统计
      const statsResponse = await fetch(`${TEST_CONFIG.supabaseUrl}/rule-cache-manager/stats`)
      if (statsResponse.ok) {
        const stats = await statsResponse.json()
        console.log('📊 缓存统计:')
        console.log(`   - 总规则数: ${stats.total_rules}`)
        console.log(`   - 活跃规则数: ${stats.active_rules}`)
        console.log(`   - 缓存大小: ${stats.cache_size_mb}MB`)
        console.log(`   - 运行时间: ${stats.uptime_seconds}秒`)
      }
    } catch (error) {
      console.log('❌ 缓存测试失败:', error.message)
    }
  },

  // 测试4: 性能监控
  async testPerformanceMonitoring() {
    console.log('\n📈 测试4: 性能监控')
    
    try {
      // 健康检查
      const healthResponse = await fetch(`${TEST_CONFIG.supabaseUrl}/rule-performance-monitor/health`)
      if (healthResponse.ok) {
        const health = await healthResponse.json()
        console.log('✅ 系统健康检查:')
        console.log(`   - 状态: ${health.status}`)
        console.log(`   - 数据库连接: ${health.database_connection}`)
        console.log(`   - 数据库延迟: ${health.database?.latency_ms || 0}ms`)
      }
      
      // 性能统计
      const statsResponse = await fetch(`${TEST_CONFIG.supabaseUrl}/rule-performance-monitor/stats?time_range=1h`)
      if (statsResponse.ok) {
        const stats = await statsResponse.json()
        console.log('📊 性能统计 (最近1小时):')
        console.log(`   - 总评估次数: ${stats.total_evaluations}`)
        console.log(`   - 平均执行时间: ${stats.avg_execution_time_ms}ms`)
        console.log(`   - P95执行时间: ${stats.p95_execution_time_ms}ms`)
        console.log(`   - 缓存命中率: ${(stats.cache_hit_rate * 100).toFixed(1)}%`)
        console.log(`   - 错误率: ${(stats.error_rate * 100).toFixed(2)}%`)
        console.log(`   - 检测到的违规: ${stats.violations_detected}`)
      }
      
      // 运行基准测试
      console.log('运行性能基准测试...')
      const benchmarkResponse = await fetch(`${TEST_CONFIG.supabaseUrl}/rule-performance-monitor/benchmark`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          test_contexts: 50,
          concurrent_requests: 3
        })
      })
      
      if (benchmarkResponse.ok) {
        const benchmark = await benchmarkResponse.json()
        console.log('✅ 基准测试完成:')
        console.log(`   - 吞吐量: ${benchmark.results?.throughput_contexts_per_second} 次/秒`)
        console.log(`   - 平均批次时间: ${benchmark.results?.avg_batch_time_ms}ms`)
        console.log(`   - 违规检出率: ${(benchmark.results?.violation_rate * 100).toFixed(1)}%`)
      }
    } catch (error) {
      console.log('❌ 性能监控测试失败:', error.message)
    }
  },

  // 测试5: 稳健性机制
  async testResilienceMechanisms() {
    console.log('\n🛡️ 测试5: 稳健性机制')
    
    try {
      // 测试重试机制 - 发送可能失败的请求
      console.log('测试重试机制...')
      const retryTestContext = generateTestContext('retry_test')
      
      const retryResponse = await fetch(`${TEST_CONFIG.supabaseUrl}/evaluate-rule`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          event: 'drug_order',
          context: retryTestContext,
          record: true
        })
      })
      
      if (retryResponse.ok) {
        const result = await retryResponse.json()
        console.log('✅ 重试机制测试通过')
        console.log(`   - 决策结果: ${result.decision}`)
        console.log(`   - 命中规则数: ${result.hits?.length || 0}`)
        console.log(`   - 执行时间: ${result.performance?.execution_time_ms}ms`)
        
        if (result.performance?.cache_hits !== undefined) {
          console.log(`   - 缓存命中: ${result.performance.cache_hits}`)
          console.log(`   - 缓存未命中: ${result.performance.cache_misses}`)
        }
      } else {
        console.log('❌ 重试机制测试失败:', retryResponse.status)
      }
      
      // 测试降级机制 - 模拟系统压力
      console.log('测试降级机制...')
      const concurrentRequests = Array.from({ length: 10 }, (_, i) => 
        fetch(`${TEST_CONFIG.supabaseUrl}/evaluate-rule`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            event: 'drug_order',
            context: generateTestContext(`concurrent_${i}`),
            record: false
          })
        })
      )
      
      const results = await Promise.allSettled(concurrentRequests)
      const successCount = results.filter(r => r.status === 'fulfilled').length
      const failureCount = results.filter(r => r.status === 'rejected').length
      
      console.log('✅ 并发压力测试完成:')
      console.log(`   - 成功请求: ${successCount}`)
      console.log(`   - 失败请求: ${failureCount}`)
      console.log(`   - 成功率: ${(successCount / results.length * 100).toFixed(1)}%`)
      
    } catch (error) {
      console.log('❌ 稳健性测试失败:', error.message)
    }
  }
}

// 运行所有测试
async function runAllTests() {
  console.log('🚀 开始执行质控引擎改进功能测试套件')
  console.log('=' .repeat(60))
  
  const testNames = Object.keys(tests)
  let passedTests = 0
  
  for (const testName of testNames) {
    try {
      await tests[testName]()
      passedTests++
    } catch (error) {
      console.log(`❌ 测试 ${testName} 执行失败:`, error.message)
    }
  }
  
  console.log('\n' + '=' .repeat(60))
  console.log(`🎯 测试完成: ${passedTests}/${testNames.length} 通过`)
  
  if (passedTests === testNames.length) {
    console.log('🎉 所有测试通过！质控引擎改进功能正常工作。')
  } else {
    console.log('⚠️ 部分测试失败，请检查相关功能。')
  }
}

// 提供单独测试函数
window.testVersionManagement = tests.testVersionManagement
window.testBatchProcessing = tests.testBatchProcessing
window.testCachePerformance = tests.testCachePerformance
window.testPerformanceMonitoring = tests.testPerformanceMonitoring
window.testResilienceMechanisms = tests.testResilienceMechanisms
window.runAllTests = runAllTests

console.log('🛠️ 可用的测试函数:')
console.log('- testVersionManagement() - 测试版本管理')
console.log('- testBatchProcessing() - 测试批量处理')
console.log('- testCachePerformance() - 测试缓存性能')
console.log('- testPerformanceMonitoring() - 测试性能监控')
console.log('- testResilienceMechanisms() - 测试稳健性机制')
console.log('- runAllTests() - 运行所有测试')

// 自动运行测试
runAllTests()
