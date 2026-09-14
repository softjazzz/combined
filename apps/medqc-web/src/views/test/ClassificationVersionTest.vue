<template>
  <div class="classification-version-test p-6">
    <a-card
      title="分类算法版本管理测试"
      class="mb-4"
    >
      <a-space
        direction="vertical"
        size="large"
        style="width: 100%"
      >
        <!-- 版本信息测试 -->
        <a-card
          title="版本信息测试"
          size="small"
        >
          <a-button
            :loading="testing.versionInfo"
            @click="testVersionInfo"
          >
            测试版本信息API
          </a-button>
          <div
            v-if="results.versionInfo"
            class="mt-3"
          >
            <a-descriptions
              title="版本信息"
              :column="2"
              bordered
              size="small"
            >
              <a-descriptions-item label="当前版本">
                {{ results.versionInfo.current_version_name }}
              </a-descriptions-item>
              <a-descriptions-item label="回退版本">
                {{ results.versionInfo.fallback_version_name }}
              </a-descriptions-item>
            </a-descriptions>
          </div>
        </a-card>

        <!-- 性能统计测试 -->
        <a-card
          title="性能统计测试"
          size="small"
        >
          <a-button
            :loading="testing.performanceStats"
            @click="testPerformanceStats"
          >
            测试性能统计API
          </a-button>
          <div
            v-if="results.performanceStats"
            class="mt-3"
          >
            <a-row :gutter="16">
              <a-col :span="6">
                <a-statistic
                  title="总请求数"
                  :value="results.performanceStats.total_requests"
                />
              </a-col>
              <a-col :span="6">
                <a-statistic 
                  title="成功率" 
                  :value="results.performanceStats.success_rate" 
                  suffix="%" 
                />
              </a-col>
              <a-col :span="6">
                <a-statistic 
                  title="平均处理时间" 
                  :value="results.performanceStats.average_processing_time" 
                  suffix="秒"
                  :precision="3"
                />
              </a-col>
              <a-col :span="6">
                <a-statistic
                  title="当前版本"
                  :value="results.performanceStats.current_version"
                />
              </a-col>
            </a-row>
          </div>
        </a-card>

        <!-- 健康检查测试 -->
        <a-card
          title="健康检查测试"
          size="small"
        >
          <a-button
            :loading="testing.healthCheck"
            @click="testHealthCheck"
          >
            测试健康检查API
          </a-button>
          <div
            v-if="results.healthCheck"
            class="mt-3"
          >
            <a-alert 
              :type="results.healthCheck.status === 'healthy' ? 'success' : 'error'"
              :message="`系统状态: ${results.healthCheck.status}`"
              show-icon
            />
          </div>
        </a-card>

        <!-- 分类测试 -->
        <a-card
          title="分类功能测试"
          size="small"
        >
          <a-textarea 
            v-model:value="testText" 
            placeholder="输入测试文本..."
            :rows="4"
            class="mb-3"
          />
          <a-button
            :loading="testing.classification"
            type="primary"
            @click="testClassification"
          >
            测试分类功能
          </a-button>
          <div
            v-if="results.classification"
            class="mt-3"
          >
            <a-descriptions
              title="分类结果"
              :column="1"
              bordered
              size="small"
            >
              <a-descriptions-item label="识别文书数">
                {{ results.classification.total_documents }}
              </a-descriptions-item>
              <a-descriptions-item label="平均置信度">
                {{ results.classification.statistics?.averageConfidence || 'N/A' }}
              </a-descriptions-item>
              <a-descriptions-item label="处理时间">
                {{ results.classification.processing_time }}秒
              </a-descriptions-item>
              <a-descriptions-item label="算法版本">
                {{ results.classification.algorithm_version }}
              </a-descriptions-item>
            </a-descriptions>
            
            <div
              v-if="results.classification.documents?.length > 0"
              class="mt-3"
            >
              <h4>识别的文书：</h4>
              <a-list
                size="small"
                bordered
              >
                <a-list-item
                  v-for="doc in results.classification.documents"
                  :key="doc.title"
                >
                  <a-list-item-meta>
                    <template #title>
                      {{ doc.title }}
                      <a-tag
                        :color="getConfidenceColor(doc.confidence)"
                        class="ml-2"
                      >
                        {{ Math.round(doc.confidence * 100) }}%
                      </a-tag>
                    </template>
                    <template #description>
                      {{ doc.summary || '无摘要' }}
                    </template>
                  </a-list-item-meta>
                </a-list-item>
              </a-list>
            </div>
          </div>
        </a-card>

        <!-- 版本切换测试 -->
        <a-card
          title="版本切换测试"
          size="small"
        >
          <a-select 
            v-model:value="selectedTestVersion" 
            placeholder="选择要切换的版本"
            style="width: 200px"
            class="mr-3"
          >
            <a-select-option value="basic">
              基础版本
            </a-select-option>
            <a-select-option value="enhanced">
              增强版本
            </a-select-option>
            <a-select-option value="advanced">
              先进版本
            </a-select-option>
          </a-select>
          <a-button
            :loading="testing.versionSwitch"
            type="primary"
            @click="testVersionSwitch"
          >
            测试版本切换
          </a-button>
          <div
            v-if="results.versionSwitch"
            class="mt-3"
          >
            <a-alert 
              :type="results.versionSwitch.success ? 'success' : 'error'"
              :message="results.versionSwitch.message"
              show-icon
            />
          </div>
        </a-card>

        <!-- 测试日志 -->
        <a-card
          title="测试日志"
          size="small"
        >
          <a-button
            size="small"
            class="mb-3"
            @click="clearLogs"
          >
            清空日志
          </a-button>
          <div class="test-logs">
            <div
              v-for="(log, index) in testLogs"
              :key="index"
              class="log-entry"
            >
              <span class="log-time">{{ log.time }}</span>
              <span :class="['log-level', `log-${log.level}`]">{{ log.level.toUpperCase() }}</span>
              <span class="log-message">{{ log.message }}</span>
            </div>
          </div>
        </a-card>
      </a-space>
    </a-card>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive } from 'vue'
