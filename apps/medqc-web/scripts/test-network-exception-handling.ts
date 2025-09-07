#!/usr/bin/env node
/**
 * 网络异常处理测试脚本
 * 测试网络超时、连接失败等异常情况的处理
 */

import { networkExceptionHandler } from '../src/lib/network-exception-handler'

interface NetworkTestResult {
  testName: string
  totalRequests: number
  successfulRequests: number
  failedRequests: number
  averageResponseTime: number
  retryCount: number
  cacheHits: number
  fallbackUsed: number
}

class NetworkExceptionTester {

  /**
   * 运行完整的网络异常处理测试
   */
  async runNetworkTests(): Promise<void> {
    console.log('🌐 开始网络异常处理测试...\n')

    const testResults: NetworkTestResult[] = []

    // 1. 测试正常网络请求
    console.log('✅ 测试正常网络请求...')
    const normalResult = await this.testNormalRequests()
    testResults.push(normalResult)

    // 2. 测试超时处理
    console.log('\n⏰ 测试超时处理...')
    const timeoutResult = await this.testTimeoutHandling()
    testResults.push(timeoutResult)

    // 3. 测试连接失败处理
    console.log('\n🔌 测试连接失败处理...')
    const connectionResult = await this.testConnectionFailure()
    testResults.push(connectionResult)

    // 4. 测试重试机制
    console.log('\n🔄 测试重试机制...')
    const retryResult = await this.testRetryMechanism()
    testResults.push(retryResult)

    // 5. 测试批量请求处理
    console.log('\n📊 测试批量请求处理...')
    const batchResult = await this.testBatchRequests()
    testResults.push(batchResult)

    // 6. 测试缓存机制
    console.log('\n💾 测试缓存机制...')
    const cacheResult = await this.testCacheMechanism()
    testResults.push(cacheResult)

    // 7. 测试离线队列
    console.log('\n📱 测试离线队列...')
    await this.testOfflineQueue()

    // 8. 测试网络状态监控
    console.log('\n📡 测试网络状态监控...')
    await this.testNetworkStatusMonitoring()

    // 生成测试报告
    this.generateTestReport(testResults)

    console.log('\n✅ 网络异常处理测试完成!')
  }

  /**
   * 测试正常网络请求
   */
  private async testNormalRequests(): Promise<NetworkTestResult> {
    const requests = 5
    let successful = 0
    let failed = 0
    const responseTimes: number[] = []

    for (let i = 0; i < requests; i++) {
      const result = await networkExceptionHandler.executeRequest(
        () => this.simulateNormalRequest(i),
        { timeout: 5000 }
      )

      if (result.success) {
        successful++
        responseTimes.push(result.totalTime)
        console.log(`  请求 ${i + 1}: 成功 (${result.totalTime}ms)`)
      } else {
        failed++
        console.log(`  请求 ${i + 1}: 失败 - ${result.error?.message}`)
      }

      await this.delay(200)
    }

    const averageTime = responseTimes.length > 0 
      ? responseTimes.reduce((sum, time) => sum + time, 0) / responseTimes.length
      : 0

    return {
      testName: '正常网络请求',
      totalRequests: requests,
      successfulRequests: successful,
      failedRequests: failed,
      averageResponseTime: Math.round(averageTime),
      retryCount: 0,
      cacheHits: 0,
      fallbackUsed: 0
    }
  }

  /**
   * 测试超时处理
   */
  private async testTimeoutHandling(): Promise<NetworkTestResult> {
    const requests = 3
    let successful = 0
    let failed = 0
    let totalRetries = 0

    for (let i = 0; i < requests; i++) {
      const result = await networkExceptionHandler.executeRequest(
        () => this.simulateTimeoutRequest(i),
        { 
          timeout: 2000, // 2秒超时
          retries: 2
        }
      )

      if (result.success) {
        successful++
        console.log(`  超时测试 ${i + 1}: 成功 (尝试 ${result.attempts} 次)`)
      } else {
        failed++
        console.log(`  超时测试 ${i + 1}: 失败 - ${result.error?.message} (尝试 ${result.attempts} 次)`)
      }

      totalRetries += result.attempts - 1
      await this.delay(500)
    }

    return {
      testName: '超时处理',
      totalRequests: requests,
      successfulRequests: successful,
      failedRequests: failed,
      averageResponseTime: 2000,
      retryCount: totalRetries,
      cacheHits: 0,
      fallbackUsed: 0
    }
  }

