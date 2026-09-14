<template>
  <div class="llm-qc-demo">
    <div class="demo-header">
      <h1>LLM集成质控系统演示</h1>
      <p class="demo-description">
        展示基于大语言模型的医疗质控规则执行系统 - Phase 1 功能
      </p>
    </div>

    <!-- 标签页导航 -->
    <a-tabs
      v-model:active-key="activeTab"
      class="demo-tabs"
    >
      <a-tab-pane
        key="demo"
        tab="质控演示"
      >
        <a-row :gutter="24">
          <!-- 控制面板 -->
          <a-col :span="8">
            <a-card
              title="控制面板"
              class="control-panel"
            >
              <a-space
                direction="vertical"
                style="width: 100%"
              >
                <a-button
                  type="primary"
                  block
                  :loading="initializing"
                  @click="initializeDemo"
                >
                  初始化演示环境
                </a-button>

                <a-button
                  block
                  :loading="analyzing"
                  :disabled="!initialized"
                  @click="runQCDemo"
                >
                  执行质控分析
                </a-button>

                <a-button
                  block
                  :loading="managingRules"
                  :disabled="!initialized"
                  @click="demonstrateRuleManagement"
                >
                  规则管理演示
                </a-button>

                <a-button
                  block
                  :loading="runningFullDemo"
                  @click="runFullDemo"
                >
                  完整功能演示
                </a-button>

                <a-divider />

                <a-button
                  block
                  type="dashed"
                  @click="clearLogs"
                >
                  清空日志
                </a-button>
              </a-space>
            </a-card>

            <!-- 系统状态 -->
            <a-card
              title="系统状态"
              class="status-panel"
              style="margin-top: 16px"
            >
              <a-descriptions
                :column="1"
                size="small"
              >
                <a-descriptions-item label="初始化状态">
                  <a-tag :color="initialized ? 'green' : 'orange'">
                    {{ initialized ? '已初始化' : '未初始化' }}
                  </a-tag>
                </a-descriptions-item>
                <a-descriptions-item label="缓存命中率">
                  {{ cacheStats.hitRate ? (cacheStats.hitRate * 100).toFixed(1) + '%' : 'N/A' }}
                </a-descriptions-item>
                <a-descriptions-item label="执行次数">
                  {{ executionMetrics.totalExecutions || 0 }}
                </a-descriptions-item>
                <a-descriptions-item label="成功率">
                  {{ executionMetrics.totalExecutions ? 
                    ((executionMetrics.successfulExecutions / executionMetrics.totalExecutions) * 100).toFixed(1) + '%' : 'N/A' }}
                </a-descriptions-item>
              </a-descriptions>
            </a-card>
          </a-col>

          <!-- 结果展示 -->
          <a-col :span="16">
            <a-card
              title="执行结果"
              class="results-panel"
            >
              <div
                v-if="qcResult"
                class="qc-results"
              >
                <a-alert
                  :message="`质控分析完成 - 总分: ${qcResult.overallScore}/100`"
                  :description="qcResult.summary"
                  :type="qcResult.riskLevel === 'low' ? 'success' : 
                    qcResult.riskLevel === 'medium' ? 'warning' : 'error'"
                  show-icon
                  style="margin-bottom: 16px"
                />

                <a-tabs>
                  <a-tab-pane
                    key="rules"
                    tab="规则结果"
                  >
                    <div class="rule-results">
                      <a-list
                        :data-source="qcResult.ruleResults"
                        item-layout="vertical"
                      >
                        <template #renderItem="{ item }">
                          <a-list-item>
                            <a-list-item-meta>
                              <template #title>
                                <span>{{ item.ruleName }} ({{ item.ruleCode }})</span>
                                <a-tag 
                                  :color="item.isCompliant ? 'green' : 'red'"
                                  style="margin-left: 8px"
                                >
                                  {{ item.isCompliant ? '合规' : '不合规' }}
                                </a-tag>
                              </template>
                              <template #description>
                                <div>
                                  <p>评分: {{ item.score }}/100 | 置信度: {{ item.confidence }}% | 执行时间: {{ item.executionTime }}ms</p>
                                  <div v-if="item.findings.length > 0">
                                    <strong>发现问题:</strong>
                                    <ul>
                                      <li
                                        v-for="finding in item.findings"
                                        :key="finding.description"
                                      >
                                        <a-tag
                                          :color="finding.severity === 'critical' ? 'red' : 
                                            finding.severity === 'major' ? 'orange' : 'blue'"
                                        >
                                          {{ finding.severity }}
                                        </a-tag>
                                        {{ finding.description }}
                                        <div
                                          v-if="finding.recommendation"
                                          style="margin-top: 4px; color: #666;"
                                        >
                                          💡 {{ finding.recommendation }}
                                        </div>
                                      </li>
                                    </ul>
                                  </div>
                                  <div
                                    v-if="item.medicalReasoning"
                                    style="margin-top: 8px;"
                                  >
                                    <strong>医学推理:</strong> {{ item.medicalReasoning }}
                                  </div>
                                </div>
                              </template>
                            </a-list-item-meta>
                          </a-list-item>
                        </template>
                      </a-list>
                    </div>
                  </a-tab-pane>

                  <a-tab-pane
                    key="analysis"
                    tab="交叉分析"
                  >
                    <div
                      v-if="qcResult.crossRuleAnalysis"
                      class="cross-analysis"
                    >
                      <a-descriptions :column="1">
                        <a-descriptions-item label="关联问题">
                          {{ qcResult.crossRuleAnalysis.correlatedIssues }}
                        </a-descriptions-item>
                        <a-descriptions-item label="系统性问题">
                          {{ qcResult.crossRuleAnalysis.systemicProblems }}
                        </a-descriptions-item>
                        <a-descriptions-item label="优先建议">
                          {{ qcResult.crossRuleAnalysis.priorityRecommendations }}
                        </a-descriptions-item>
                      </a-descriptions>
                    </div>
                  </a-tab-pane>

                  <a-tab-pane
                    key="metrics"
                    tab="性能指标"
                  >
                    <a-row :gutter="16">
                      <a-col :span="12">
                        <a-statistic
                          title="总执行时间"
                          :value="qcResult.executionTime"
                          suffix="ms"
                        />
                      </a-col>
                      <a-col :span="12">
                        <a-statistic
                          title="检查规则数"
                          :value="qcResult.ruleResults.length"
                        />
                      </a-col>
                    </a-row>
                  </a-tab-pane>
                </a-tabs>
              </div>

              <div
                v-else
                class="no-results"
              >
                <a-empty description="暂无执行结果，请点击上方按钮开始演示" />
              </div>
            </a-card>
          </a-col>
        </a-row>

        <!-- 日志面板 -->
        <a-card
          title="执行日志"
          class="logs-panel"
          style="margin-top: 24px"
        >
          <div class="logs-container">
            <pre
              v-if="logs.length > 0"
              class="logs-content"
            >{{ logs.join('\n') }}</pre>
            <a-empty
              v-else
              description="暂无日志"
            />
          </div>
        </a-card>
      </a-tab-pane>

      <!-- LLM配置标签页 -->
      <a-tab-pane
        key="config"
        tab="LLM配置"
      >
        <QCLLMConfig />
      </a-tab-pane>
    </a-tabs>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import { llmQCDemoService } from '@/services/llm-qc-demo'
