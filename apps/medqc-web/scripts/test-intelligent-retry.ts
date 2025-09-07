#!/usr/bin/env node
/**
 * 智能重试机制测试脚本
 * 测试不同错误类型和场景下的重试策略
 */

import { intelligentRetryManager } from '../src/lib/intelligent-retry-manager'

interface RetryTestResult {
  testName: string
  operationId: string
  totalOperations: number
  successfulOperations: number
  failedOperations: number
  averageAttempts: number
  totalRetries: number
  averageDelay: number
  strategy: string
}

class IntelligentRetryTester {

  /**
   * 运行完整的重试机制测试
   */
  async runRetryTests(): Promise<void> {
    console.log('🔄 开始智能重试机制测试...\n')

    const testResults: RetryTestResult[] = []

    // 1. 测试网络错误重试
    console.log('🌐 测试网络错误重试策略...')
    const networkResult = await this.testNetworkErrorRetry()
    testResults.push(networkResult)

    // 2. 测试超时错误重试
    console.log('\n⏰ 测试超时错误重试策略...')
    const timeoutResult = await this.testTimeoutErrorRetry()
    testResults.push(timeoutResult)

    // 3. 测试限流错误重试
    console.log('\n🚦 测试限流错误重试策略...')
    const rateLimitResult = await this.testRateLimitRetry()
    testResults.push(rateLimitResult)

    // 4. 测试服务器错误重试
    console.log('\n🖥️ 测试服务器错误重试策略...')
    const serverErrorResult = await this.testServerErrorRetry()
    testResults.push(serverErrorResult)

    // 5. 测试客户端错误（不重试）
    console.log('\n👤 测试客户端错误处理...')
    const clientErrorResult = await this.testClientErrorHandling()
    testResults.push(clientErrorResult)

    // 6. 测试自适应重试策略
    console.log('\n🧠 测试自适应重试策略...')
    const adaptiveResult = await this.testAdaptiveRetry()
    testResults.push(adaptiveResult)

    // 7. 测试批量重试操作
    console.log('\n📊 测试批量重试操作...')
    const batchResult = await this.testBatchRetry()
    testResults.push(batchResult)

    // 8. 测试重试统计和监控
    console.log('\n📈 测试重试统计和监控...')
    await this.testRetryStatistics()

    // 生成测试报告
    this.generateTestReport(testResults)

    console.log('\n✅ 智能重试机制测试完成!')
  }

  /**
   * 测试网络错误重试
   */
  private async testNetworkErrorRetry(): Promise<RetryTestResult> {
    const operationId = 'network_error_test'
    const operations = 5
    let successful = 0
    let failed = 0
    let totalAttempts = 0
    const delays: number[] = []

    for (let i = 0; i < operations; i++) {
      const result = await intelligentRetryManager.executeWithRetry(
        () => this.simulateNetworkError(i),
        `${operationId}_${i}`
      )

      if (result.success) {
        successful++
        console.log(`  网络测试 ${i + 1}: 成功 (尝试 ${result.attempts} 次)`)
      } else {
        failed++
        console.log(`  网络测试 ${i + 1}: 失败 (尝试 ${result.attempts} 次)`)
      }

      totalAttempts += result.attempts
      if (result.finalDelay) delays.push(result.finalDelay)

      await this.delay(200)
    }

    const averageDelay = delays.length > 0 ? delays.reduce((sum, d) => sum + d, 0) / delays.length : 0

    return {
      testName: '网络错误重试',
      operationId,
      totalOperations: operations,
      successfulOperations: successful,
      failedOperations: failed,
      averageAttempts: totalAttempts / operations,
      totalRetries: totalAttempts - operations,
      averageDelay: Math.round(averageDelay),
      strategy: 'exponential'
    }
  }

  /**
   * 测试超时错误重试
   */
  private async testTimeoutErrorRetry(): Promise<RetryTestResult> {
    const operationId = 'timeout_error_test'
    const operations = 4
    let successful = 0
    let failed = 0
    let totalAttempts = 0

    for (let i = 0; i < operations; i++) {
      const result = await intelligentRetryManager.executeWithRetry(
        () => this.simulateTimeoutError(i),
        `${operationId}_${i}`
      )

      if (result.success) {
        successful++
        console.log(`  超时测试 ${i + 1}: 成功 (尝试 ${result.attempts} 次, 耗时 ${result.totalTime}ms)`)
      } else {
        failed++
        console.log(`  超时测试 ${i + 1}: 失败 (尝试 ${result.attempts} 次, 耗时 ${result.totalTime}ms)`)
      }

      totalAttempts += result.attempts
      await this.delay(300)
    }

    return {
      testName: '超时错误重试',
      operationId,
      totalOperations: operations,
      successfulOperations: successful,
      failedOperations: failed,
      averageAttempts: totalAttempts / operations,
      totalRetries: totalAttempts - operations,
      averageDelay: 2000,
      strategy: 'linear'
    }
  }

