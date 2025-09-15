#!/usr/bin/env node

/**
 * 智慧医保质控系统 - 数据分析模块完整测试脚本
 * 
 * 测试所有已实现的数据分析功能：
 * 1. 基础统计分析功能
 * 2. 科室和医生维度报告
 * 3. 自动化报表生成和调度
 * 4. 高级分析功能（预测、异常检测）
 */

const BASE_URL = 'http://localhost:54321/functions/v1';

// 测试配置
const TEST_CONFIG = {
  timeRanges: ['7d', '30d', '90d'],
  granularities: ['day', 'week', 'month'],
  anomalySensitivities: [1.5, 2.0, 2.5],
  predictionModels: ['linear', 'moving_average', 'seasonal']
};

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
};

function log(message, color = 'reset') {
  console.log(`${colors[color]}${message}${colors.reset}`);
}

function logSection(title) {
  log(`\n${'='.repeat(80)}`, 'cyan');
  log(`${title}`, 'bright');
  log(`${'='.repeat(80)}`, 'cyan');
}

function logTest(testName) {
  log(`\n📊 测试: ${testName}`, 'blue');
}

function logSuccess(message) {
  log(`✅ ${message}`, 'green');
}

function logError(message) {
  log(`❌ ${message}`, 'red');
}

function logWarning(message) {
  log(`⚠️  ${message}`, 'yellow');
}