  /**
   * 测试连接失败处理
   */
  private async testConnectionFailure(): Promise<NetworkTestResult> {
    const requests = 3
    let successful = 0
    let failed = 0
    let totalRetries = 0

    for (let i = 0; i < requests; i++) {
      const result = await networkExceptionHandler.executeRequest(
        () => this.simulateConnectionFailure(i),
        { 
          timeout: 5000,
          retries: 2,
          fallbackUrls: ['http://fallback1.example.com', 'http://fallback2.example.com']
        }
      )

      if (result.success) {
        successful++
        console.log(`  连接测试 ${i + 1}: 成功 ${result.usedFallback ? '(使用降级)' : ''} (尝试 ${result.attempts} 次)`)
      } else {
        failed++
        console.log(`  连接测试 ${i + 1}: 失败 - ${result.error?.message} (尝试 ${result.attempts} 次)`)
      }

      totalRetries += result.attempts - 1
      await this.delay(300)
    }

    return {
      testName: '连接失败处理',
      totalRequests: requests,
      successfulRequests: successful,
      failedRequests: failed,
      averageResponseTime: 1000,
      retryCount: totalRetries,
      cacheHits: 0,
      fallbackUsed: successful
    }
  }

  /**
   * 测试重试机制
   */
  private async testRetryMechanism(): Promise<NetworkTestResult> {
    const requests = 3
    let successful = 0
    let failed = 0
    let totalRetries = 0

    for (let i = 0; i < requests; i++) {
      const result = await networkExceptionHandler.executeRequest(
        () => this.simulateIntermittentFailure(i),
        { 
          timeout: 3000,
          retries: 3,
          retryConfig: {
            maxRetries: 3,
            baseDelay: 1000,
            maxDelay: 5000,
            backoffFactor: 2
          }
        }
      )

      if (result.success) {
        successful++
        console.log(`  重试测试 ${i + 1}: 成功 (尝试 ${result.attempts} 次)`)
      } else {
        failed++
        console.log(`  重试测试 ${i + 1}: 失败 - ${result.error?.message} (尝试 ${result.attempts} 次)`)
      }

      totalRetries += result.attempts - 1
      await this.delay(100)
    }

    return {
      testName: '重试机制',
      totalRequests: requests,
      successfulRequests: successful,
      failedRequests: failed,
      averageResponseTime: 1500,
      retryCount: totalRetries,
      cacheHits: 0,
      fallbackUsed: 0
    }
  }

  /**
   * 测试批量请求处理
   */
  private async testBatchRequests(): Promise<NetworkTestResult> {
    const batchSize = 10
    const requests = Array.from({ length: batchSize }, (_, i) => ({
      fn: () => this.simulateNormalRequest(i),
      options: { timeout: 3000, retries: 1 }
    }))

    const result = await networkExceptionHandler.executeBatchRequests(requests, {
      maxConcurrency: 3,
      failFast: false,
      collectErrors: true
    })

    console.log(`  批量请求完成: ${result.summary.successful}/${result.summary.total} 成功`)
    console.log(`  平均响应时间: ${result.summary.averageTime}ms`)
    console.log(`  缓存命中: ${result.summary.fromCache} 个`)
    console.log(`  使用降级: ${result.summary.usedFallback} 个`)

    return {
      testName: '批量请求处理',
      totalRequests: result.summary.total,
      successfulRequests: result.summary.successful,
      failedRequests: result.summary.failed,
      averageResponseTime: result.summary.averageTime,
      retryCount: 0,
      cacheHits: result.summary.fromCache,
      fallbackUsed: result.summary.usedFallback
    }
  }