import { message } from 'ant-design-vue'

interface VersionInfoResult {
  current_version_name: string
  fallback_version_name: string
}

interface PerformanceStatsResult {
  total_requests: number
  success_rate: number
  average_processing_time: number
  current_version: string
}

interface HealthCheckResult {
  status: string
}

interface ClassificationDocument {
  title: string
  confidence: number
  summary?: string
}

interface ClassificationResult {
  total_documents: number
  statistics?: {
    averageConfidence?: number
  }
  processing_time: number
  algorithm_version: string
  documents: ClassificationDocument[]
}

interface VersionSwitchResult {
  success: boolean
  message: string
}

interface TestLogItem {
  time: string
  level: string
  message: string
}

const getErrorMessage = (error: unknown): string => {
  if (error instanceof Error) return error.message
  if (typeof error === 'object' && error && 'message' in error) {
    return String((error as { message?: unknown }).message || '未知错误')
  }
  return '未知错误'
}

// 响应式数据
const testing = reactive({
  versionInfo: false,
  performanceStats: false,
  healthCheck: false,
  classification: false,
  versionSwitch: false
})

const results = reactive({
  versionInfo: null as VersionInfoResult | null,
  performanceStats: null as PerformanceStatsResult | null,
  healthCheck: null as HealthCheckResult | null,
  classification: null as ClassificationResult | null,
  versionSwitch: null as VersionSwitchResult | null
})

const testText = ref(`患者张伟，44岁男性，因肛旁肿物疼痛2+天入院。

首次病程记录
患者张伟，44岁，以"发现肛旁肿物疼痛2+天"为主诉入院。
现病史：患者5天前出现发热、咳嗽症状...

孙治庆主治医师查房记录
2025-03-29 10:08
患者张伟，44岁男性，年龄44岁，以"发现肛旁肿物疼痛2+天"为主诉于2025年3月29日13:49入院。

CT检查记录
CT检查显示肛瘘并肛周脓肿。

手术日期：2025年3月30日
手术名称：高位复杂性肛瘘切除术+肛周脓肿切开引流术
手术经过：手术顺利完成...`)

const selectedTestVersion = ref('advanced')
const testLogs = ref<TestLogItem[]>([])

// 方法
const addLog = (level: string, message: string) => {
  testLogs.value.unshift({
    time: new Date().toLocaleTimeString(),
    level,
    message
  })
  if (testLogs.value.length > 50) {
    testLogs.value = testLogs.value.slice(0, 50)
  }
}

const clearLogs = () => {
  testLogs.value = []
}

const getConfidenceColor = (confidence: number) => {
  if (confidence >= 0.8) return 'green'
  if (confidence >= 0.6) return 'orange'
  return 'red'
}

const testVersionInfo = async () => {
  testing.versionInfo = true
  addLog('info', '开始测试版本信息API...')
  
  try {
    const response = await fetch('/api/enhanced-classification/version/info')
    if (response.ok) {
      results.versionInfo = await response.json()
      addLog('success', '版本信息API测试成功')
      message.success('版本信息获取成功')
    } else {
      throw new Error(`HTTP ${response.status}`)
    }
  } catch (error: unknown) {
    addLog('error', `版本信息API测试失败: ${getErrorMessage(error)}`)
    message.error('版本信息获取失败')
  } finally {
    testing.versionInfo = false
  }
}