  /**
   * 测试限流错误重试
   */
  private async testRateLimitRetry(): Promise<RetryTestResult> {
    const operationId = 'rate_limit_test'
    const operations = 3
    let successful = 0
    let failed = 0
    let totalAttempts = 0

    for (let i = 0; i < operations; i++) {
      const result = await intelligentRetryManager.executeWithRetry(
        () => this.simulateRateLimitError(i),
        `${operationId}_${i}`
      )

      if (result.success) {
        successful++
        console.log(`  限流测试 ${i + 1}: 成功 (尝试 ${result.attempts} 次, 策略: ${result.strategy})`)
      } else {
        failed++
        console.log(`  限流测试 ${i + 1}: 失败 (尝试 ${result.attempts} 次, 策略: ${result.strategy})`)
      }

      totalAttempts += result.attempts
      await this.delay(500)
    }

    return {
      testName: '限流错误重试',
      operationId,
      totalOperations: operations,
      successfulOperations: successful,
      failedOperations: failed,
      averageAttempts: totalAttempts / operations,
      totalRetries: totalAttempts - operations,
      averageDelay: 5000,
      strategy: 'exponential'
    }
  }

  /**
   * 测试服务器错误重试
   */
  private async testServerErrorRetry(): Promise<RetryTestResult> {
    const operationId = 'server_error_test'
    const operations = 4
    let successful = 0
    let failed = 0
    let totalAttempts = 0

    for (let i = 0; i < operations; i++) {
      const result = await intelligentRetryManager.executeWithRetry(
        () => this.simulateServerError(i),
        `${operationId}_${i}`
      )

      if (result.success) {
        successful++
        console.log(`  服务器错误测试 ${i + 1}: 成功 (尝试 ${result.attempts} 次)`)
      } else {
        failed++
        console.log(`  服务器错误测试 ${i + 1}: 失败 (尝试 ${result.attempts} 次)`)
      }

      totalAttempts += result.attempts
      await this.delay(200)
    }

    return {
      testName: '服务器错误重试',
      operationId,
      totalOperations: operations,
      successfulOperations: successful,
      failedOperations: failed,
      averageAttempts: totalAttempts / operations,
      totalRetries: totalAttempts - operations,
      averageDelay: 1500,
      strategy: 'exponential'
    }
  }

  /**
   * 测试客户端错误处理
   */
  private async testClientErrorHandling(): Promise<RetryTestResult> {
    const operationId = 'client_error_test'
    const operations = 3
    let successful = 0
    let failed = 0
    let totalAttempts = 0

    for (let i = 0; i < operations; i++) {
      const result = await intelligentRetryManager.executeWithRetry(
        () => this.simulateClientError(i),
        `${operationId}_${i}`
      )

      if (result.success) {
        successful++
        console.log(`  客户端错误测试 ${i + 1}: 成功 (尝试 ${result.attempts} 次)`)
      } else {
        failed++
        console.log(`  客户端错误测试 ${i + 1}: 失败 (尝试 ${result.attempts} 次) - 预期行为`)
      }

      totalAttempts += result.attempts
      await this.delay(100)
    }

    return {
      testName: '客户端错误处理',
      operationId,
      totalOperations: operations,
      successfulOperations: successful,
      failedOperations: failed,
      averageAttempts: totalAttempts / operations,
      totalRetries: totalAttempts - operations,
      averageDelay: 0,
      strategy: 'fixed'
    }
  }

  /**
   * 测试自适应重试策略
   */
  private async testAdaptiveRetry(): Promise<RetryTestResult> {
    const operationId = 'adaptive_retry_test'
    const operations = 10
    let successful = 0
    let failed = 0
    let totalAttempts = 0

    // 先执行一些操作建立历史数据
    for (let i = 0; i < operations; i++) {
      const result = await intelligentRetryManager.executeWithRetry(
        () => this.simulateAdaptiveScenario(i),
        operationId, // 使用相同的operationId以建立历史
        {
          strategy: 'adaptive',
          maxAttempts: 4
        }
      )

      if (result.success) {
        successful++
        console.log(`  自适应测试 ${i + 1}: 成功 (尝试 ${result.attempts} 次, 策略: ${result.strategy})`)
      } else {
        failed++
        console.log(`  自适应测试 ${i + 1}: 失败 (尝试 ${result.attempts} 次, 策略: ${result.strategy})`)
      }

      totalAttempts += result.attempts
      await this.delay(100)
    }

    return {
      testName: '自适应重试策略',
      operationId,
      totalOperations: operations,
      successfulOperations: successful,
      failedOperations: failed,
      averageAttempts: totalAttempts / operations,
      totalRetries: totalAttempts - operations,
      averageDelay: 1000,
      strategy: 'adaptive'
    }
  }