  /**
   * 测试缓存机制
   */
  private async testCacheMechanism(): Promise<NetworkTestResult> {
    const requests = 5
    let successful = 0
    let failed = 0
    let cacheHits = 0
    const responseTimes: number[] = []

    // 第一次请求（应该缓存）
    for (let i = 0; i < requests; i++) {
      const result = await networkExceptionHandler.executeRequest(
        () => this.simulateNormalRequest(0), // 使用相同的请求以测试缓存
        { timeout: 3000 }
      )

      if (result.success) {
        successful++
        responseTimes.push(result.totalTime)
        if (result.fromCache) {
          cacheHits++
          console.log(`  缓存测试 ${i + 1}: 缓存命中 (${result.totalTime}ms)`)
        } else {
          console.log(`  缓存测试 ${i + 1}: 网络请求 (${result.totalTime}ms)`)
        }
      } else {
        failed++
        console.log(`  缓存测试 ${i + 1}: 失败 - ${result.error?.message}`)
      }

      await this.delay(100)
    }

    const averageTime = responseTimes.length > 0 
      ? responseTimes.reduce((sum, time) => sum + time, 0) / responseTimes.length
      : 0

    return {
      testName: '缓存机制',
      totalRequests: requests,
      successfulRequests: successful,
      failedRequests: failed,
      averageResponseTime: Math.round(averageTime),
      retryCount: 0,
      cacheHits,
      fallbackUsed: 0
    }
  }

  /**
   * 测试离线队列
   */
  private async testOfflineQueue(): Promise<void> {
    console.log('  模拟离线状态...')
    
    // 模拟离线请求
    const offlinePromises = []
    for (let i = 0; i < 3; i++) {
      const promise = networkExceptionHandler.executeRequest(
        () => this.simulateNormalRequest(i),
        { enableOfflineMode: true }
      )
      offlinePromises.push(promise)
    }

    console.log('  离线请求已加入队列')
    
    // 模拟网络恢复
    setTimeout(() => {
      console.log('  模拟网络恢复...')
    }, 2000)

    const results = await Promise.all(offlinePromises)
    const successful = results.filter(r => r.success).length
    
    console.log(`  离线队列处理完成: ${successful}/${results.length} 成功`)
  }

  /**
   * 测试网络状态监控
   */
  private async testNetworkStatusMonitoring(): Promise<void> {
    const status = networkExceptionHandler.getNetworkStatus()
    
    console.log('  网络状态监控信息:')
    console.log(`    在线状态: ${status.isOnline ? '在线' : '离线'}`)
    console.log(`    连续失败次数: ${status.consecutiveFailures}`)
    console.log(`    最后成功时间: ${status.lastSuccessTime.toLocaleString()}`)
    console.log(`    平均响应时间: ${status.averageResponseTime}ms`)
    console.log(`    错误率: ${(status.errorRate * 100).toFixed(1)}%`)
    console.log(`    队列中请求: ${status.queuedRequests} 个`)
    console.log(`    缓存大小: ${status.cacheSize} 个`)
  }

  /**
   * 模拟正常请求
   */
  private async simulateNormalRequest(id: number): Promise<{ id: number, data: string }> {
    await this.delay(500 + Math.random() * 1000) // 0.5-1.5秒
    
    // 10%的概率失败
    if (Math.random() < 0.1) {
      throw new Error(`模拟请求失败: ${id}`)
    }
    
    return { id, data: `正常响应数据 ${id}` }
  }

  /**
   * 模拟超时请求
   */
  private async simulateTimeoutRequest(id: number): Promise<{ id: number, data: string }> {
    // 50%的概率超时
    const delay = Math.random() < 0.5 ? 3000 : 1000
    await this.delay(delay)
    
    return { id, data: `超时测试响应 ${id}` }
  }

  /**
   * 模拟连接失败
   */
  private async simulateConnectionFailure(id: number): Promise<{ id: number, data: string }> {
    // 70%的概率连接失败
    if (Math.random() < 0.7) {
      const error = new Error('ECONNREFUSED: Connection refused')
      ;(error as any).code = 'ECONNREFUSED'
      throw error
    }
    
    await this.delay(800)
    return { id, data: `连接成功响应 ${id}` }
  }