import type { ComprehensiveQCResult } from '@/types/enhanced-qc-rule'
import QCLLMConfig from '@/components/QCLLMConfig.vue'

// 响应式数据
const activeTab = ref('demo')
const initialized = ref(false)
const initializing = ref(false)
const analyzing = ref(false)
const managingRules = ref(false)
const runningFullDemo = ref(false)

const qcResult = ref<ComprehensiveQCResult | null>(null)
const logs = ref<string[]>([])

const cacheStats = reactive({
  hitRate: 0,
  totalRequests: 0,
  cacheSize: 0
})

const executionMetrics = reactive({
  totalExecutions: 0,
  successfulExecutions: 0,
  averageExecutionTime: 0
})

// 日志记录函数
const addLog = (message: string) => {
  const timestamp = new Date().toLocaleTimeString()
  logs.value.push(`[${timestamp}] ${message}`)

  // 保持最新的50条日志
  if (logs.value.length > 50) {
    logs.value = logs.value.slice(-50)
  }

  // 同时输出到控制台（仅在开发模式）
  if (import.meta.env.MODE === 'development') {
    console.log(`[LLM质控演示] ${message}`)
  }
}

const getErrorMessage = (error: unknown): string =>
  error instanceof Error ? error.message : String(error)

// ❌ 移除全局 console.log 重写，避免影响全站调试
// 改为在需要记录日志的地方显式调用 addLog()

// 方法实现
const initializeDemo = async () => {
  try {
    initializing.value = true
    addLog('开始初始化演示环境...')
    
    await llmQCDemoService.initializeDemo()
    initialized.value = true
    
    // 更新统计信息
    await updateStats()
    
    addLog('✅ 演示环境初始化完成')
    message.success('演示环境初始化成功')
    
  } catch (error) {
    addLog(`❌ 初始化失败: ${getErrorMessage(error)}`)
    message.error('初始化失败')
  } finally {
    initializing.value = false
  }
}