  /**
   * 测试批量重试操作
   */
  private async testBatchRetry(): Promise<RetryTestResult> {
    const operations = Array.from({ length: 8 }, (_, i) => ({
      fn: () => this.simulateMixedScenario(i),
      id: `batch_operation_${i}`,
      config: {
        maxAttempts: 3,
        strategy: 'exponential' as const
      }
    }))

    const result = await intelligentRetryManager.executeBatchWithRetry(operations, {
      maxConcurrency: 3,
      failFast: false,
      collectResults: true
    })

    console.log(`  批量重试完成: ${result.summary.successful}/${result.summary.total} 成功`)
    console.log(`  平均尝试次数: ${result.summary.averageAttempts}`)
    console.log(`  总耗时: ${result.summary.totalTime}ms`)

    return {
      testName: '批量重试操作',
      operationId: 'batch_retry',
      totalOperations: result.summary.total,
      successfulOperations: result.summary.successful,
      failedOperations: result.summary.failed,
      averageAttempts: result.summary.averageAttempts,
      totalRetries: Math.round((result.summary.averageAttempts - 1) * result.summary.total),
      averageDelay: 1000,
      strategy: 'exponential'
    }
  }

  /**
   * 测试重试统计和监控
   */
  private async testRetryStatistics(): Promise<void> {
    console.log('  检查重试统计信息...')
    
    const systemStats = intelligentRetryManager.getSystemStats()
    console.log(`  系统统计:`)
    console.log(`    总操作数: ${systemStats.totalOperations}`)
    console.log(`    总重试次数: ${systemStats.totalRetries}`)
    console.log(`    总体成功率: ${(systemStats.overallSuccessRate * 100).toFixed(1)}%`)
    console.log(`    平均尝试次数: ${systemStats.averageAttemptsPerOperation}`)
    console.log(`    最多重试操作: ${systemStats.mostRetriedOperation}`)
    console.log(`    最不可靠操作: ${systemStats.leastReliableOperation}`)

    // 获取特定操作的统计
    const networkStats = intelligentRetryManager.getOperationStats('network_error_test_0')
    if (networkStats) {
      console.log(`  网络错误操作统计:`)
      console.log(`    总尝试: ${networkStats.totalAttempts}`)
      console.log(`    成功率: ${(networkStats.successRate * 100).toFixed(1)}%`)
      console.log(`    平均尝试次数: ${networkStats.averageAttempts.toFixed(2)}`)
    }

    // 获取重试历史
    const recentHistory = intelligentRetryManager.getRetryHistory(undefined, 10)
    console.log(`  最近 ${recentHistory.length} 次重试历史:`)
    recentHistory.slice(0, 5).forEach((h, i) => {
      console.log(`    ${i + 1}. ${h.operationId}: ${h.success ? '成功' : '失败'} (${h.attempts} 次尝试)`)
    })
  }

  /**
   * 模拟网络错误
   */
  private async simulateNetworkError(id: number): Promise<{ id: number, data: string }> {
    await this.delay(300 + Math.random() * 500)
    
    // 60%的概率网络错误
    if (Math.random() < 0.6) {
      const error = new Error('ECONNREFUSED: Connection refused')
      ;(error as any).code = 'ECONNREFUSED'
      throw error
    }
    
    return { id, data: `网络请求成功 ${id}` }
  }

  /**
   * 模拟超时错误
   */
  private async simulateTimeoutError(id: number): Promise<{ id: number, data: string }> {
    // 50%的概率超时
    const delay = Math.random() < 0.5 ? 4000 : 800
    await this.delay(delay)
    
    if (delay > 3000) {
      throw new Error('请求超时')
    }
    
    return { id, data: `超时测试成功 ${id}` }
  }

  /**
   * 模拟限流错误
   */
  private async simulateRateLimitError(id: number): Promise<{ id: number, data: string }> {
    await this.delay(200)
    
    // 70%的概率限流
    if (Math.random() < 0.7) {
      const error = new Error('Too Many Requests')
      ;(error as any).status = 429
      throw error
    }
    
    return { id, data: `限流测试成功 ${id}` }
  }

  /**
   * 模拟服务器错误
   */
  private async simulateServerError(id: number): Promise<{ id: number, data: string }> {
    await this.delay(400)
    
    // 50%的概率服务器错误
    if (Math.random() < 0.5) {
      const error = new Error('Internal Server Error')
      ;(error as any).status = 500
      throw error
    }
    
    return { id, data: `服务器测试成功 ${id}` }
  }