// HTTP 请求工具
async function makeRequest(service, endpoint, params = {}) {
  const url = new URL(`${BASE_URL}/${service}/${endpoint}`);
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null) {
      url.searchParams.append(key, value.toString());
    }
  });

  try {
    const response = await fetch(url.toString());
    const data = await response.json();
    
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${data.error || 'Unknown error'}`);
    }
    
    return { success: true, data, status: response.status };
  } catch (error) {
    return { success: false, error: error.message, status: 0 };
  }
}

// 测试函数集合
const tests = {
  // 1. 基础统计分析功能测试
  async testBasicStatistics() {
    logSection('基础统计分析功能测试');
    
    let passCount = 0;
    let totalTests = 0;

    // 测试仪表盘KPI
    logTest('仪表盘KPI指标');
    totalTests++;
    const dashboardResult = await makeRequest('statistics', 'dashboard');
    if (dashboardResult.success) {
      const { kpis } = dashboardResult.data;
      logSuccess(`仪表盘KPI获取成功 - 今日违规: ${kpis.todayViolations}, 活跃规则: ${kpis.activeRules}`);
      passCount++;
    } else {
      logError(`仪表盘KPI获取失败: ${dashboardResult.error}`);
    }

    // 测试趋势分析
    for (const timeRange of TEST_CONFIG.timeRanges) {
      for (const granularity of TEST_CONFIG.granularities) {
        logTest(`趋势分析 - ${timeRange} ${granularity}粒度`);
        totalTests++;
        
        const trendsResult = await makeRequest('statistics', 'trends', {
          days: parseInt(timeRange),
          granularity,
          analysis: 'true'
        });
        
        if (trendsResult.success) {
          const { trends, analysis } = trendsResult.data;
          logSuccess(`趋势分析成功 - ${trends?.length || 0}个数据点, 趋势: ${analysis?.total_trend?.trend || 'N/A'}`);
          passCount++;
        } else {
          logError(`趋势分析失败: ${trendsResult.error}`);
        }
      }
    }

    // 测试违规深度分析
    logTest('违规深度分析');
    totalTests++;
    const violationResult = await makeRequest('statistics', 'violations-analysis', {
      range: '30d',
      group_by: 'rule_type'
    });
    
    if (violationResult.success) {
      const { by_rule_type, temporal_patterns } = violationResult.data;
      logSuccess(`违规分析成功 - 规则类型: ${by_rule_type?.length || 0}, 时间模式: ${temporal_patterns ? '已分析' : '未分析'}`);
      passCount++;
    } else {
      logError(`违规分析失败: ${violationResult.error}`);
    }

    log(`\n📈 基础统计分析测试完成: ${passCount}/${totalTests} 通过`, passCount === totalTests ? 'green' : 'yellow');
    return { passCount, totalTests };
  },

  // 2. 科室和医生维度报告测试
  async testDepartmentDoctorReports() {
    logSection('科室和医生维度报告测试');
    
    let passCount = 0;
    let totalTests = 0;

    // 测试科室分析
    logTest('科室维度分析');
    totalTests++;
    const deptResult = await makeRequest('statistics', 'departments', {
      range: '30d',
      comparison: 'true'
    });
    
    if (deptResult.success) {
      const { departments, summary } = deptResult.data;
      logSuccess(`科室分析成功 - ${departments?.length || 0}个科室, 高风险科室: ${summary?.high_risk_departments || 0}`);
      passCount++;
    } else {
      logError(`科室分析失败: ${deptResult.error}`);
    }

    // 测试医生分析
    logTest('医生维度分析');
    totalTests++;
    const doctorResult = await makeRequest('statistics', 'doctors', {
      range: '30d',
      profile: 'true'
    });
    
    if (doctorResult.success) {
      const { doctors, summary } = doctorResult.data;
      logSuccess(`医生分析成功 - ${doctors?.length || 0}位医生, 平均质量分: ${summary?.avg_quality_score || 'N/A'}`);
      passCount++;
    } else {
      logError(`医生分析失败: ${doctorResult.error}`);
    }

    log(`\n👥 科室医生报告测试完成: ${passCount}/${totalTests} 通过`, passCount === totalTests ? 'green' : 'yellow');
    return { passCount, totalTests };
  },

  // 3. 自动化报表生成测试
  async testReportGeneration() {
    logSection('自动化报表生成测试');
    
    let passCount = 0;
    let totalTests = 0;

    // 测试报表模板获取
    logTest('报表模板获取');
    totalTests++;
    const templatesResult = await makeRequest('data-export', 'templates');
    
    if (templatesResult.success) {
      const { templates } = templatesResult.data;
      logSuccess(`报表模板获取成功 - ${templates?.length || 0}个模板`);
      passCount++;
    } else {
      logError(`报表模板获取失败: ${templatesResult.error}`);
    }

    // 测试报表生成（模拟）
    logTest('报表生成功能');
    totalTests++;
    try {
      // 模拟报表生成请求
      const generateResult = await fetch(`${BASE_URL}/data-export/generate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          templateId: 'violations_summary',
          format: 'excel',
          parameters: { timeRange: '30d' }
        })
      });
      
      if (generateResult.ok) {
        logSuccess('报表生成功能正常');
        passCount++;
      } else {
        logWarning('报表生成功能需要完善');
      }
    } catch (error) {
      logWarning(`报表生成测试跳过: ${error.message}`);
    }

    // 测试调度任务管理
    logTest('调度任务管理');
    totalTests++;
    const schedulerResult = await makeRequest('report-scheduler', 'jobs');
    
    if (schedulerResult.success) {
      const { jobs } = schedulerResult.data;
      logSuccess(`调度任务管理正常 - ${jobs?.length || 0}个任务`);
      passCount++;
    } else {
      logWarning(`调度任务管理需要完善: ${schedulerResult.error}`);
    }

    log(`\n📋 报表生成测试完成: ${passCount}/${totalTests} 通过`, passCount === totalTests ? 'green' : 'yellow');
    return { passCount, totalTests };
  },

  // 4. 高级分析功能测试
  async testAdvancedAnalytics() {
    logSection('高级分析功能测试');
    
    let passCount = 0;
    let totalTests = 0;

    // 测试异常检测
    for (const sensitivity of TEST_CONFIG.anomalySensitivities) {
      logTest(`异常检测 - 敏感度 ${sensitivity}`);
      totalTests++;
      
      const anomalyResult = await makeRequest('statistics', 'anomaly-detection', {
        days: 30,
        sensitivity
      });
      
      if (anomalyResult.success) {
        const { anomalies, statistics } = anomalyResult.data;
        logSuccess(`异常检测成功 - 发现 ${anomalies?.length || 0} 个异常, 异常率: ${statistics?.anomaly_rate || 0}%`);
        passCount++;
      } else {
        logError(`异常检测失败: ${anomalyResult.error}`);
      }
    }

    // 测试预测分析
    for (const model of TEST_CONFIG.predictionModels) {
      logTest(`预测分析 - ${model}模型`);
      totalTests++;
      
      const predictionResult = await makeRequest('statistics', 'predictions', {
        range: '90d',
        days: 7,
        model
      });
      
      if (predictionResult.success) {
        const { predictions, model_info, confidence } = predictionResult.data;
        logSuccess(`预测分析成功 - ${predictions?.length || 0}天预测, 置信度: ${confidence || 0}%, 模型: ${model_info?.type || model}`);
        passCount++;
      } else {
        logError(`预测分析失败: ${predictionResult.error}`);
      }
    }

    log(`\n🔮 高级分析测试完成: ${passCount}/${totalTests} 通过`, passCount === totalTests ? 'green' : 'yellow');
    return { passCount, totalTests };
  },

  // 5. 前端组件集成测试
  async testFrontendIntegration() {
    logSection('前端组件集成测试');
    
    let passCount = 0;
    let totalTests = 4;

    // 检查前端文件是否存在
    const fs = require('fs');
    const path = require('path');
    
    const frontendFiles = [
      'src/views/analytics/DataAnalytics.vue',
      'src/views/analytics/AdvancedAnalytics.vue',
      'src/views/analytics/DepartmentDoctorReports.vue',
      'src/views/analytics/ReportScheduler.vue'
    ];

    for (const file of frontendFiles) {
      logTest(`检查前端组件: ${file}`);
      const filePath = path.join(process.cwd(), file);
      
      if (fs.existsSync(filePath)) {
        logSuccess(`前端组件存在: ${file}`);
        passCount++;
      } else {
        logError(`前端组件缺失: ${file}`);
      }
    }

    log(`\n🎨 前端集成测试完成: ${passCount}/${totalTests} 通过`, passCount === totalTests ? 'green' : 'yellow');
    return { passCount, totalTests };
  }
};

