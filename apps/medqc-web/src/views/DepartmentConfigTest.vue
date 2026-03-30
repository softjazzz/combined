<template>
  <div class="department-config-test">
    <div class="page-header">
      <h1>专科化配置测试</h1>
      <p>测试和验证不同科室的专科化质控配置效果</p>
    </div>

    <div class="content-wrapper">
      <!-- 测试配置 -->
      <a-card
        title="测试配置"
        class="test-config-card"
      >
        <a-form
          layout="inline"
          @finish="runTest"
        >
          <a-form-item label="选择科室">
            <a-select
              v-model:value="testConfig.departmentId"
              placeholder="请选择科室"
              style="width: 200px"
            >
              <a-select-option
                v-for="dept in departments"
                :key="dept.id"
                :value="dept.id"
              >
                {{ dept.name }}
              </a-select-option>
            </a-select>
          </a-form-item>

          <a-form-item label="测试类型">
            <a-select
              v-model:value="testConfig.testType"
              placeholder="请选择测试类型"
              style="width: 200px"
            >
              <a-select-option value="rules">
                规则测试
              </a-select-option>
              <a-select-option value="sampling">
                抽样测试
              </a-select-option>
              <a-select-option value="workflow">
                工作流测试
              </a-select-option>
              <a-select-option value="performance">
                性能测试
              </a-select-option>
            </a-select>
          </a-form-item>

          <a-form-item label="测试数据量">
            <a-input-number
              v-model:value="testConfig.dataSize"
              :min="10"
              :max="1000"
              style="width: 120px"
            />
          </a-form-item>

          <a-form-item>
            <a-button
              type="primary"
              html-type="submit"
              :loading="testing"
              :disabled="!testConfig.departmentId"
            >
              开始测试
            </a-button>
          </a-form-item>
        </a-form>
      </a-card>

      <!-- 测试结果 -->
      <a-card
        v-if="testResults.length > 0"
        title="测试结果"
        class="test-results-card"
      >
        <template #extra>
          <a-space>
            <a-button @click="exportResults">
              <template #icon>
                <DownloadOutlined />
              </template>
              导出结果
            </a-button>
            <a-button @click="clearResults">
              <template #icon>
                <ClearOutlined />
              </template>
              清空结果
            </a-button>
          </a-space>
        </template>

        <div class="results-summary">
          <a-row :gutter="16">
            <a-col :span="6">
              <a-statistic
                title="测试总数"
                :value="testSummary.totalTests"
                :value-style="{ color: '#1890ff' }"
              />
            </a-col>
            <a-col :span="6">
              <a-statistic
                title="成功率"
                :value="testSummary.successRate"
                suffix="%"
                :value-style="{ color: '#3f8600' }"
              />
            </a-col>
            <a-col :span="6">
              <a-statistic
                title="平均耗时"
                :value="testSummary.avgTime"
                suffix="ms"
                :value-style="{ color: '#cf1322' }"
              />
            </a-col>
            <a-col :span="6">
              <a-statistic
                title="错误数量"
                :value="testSummary.errorCount"
                :value-style="{ color: '#cf1322' }"
              />
            </a-col>
          </a-row>
        </div>

        <a-divider />

        <a-table
          :columns="resultsColumns"
          :data-source="testResults"
          :pagination="{ pageSize: 10 }"
          :scroll="{ x: 1200 }"
        >
          <template #bodyCell="{ column, record }">
            <template v-if="column.key === 'status'">
              <a-tag :color="record.status === 'success' ? 'green' : 'red'">
                {{ record.status === 'success' ? '成功' : '失败' }}
              </a-tag>
            </template>
            <template v-else-if="column.key === 'duration'">
              {{ record.duration }}ms
            </template>
            <template v-else-if="column.key === 'actions'">
              <a-space>
                <a-button
                  type="link"
                  size="small"
                  @click="viewDetails(record as TestResultItem)"
                >
                  查看详情
                </a-button>
                <a-button
                  v-if="record.status === 'failed'"
                  type="link"
                  size="small"
                  @click="retryTest(record as TestResultItem)"
                >
                  重试
                </a-button>
              </a-space>
            </template>
          </template>
        </a-table>
      </a-card>

      <!-- 测试详情模态框 -->
      <a-modal
        v-model:open="showDetailsModal"
        title="测试详情"
        width="800px"
        :footer="null"
      >
        <div
          v-if="selectedResult"
          class="test-details"
        >
          <a-descriptions
            :column="2"
            bordered
          >
            <a-descriptions-item label="测试ID">
              {{ selectedResult.id }}
            </a-descriptions-item>
            <a-descriptions-item label="测试类型">
              {{ getTestTypeName(selectedResult.testType) }}
            </a-descriptions-item>
            <a-descriptions-item label="科室">
              {{ getDepartmentName(selectedResult.departmentId) }}
            </a-descriptions-item>
            <a-descriptions-item label="状态">
              <a-tag :color="selectedResult.status === 'success' ? 'green' : 'red'">
                {{ selectedResult.status === 'success' ? '成功' : '失败' }}
              </a-tag>
            </a-descriptions-item>
            <a-descriptions-item label="开始时间">
              {{ selectedResult.startTime }}
            </a-descriptions-item>
            <a-descriptions-item label="结束时间">
              {{ selectedResult.endTime }}
            </a-descriptions-item>
            <a-descriptions-item label="耗时">
              {{ selectedResult.duration }}ms
            </a-descriptions-item>
            <a-descriptions-item label="数据量">
              {{ selectedResult.dataSize }}
            </a-descriptions-item>
          </a-descriptions>

          <a-divider />

          <h4>测试结果详情</h4>
          <a-textarea
            :value="JSON.stringify(selectedResult.details, null, 2)"
            :rows="10"
            readonly
          />

          <div
            v-if="selectedResult.status === 'failed'"
            class="error-section"
          >
            <h4>错误信息</h4>
            <a-alert
              :message="selectedResult.error"
              type="error"
              show-icon
            />
          </div>
        </div>
      </a-modal>

      <!-- 实时测试日志 -->
      <a-card
        v-if="testing"
        title="实时测试日志"
        class="test-logs-card"
      >
        <div class="logs-container">
          <div
            v-for="log in testLogs"
            :key="log.id"
            class="log-entry"
            :class="log.level"
          >
            <span class="log-time">{{ log.timestamp }}</span>
            <span class="log-message">{{ log.message }}</span>
          </div>
        </div>
      </a-card>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import type { TableColumnsType } from 'ant-design-vue'