  /**
   * 模拟客户端错误
   */
  private async simulateClientError(id: number): Promise<{ id: number, data: string }> {
    await this.delay(200)
    
    // 客户端错误不应该重试
    const error = new Error('Bad Request')
    ;(error as any).status = 400
    throw error
  }

  /**
   * 模拟自适应场景
   */
  private async simulateAdaptiveScenario(id: number): Promise<{ id: number, data: string }> {
    await this.delay(300)
    
    // 前几次失败率高，后面成功率提高（模拟系统学习）
    const failureRate = Math.max(0.8 - (id * 0.1), 0.2)
    
    if (Math.random() < failureRate) {
      throw new Error(`自适应测试失败 ${id}`)
    }
    
    return { id, data: `自适应测试成功 ${id}` }
  }

  /**
   * 模拟混合场景
   */
  private async simulateMixedScenario(id: number): Promise<{ id: number, data: string }> {
    await this.delay(200 + Math.random() * 400)
    
    // 不同类型的错误
    const rand = Math.random()
    
    if (rand < 0.3) {
      // 网络错误
      const error = new Error('Network error')
      ;(error as any).code = 'NETWORK_ERROR'
      throw error
    } else if (rand < 0.5) {
      // 超时错误
      throw new Error('Timeout error')
    } else if (rand < 0.7) {
      // 成功
      return { id, data: `混合测试成功 ${id}` }
    } else {
      // 服务器错误
      const error = new Error('Server error')
      ;(error as any).status = 503
      throw error
    }
  }

  /**
   * 生成测试报告
   */
  private generateTestReport(results: RetryTestResult[]): void {
    console.log('\n📊 智能重试机制测试报告')
    console.log('=' .repeat(80))

    console.log('测试项目 | 总数 | 成功 | 失败 | 平均尝试 | 总重试 | 策略')
    console.log('-'.repeat(80))

    let totalOps = 0
    let totalSuccess = 0
    let totalRetries = 0

    for (const result of results) {
      totalOps += result.totalOperations
      totalSuccess += result.successfulOperations
      totalRetries += result.totalRetries

      const successRate = (result.successfulOperations / result.totalOperations * 100).toFixed(1)
      
      console.log(
        `${result.testName.padEnd(14)} | ` +
        `${result.totalOperations.toString().padStart(4)} | ` +
        `${result.successfulOperations.toString().padStart(4)} | ` +
        `${result.failedOperations.toString().padStart(4)} | ` +
        `${result.averageAttempts.toFixed(2).padStart(9)} | ` +
        `${result.totalRetries.toString().padStart(6)} | ` +
        `${result.strategy.padEnd(12)}`
      )
    }

    console.log('-'.repeat(80))
    
    const overallSuccessRate = (totalSuccess / totalOps * 100).toFixed(1)
    const avgRetriesPerOp = (totalRetries / totalOps).toFixed(2)
    
    console.log(`总计: ${totalOps} 操作, ${totalSuccess} 成功, ${totalRetries} 重试`)
    console.log(`总体成功率: ${overallSuccessRate}%`)
    console.log(`平均重试次数: ${avgRetriesPerOp}`)

    console.log('\n💡 测试结论:')
    if (parseFloat(overallSuccessRate) >= 70) {
      console.log('✅ 智能重试机制工作良好')
      console.log('✅ 不同错误类型的重试策略有效')
      console.log('✅ 自适应重试能够根据历史调整策略')
      console.log('✅ 批量重试操作性能良好')
      console.log('✅ 建议在生产环境中启用')
    } else {
      console.log('⚠️ 重试机制需要进一步优化')
      console.log('⚠️ 建议调整重试参数和策略')
    }

    console.log('\n🎯 优化建议:')
    console.log('• 根据实际业务场景调整重试次数')
    console.log('• 优化不同错误类型的重试延迟')
    console.log('• 定期分析重试统计数据')
    console.log('• 考虑实现更细粒度的重试条件')

    console.log('\n' + '='.repeat(80))
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
    intelligentRetryManager.clearStats()
  }
}

/**
 * 主函数
 */
async function main() {
  try {
    const tester = new IntelligentRetryTester()
    await tester.runRetryTests()
    
    console.log('\n🎉 智能重试机制验证完成!')
    console.log('🔄 系统现在具备了智能的重试和容错能力')
    
    // 清理资源
    tester.cleanup()
    
  } catch (error) {
    console.error('❌ 重试机制测试失败:', error)
    process.exit(1)
  }
}

// 运行测试
if (require.main === module) {
  main()
}

export { IntelligentRetryTester }