// 主测试函数
async function runCompleteTest() {
  logSection('智慧医保质控系统 - 数据分析模块完整测试');
  log('开始执行全面功能测试...', 'bright');

  const results = [];
  let totalPassed = 0;
  let totalTests = 0;

  try {
    // 执行所有测试
    for (const [testName, testFunc] of Object.entries(tests)) {
      const result = await testFunc();
      results.push({ testName, ...result });
      totalPassed += result.passCount;
      totalTests += result.totalTests;
    }

    // 输出总结报告
    logSection('测试总结报告');
    
    for (const result of results) {
      const status = result.passCount === result.totalTests ? '✅' : '⚠️';
      log(`${status} ${result.testName}: ${result.passCount}/${result.totalTests} 通过`, 
          result.passCount === result.totalTests ? 'green' : 'yellow');
    }

    log(`\n📊 总体测试结果: ${totalPassed}/${totalTests} 通过`, 'bright');
    
    const successRate = ((totalPassed / totalTests) * 100).toFixed(1);
    log(`🎯 成功率: ${successRate}%`, successRate >= 90 ? 'green' : successRate >= 70 ? 'yellow' : 'red');

    if (successRate >= 90) {
      log('\n🎉 数据分析模块测试通过！系统功能完整，可以投入使用。', 'green');
    } else if (successRate >= 70) {
      log('\n⚠️  数据分析模块基本功能正常，部分高级功能需要完善。', 'yellow');
    } else {
      log('\n❌ 数据分析模块存在较多问题，需要进一步开发和调试。', 'red');
    }

    // 输出下一步建议
    logSection('下一步建议');
    
    if (successRate < 100) {
      log('🔧 建议优先处理以下问题:', 'blue');
      log('   1. 确保 Supabase Edge Functions 正确部署', 'cyan');
      log('   2. 检查数据库表结构和数据完整性', 'cyan');
      log('   3. 验证前端路由和组件集成', 'cyan');
      log('   4. 测试邮件服务配置（如果需要）', 'cyan');
    }
    
    log('📈 功能扩展建议:', 'blue');
    log('   1. 添加更多预测模型和算法', 'cyan');
    log('   2. 实现实时数据流处理', 'cyan');
    log('   3. 增加更多可视化图表类型', 'cyan');
    log('   4. 优化大数据量处理性能', 'cyan');

  } catch (error) {
    logError(`测试执行失败: ${error.message}`);
    console.error(error);
  }
}

// 执行测试
if (require.main === module) {
  runCompleteTest().catch(console.error);
}

module.exports = { runCompleteTest, tests };