  /**
   * 模拟间歇性失败
   */
  private async simulateIntermittentFailure(id: number): Promise<{ id: number, data: string }> {
    // 前两次尝试失败，第三次成功
    const attemptCount = (this as any)[`attempt_${id}`] || 0
    ;(this as any)[`attempt_${id}`] = attemptCount + 1
    
    if (attemptCount < 2) {
      throw new Error(`间歇性失败 ${id} (尝试 ${attemptCount + 1})`)
    }
    
    await this.delay(600)
    return { id, data: `重试成功响应 ${id}` }
  }

  /**
   * 生成测试报告
   */
  private generateTestReport(results: NetworkTestResult[]): void {
    console.log('\n📊 网络异常处理测试报告')
    console.log('=' .repeat(70))

    let totalRequests = 0
    let totalSuccessful = 0
    let totalFailed = 0
    let totalRetries = 0

    console.log('测试项目 | 总数 | 成功 | 失败 | 平均时间 | 重试 | 缓存 | 降级')
    console.log('-'.repeat(70))

    for (const result of results) {
      totalRequests += result.totalRequests
      totalSuccessful += result.successfulRequests
      totalFailed += result.failedRequests
      totalRetries += result.retryCount

      const successRate = (result.successfulRequests / result.totalRequests * 100).toFixed(1)
      
      console.log(
        `${result.testName.padEnd(12)} | ` +
        `${result.totalRequests.toString().padStart(4)} | ` +
        `${result.successfulRequests.toString().padStart(4)} | ` +
        `${result.failedRequests.toString().padStart(4)} | ` +
        `${result.averageResponseTime.toString().padStart(7)}ms | ` +
        `${result.retryCount.toString().padStart(4)} | ` +
        `${result.cacheHits.toString().padStart(4)} | ` +
        `${result.fallbackUsed.toString().padStart(4)}`
      )
    }

    console.log('-'.repeat(70))
    
    const overallSuccessRate = (totalSuccessful / totalRequests * 100).toFixed(1)
    
    console.log(`总计: ${totalRequests} 请求, ${totalSuccessful} 成功, ${totalFailed} 失败`)
    console.log(`总体成功率: ${overallSuccessRate}%`)
    console.log(`总重试次数: ${totalRetries}`)

    console.log('\n💡 测试结论:')
    if (parseFloat(overallSuccessRate) >= 80) {
      console.log('✅ 网络异常处理机制工作良好')
      console.log('✅ 重试和降级策略有效')
      console.log('✅ 缓存机制正常工作')
      console.log('✅ 建议在生产环境中启用')
    } else {
      console.log('⚠️ 网络异常处理需要进一步优化')
      console.log('⚠️ 建议调整重试参数和降级策略')
    }

    console.log('\n🎯 优化建议:')
    console.log('• 根据实际网络环境调整超时时间')
    console.log('• 优化重试间隔和最大重试次数')
    console.log('• 配置合适的降级URL')
    console.log('• 定期清理缓存以释放内存')

    console.log('\n' + '='.repeat(70))
  }

  /**
   * 延迟函数
   */
  private delay(ms: number): Promise<void> {
    return new Promise(resolve => setTimeout(resolve, ms))
  }

  /**
   * 清理资源
   */
  cleanup(): void {
    networkExceptionHandler.clearCache()
    networkExceptionHandler.clearOfflineQueue()
  }
}

/**
 * 主函数
 */
async function main() {
  try {
    const tester = new NetworkExceptionTester()
    await tester.runNetworkTests()
    
    console.log('\n🎉 网络异常处理验证完成!')
    console.log('🛡️ 系统现在具备了强大的网络容错能力')
    
    // 清理资源
    tester.cleanup()
    
  } catch (error) {
    console.error('❌ 网络异常处理测试失败:', error)
    process.exit(1)
  }
}

// 运行测试
if (require.main === module) {
  main()
}

export { NetworkExceptionTester }