const runQCDemo = async () => {
  try {
    analyzing.value = true
    addLog('开始执行质控分析演示...')
    
    const result = await llmQCDemoService.runQCDemo()
    qcResult.value = result
    
    // 更新统计信息
    await updateStats()
    
    addLog('✅ 质控分析演示完成')
    message.success('质控分析完成')
    
  } catch (error) {
    addLog(`❌ 质控分析失败: ${getErrorMessage(error)}`)
    message.error('质控分析失败')
  } finally {
    analyzing.value = false
  }
}

const demonstrateRuleManagement = async () => {
  try {
    managingRules.value = true
    addLog('开始规则管理演示...')
    
    await llmQCDemoService.demonstrateRuleManagement()
    
    // 更新统计信息
    await updateStats()
    
    addLog('✅ 规则管理演示完成')
    message.success('规则管理演示完成')
    
  } catch (error) {
    addLog(`❌ 规则管理演示失败: ${getErrorMessage(error)}`)
    message.error('规则管理演示失败')
  } finally {
    managingRules.value = false
  }
}

const runFullDemo = async () => {
  try {
    runningFullDemo.value = true
    addLog('开始完整功能演示...')
    
    const result = await llmQCDemoService.runFullDemo()
    qcResult.value = result
    initialized.value = true
    
    // 更新统计信息
    await updateStats()
    
    addLog('✅ 完整功能演示完成')
    message.success('完整功能演示完成')
    
  } catch (error) {
    addLog(`❌ 完整功能演示失败: ${getErrorMessage(error)}`)
    message.error('完整功能演示失败')
  } finally {
    runningFullDemo.value = false
  }
}

const updateStats = async () => {
  try {
    const cacheStatsData = await llmQCDemoService.getCacheStats()
    Object.assign(cacheStats, cacheStatsData.overall)
    
    const execMetricsData = await llmQCDemoService.getExecutionMetrics()
    Object.assign(executionMetrics, execMetricsData)
    
  } catch (error) {
    console.error('Failed to update stats:', error)
  }
}

const clearLogs = () => {
  logs.value = []
  addLog('日志已清空')
}

// 生命周期
onMounted(() => {
  addLog('LLM集成质控系统演示页面已加载')
  addLog('请点击"初始化演示环境"开始体验')
})
</script>

<style scoped>
.llm-qc-demo {
  padding: 24px;
  background: #f5f5f5;
  min-height: 100vh;
}

.demo-header {
  text-align: center;
  margin-bottom: 32px;
  padding: 24px;
  background: white;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.1);
}

.demo-header h1 {
  margin: 0 0 8px 0;
  color: #2b6cf6;
  font-size: 28px;
}

.demo-description {
  margin: 0;
  color: #666;
  font-size: 16px;
}

.control-panel,
.status-panel,
.results-panel,
.logs-panel {
  box-shadow: 0 2px 8px rgba(0,0,0,0.1);
}

.qc-results {
  max-height: 600px;
  overflow-y: auto;
}

.rule-results {
  max-height: 400px;
  overflow-y: auto;
}

.cross-analysis {
  padding: 16px;
  background: #fafafa;
  border-radius: 6px;
}

.no-results {
  padding: 40px;
  text-align: center;
}

.logs-panel {
  margin-top: 24px;
}

.logs-container {
  max-height: 300px;
  overflow-y: auto;
  background: #f6f8fa;
  border-radius: 6px;
  padding: 16px;
}

.logs-content {
  margin: 0;
  font-family: 'Courier New', monospace;
  font-size: 12px;
  line-height: 1.4;
  color: #333;
  white-space: pre-wrap;
  word-break: break-all;
}

:deep(.ant-card-head-title) {
  font-weight: 600;
}

:deep(.ant-list-item-meta-title) {
  margin-bottom: 8px;
}

:deep(.ant-descriptions-item-label) {
  font-weight: 500;
}

:deep(.ant-statistic-title) {
  font-size: 14px;
  color: #666;
}

:deep(.ant-statistic-content) {
  font-size: 20px;
  font-weight: 600;
  color: #2b6cf6;
}

.demo-tabs {
  margin-top: 16px;
}

:deep(.demo-tabs .ant-tabs-nav) {
  margin-bottom: 24px;
}

:deep(.demo-tabs .ant-tabs-tab) {
  font-size: 16px;
  font-weight: 500;
}
</style>