import { DownloadOutlined, ClearOutlined } from '@ant-design/icons-vue'

type TestType = 'rules' | 'sampling' | 'workflow' | 'performance'
type TestStatus = 'success' | 'failed'
type LogLevel = 'info' | 'success' | 'error'

interface Department {
  id: string
  name: string
}

interface TestResultItem {
  id: string
  testType: TestType
  departmentId: string
  status: TestStatus
  dataSize: number
  duration: number
  startTime: string
  endTime: string
  details: {
    rulesExecuted: number
    recordsProcessed: number
    defectsFound: number
    averageScore: number
  }
  error: string | null
}

interface TestLogEntry {
  id: number
  level: LogLevel
  message: string
  timestamp: string
}

const getErrorMessage = (error: unknown): string => {
  if (error instanceof Error) return error.message
  if (typeof error === 'object' && error && 'message' in error) {
    return String((error as { message?: unknown }).message || '未知错误')
  }
  return '未知错误'
}

// 响应式数据
const testing = ref(false)
const showDetailsModal = ref(false)
const selectedResult = ref<TestResultItem | null>(null)

// 测试配置
const testConfig = reactive<{
  departmentId: string
  testType: TestType
  dataSize: number
}>({
  departmentId: '',
  testType: 'rules',
  dataSize: 100,
})

// 科室列表
const departments = ref<Department[]>([
  { id: '1', name: '心内科' },
  { id: '2', name: '神经外科' },
  { id: '3', name: '急诊科' },
  { id: '4', name: 'ICU' },
])

// 测试结果
const testResults = ref<TestResultItem[]>([])

// 测试日志
const testLogs = ref<TestLogEntry[]>([])

// 表格列配置
const resultsColumns: TableColumnsType<TestResultItem> = [
  { title: '测试ID', dataIndex: 'id', key: 'id', width: 120 },
  { title: '测试类型', dataIndex: 'testType', key: 'testType', width: 120 },
  { title: '科室', dataIndex: 'departmentId', key: 'departmentId', width: 120 },
  { title: '状态', dataIndex: 'status', key: 'status', width: 100 },
  { title: '数据量', dataIndex: 'dataSize', key: 'dataSize', width: 100 },
  { title: '耗时', dataIndex: 'duration', key: 'duration', width: 100 },
  { title: '开始时间', dataIndex: 'startTime', key: 'startTime', width: 180 },
  { title: '操作', key: 'actions', width: 150, fixed: 'right' as const },
]

// 计算属性
const testSummary = computed(() => {
  const total = testResults.value.length
  const successful = testResults.value.filter((r) => r.status === 'success').length
  const failed = testResults.value.filter((r) => r.status === 'failed').length
  const totalTime = testResults.value.reduce((sum, r) => sum + r.duration, 0)

  return {
    totalTests: total,
    successRate: total > 0 ? Math.round((successful / total) * 100) : 0,
    avgTime: total > 0 ? Math.round(totalTime / total) : 0,
    errorCount: failed,
  }
})