const testPerformanceStats = async () => {
  testing.performanceStats = true
  addLog('info', '开始测试性能统计API...')
  
  try {
    const response = await fetch('/api/enhanced-classification/performance/stats')
    if (response.ok) {
      results.performanceStats = await response.json()
      addLog('success', '性能统计API测试成功')
      message.success('性能统计获取成功')
    } else {
      throw new Error(`HTTP ${response.status}`)
    }
  } catch (error: unknown) {
    addLog('error', `性能统计API测试失败: ${getErrorMessage(error)}`)
    message.error('性能统计获取失败')
  } finally {
    testing.performanceStats = false
  }
}

const testHealthCheck = async () => {
  testing.healthCheck = true
  addLog('info', '开始测试健康检查API...')
  
  try {
    const response = await fetch('/api/enhanced-classification/health')
    if (response.ok) {
      results.healthCheck = await response.json()
      const healthCheck = results.healthCheck
      addLog('success', `健康检查完成，状态: ${healthCheck?.status || 'unknown'}`)
      message.success('健康检查完成')
    } else {
      throw new Error(`HTTP ${response.status}`)
    }
  } catch (error: unknown) {
    addLog('error', `健康检查API测试失败: ${getErrorMessage(error)}`)
    message.error('健康检查失败')
  } finally {
    testing.healthCheck = false
  }
}

const testClassification = async () => {
  if (!testText.value.trim()) {
    message.warning('请输入测试文本')
    return
  }

  testing.classification = true
  addLog('info', '开始测试分类功能...')
  
  try {
    const response = await fetch('/api/enhanced-classification/classify', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        recordId: 'test-record-id',
        rawText: testText.value,
        confidenceThreshold: 0.5,
        enableHierarchicalClassification: true
      })
    })
    
    if (response.ok) {
      results.classification = await response.json()
      const classification = results.classification
      addLog('success', `分类测试成功，识别${classification?.total_documents || 0}个文书`)
      message.success('分类测试成功')
    } else {
      throw new Error(`HTTP ${response.status}`)
    }
  } catch (error: unknown) {
    addLog('error', `分类功能测试失败: ${getErrorMessage(error)}`)
    message.error('分类测试失败')
  } finally {
    testing.classification = false
  }
}

const testVersionSwitch = async () => {
  if (!selectedTestVersion.value) {
    message.warning('请选择要切换的版本')
    return
  }

  testing.versionSwitch = true
  addLog('info', `开始测试版本切换到: ${selectedTestVersion.value}`)
  
  try {
    const response = await fetch('/api/enhanced-classification/version/switch', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ version: selectedTestVersion.value })
    })
    
    if (response.ok) {
      results.versionSwitch = await response.json()
      const versionSwitch = results.versionSwitch
      addLog('success', `版本切换测试完成: ${versionSwitch?.message || ''}`)
      if (versionSwitch?.success) {
        message.success('版本切换成功')
      } else {
        message.error(versionSwitch?.message || '版本切换失败')
      }
    } else {
      throw new Error(`HTTP ${response.status}`)
    }
  } catch (error: unknown) {
    addLog('error', `版本切换测试失败: ${getErrorMessage(error)}`)
    message.error('版本切换测试失败')
  } finally {
    testing.versionSwitch = false
  }
}
</script>

<style scoped>
.classification-version-test {
  max-width: 1200px;
  margin: 0 auto;
}

.test-logs {
  max-height: 300px;
  overflow-y: auto;
  background: #f5f5f5;
  padding: 12px;
  border-radius: 4px;
  font-family: 'Courier New', monospace;
  font-size: 12px;
}

.log-entry {
  margin-bottom: 4px;
  display: flex;
  align-items: center;
}

.log-time {
  color: #666;
  margin-right: 8px;
  min-width: 80px;
}

.log-level {
  margin-right: 8px;
  padding: 2px 6px;
  border-radius: 3px;
  font-weight: bold;
  min-width: 60px;
  text-align: center;
  font-size: 10px;
}

.log-info {
  background: #e6f7ff;
  color: #2b6cf6;
}

.log-success {
  background: #f6ffed;
  color: #52c41a;
}

.log-error {
  background: #fff2f0;
  color: #ff4d4f;
}

.log-message {
  flex: 1;
}
</style>