// 方法
const runTest = async () => {
  testing.value = true
  testLogs.value = []

  try {
    addLog('info', '开始执行测试...')
    addLog('info', `科室: ${getDepartmentName(testConfig.departmentId)}`)
    addLog('info', `测试类型: ${getTestTypeName(testConfig.testType)}`)
    addLog('info', `数据量: ${testConfig.dataSize}`)

    const startTime = new Date()

    // 模拟测试执行
    await simulateTest()

    const endTime = new Date()
    const duration = endTime.getTime() - startTime.getTime()

    // 添加测试结果
    const result = {
      id: `test_${Date.now()}`,
      testType: testConfig.testType,
      departmentId: testConfig.departmentId,
      status: (Math.random() > 0.2 ? 'success' : 'failed') as TestStatus,
      dataSize: testConfig.dataSize,
      duration,
      startTime: startTime.toLocaleString(),
      endTime: endTime.toLocaleString(),
      details: {
        rulesExecuted: Math.floor(Math.random() * 50) + 10,
        recordsProcessed: testConfig.dataSize,
        defectsFound: Math.floor(Math.random() * 20),
        averageScore: Math.floor(Math.random() * 30) + 70,
      },
      error: Math.random() > 0.2 ? null : '模拟测试错误：配置参数不匹配',
    }

    testResults.value.unshift(result)

    addLog('success', `测试完成，耗时: ${duration}ms`)
    message.success('测试执行完成')
  } catch (error: unknown) {
    addLog('error', `测试失败: ${getErrorMessage(error)}`)
    message.error('测试执行失败')
  } finally {
    testing.value = false
  }
}

const simulateTest = async () => {
  const steps = [
    '初始化测试环境...',
    '加载科室配置...',
    '准备测试数据...',
    '执行质控规则...',
    '分析测试结果...',
    '生成测试报告...',
  ]

  for (const step of steps) {
    addLog('info', step)
    await new Promise((resolve) => setTimeout(resolve, 500))
  }
}

const addLog = (level: LogLevel, message: string) => {
  testLogs.value.push({
    id: Date.now() + Math.random(),
    level,
    message,
    timestamp: new Date().toLocaleTimeString(),
  })
}

const viewDetails = (record: TestResultItem) => {
  selectedResult.value = record
  showDetailsModal.value = true
}

const retryTest = async (record: TestResultItem) => {
  // 重新执行失败的测试
  testConfig.departmentId = record.departmentId
  testConfig.testType = record.testType
  testConfig.dataSize = record.dataSize

  await runTest()
}

const exportResults = () => {
  const data = JSON.stringify(testResults.value, null, 2)
  const blob = new Blob([data], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `test_results_${new Date().toISOString().split('T')[0]}.json`
  a.click()
  URL.revokeObjectURL(url)
  message.success('测试结果已导出')
}

const clearResults = () => {
  testResults.value = []
  message.success('测试结果已清空')
}

const getTestTypeName = (type: string) => {
  const names: Record<TestType, string> = {
    rules: '规则测试',
    sampling: '抽样测试',
    workflow: '工作流测试',
    performance: '性能测试',
  }
  return names[type as TestType] || type
}

const getDepartmentName = (id: string) => {
  const dept = departments.value.find((d) => d.id === id)
  return dept ? dept.name : id
}

// 生命周期
onMounted(() => {
  // 初始化
})
</script>

<style scoped>
.department-config-test {
  padding: 24px;
}

.page-header {
  margin-bottom: 24px;
}

.page-header h1 {
  margin: 0 0 8px 0;
  font-size: 24px;
  font-weight: 600;
}

.page-header p {
  margin: 0;
  color: #666;
}

.content-wrapper {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.test-config-card,
.test-results-card,
.test-logs-card {
  margin-bottom: 24px;
}

.results-summary {
  margin-bottom: 24px;
}

.test-details {
  max-height: 600px;
  overflow-y: auto;
}

.error-section {
  margin-top: 16px;
}

.logs-container {
  max-height: 300px;
  overflow-y: auto;
  background: #f5f5f5;
  padding: 12px;
  border-radius: 4px;
}

.log-entry {
  margin-bottom: 4px;
  font-family: monospace;
  font-size: 12px;
}

.log-entry.info {
  color: #1890ff;
}

.log-entry.success {
  color: #52c41a;
}

.log-entry.error {
  color: #ff4d4f;
}

.log-time {
  color: #666;
  margin-right: 8px;
}

.log-message {
  color: inherit;
}
</style>
