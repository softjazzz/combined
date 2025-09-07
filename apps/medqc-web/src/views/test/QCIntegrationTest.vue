<template>
  <div class="qc-integration-test">
    <a-card title="质控集成功能测试" class="test-card">
      <div class="test-section">
        <h3>1. 文档质控状态显示测试</h3>
        <div class="document-cards">
          <div
            v-for="doc in testDocuments"
            :key="doc.id"
            class="test-document-card"
          >
            <div class="document-header">
              <span class="document-title">{{ doc.title }}</span>
              <div class="document-tags">
                <a-tag color="green" size="small">AI分类</a-tag>
                <a-tag
                  v-if="doc.qc_status"
                  :color="getQCStatusColor(doc.qc_status)"
                  size="small"
                >
                  {{ getQCStatusText(doc.qc_status) }}
                </a-tag>
                <a-tag
                  v-if="doc.qc_issues_count > 0"
                  color="orange"
                  size="small"
                >
                  {{ doc.qc_issues_count }}个问题
                </a-tag>
              </div>
            </div>
            <div class="document-meta">
              <span class="document-type">{{ doc.type_name }}</span>
              <span v-if="doc.qc_score !== null" class="qc-score">
                质控: {{ doc.qc_score }}分
              </span>
              <span v-if="doc.qc_last_analyzed" class="qc-time">
                {{ formatRelativeTime(doc.qc_last_analyzed) }}
              </span>
            </div>
          </div>
        </div>
      </div>

      <a-divider />

      <div class="test-section">
        <h3>2. 实时质控分析测试</h3>
        <div class="qc-test-form">
          <a-form layout="vertical">
            <a-form-item label="测试文档内容">
              <a-textarea
                v-model:value="testContent"
                :rows="6"
                placeholder="输入医疗文档内容进行质控测试..."
                @input="handleContentChange"
              />
            </a-form-item>
            <a-form-item>
              <a-space>
                <a-switch
                  v-model:checked="realTimeQCEnabled"
                  checked-children="实时质控"
                  un-checked-children="手动质控"
                />
                <a-button
                  type="primary"
                  :loading="analyzing"
                  @click="manualAnalyze"
                >
                  手动分析
                </a-button>
                <a-button @click="clearResults">清除结果</a-button>
              </a-space>
            </a-form-item>
          </a-form>
        </div>

        <!-- 质控结果展示 -->
        <div v-if="qcResult" class="qc-result-display">
          <a-card title="质控分析结果" size="small">
            <div class="qc-summary">
              <a-statistic
                title="质控评分"
                :value="qcResult.qc_score"
                suffix="/100"
                :value-style="{ 
                  color: getQCScoreColor(qcResult.qc_score),
                  fontSize: '18px',
                  fontWeight: 'bold'
                }"
              />
              <a-tag
                :color="getQCStatusColor(qcResult.qc_status)"
                class="qc-status-tag"
              >
                {{ getQCStatusText(qcResult.qc_status) }}
              </a-tag>
            </div>

            <div v-if="qcResult.results && qcResult.results.length > 0" class="qc-issues">
              <h4>检测到的问题：</h4>
              <div
                v-for="(issue, index) in qcResult.results.filter(r => !r.compliant)"
                :key="index"
                class="qc-issue-item"
              >
                <a-tag
                  :color="getIssueSeverityColor(issue.severity || 'info')"
                  size="small"
                >
                  {{ issue.rule_name }}
                </a-tag>
                <span class="issue-message">{{ issue.message }}</span>
              </div>
            </div>

            <div v-if="qcResult.suggestions && qcResult.suggestions.length > 0" class="qc-suggestions">
              <h4>改进建议：</h4>
              <ul>
                <li
                  v-for="(suggestion, index) in qcResult.suggestions"
                  :key="index"
                >
                  {{ suggestion }}
                </li>
              </ul>
            </div>
          </a-card>
        </div>

        <!-- 分析中状态 -->
        <div v-else-if="analyzing" class="analyzing-status">
          <a-spin>
            <div class="analyzing-text">
              <LoadingOutlined />
              正在进行质控分析...
            </div>
          </a-spin>
        </div>
      </div>

      <a-divider />

      <div class="test-section">
        <h3>3. 批量质控测试</h3>
        <div class="batch-qc-test">
          <a-space>
            <a-button
              type="primary"
              :loading="batchAnalyzing"
              @click="testBatchQC"
            >
              测试批量质控
            </a-button>
            <a-button @click="generateTestData">生成测试数据</a-button>
          </a-space>
          
          <div v-if="batchResult" class="batch-result">
            <a-alert
              :message="`批量质控已启动: ${batchResult.message}`"
              :description="`总文档数: ${batchResult.total_documents}, 队列任务: ${batchResult.queued_tasks}`"
              type="success"
              show-icon
            />
          </div>
        </div>
      </div>
    </a-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import { LoadingOutlined } from '@ant-design/icons-vue'
import { documentQCService } from '@/services/document-qc-service'

// 响应式数据
const testDocuments = ref([
  {
    id: 'test-doc-1',
    title: '入院记录示例',
    type_name: '入院记录',
    qc_status: 'passed',
    qc_score: 95,
    qc_issues_count: 0,
    qc_last_analyzed: new Date(Date.now() - 3600000).toISOString()
  },
  {
    id: 'test-doc-2',
    title: '病程记录示例',
    type_name: '病程记录',
    qc_status: 'warning',
    qc_score: 78,
    qc_issues_count: 2,
    qc_last_analyzed: new Date(Date.now() - 1800000).toISOString()
  },
  {
    id: 'test-doc-3',
    title: '出院记录示例',
    type_name: '出院记录',
    qc_status: 'failed',
    qc_score: 45,
    qc_issues_count: 5,
    qc_last_analyzed: new Date(Date.now() - 900000).toISOString()
  },
  {
    id: 'test-doc-4',
    title: '手术记录示例',
    type_name: '手术记录',
    qc_status: 'analyzing',
    qc_score: null,
    qc_issues_count: 0,
    qc_last_analyzed: null
  }
])

const testContent = ref('')
const realTimeQCEnabled = ref(true)
const analyzing = ref(false)
const batchAnalyzing = ref(false)
const qcResult = ref(null)
const batchResult = ref(null)
const debounceTimer = ref(null)

// 质控状态相关方法
const getQCStatusColor = (status) => {
  const statusColors = {
    'passed': 'green',
    'warning': 'orange', 
    'failed': 'red',
    'pending': 'default',
    'analyzing': 'blue'
  }
  return statusColors[status] || 'default'
}

const getQCStatusText = (status) => {
  const statusTexts = {
    'passed': '质控通过',
    'warning': '质控警告',
    'failed': '质控失败', 
    'pending': '待质控',
    'analyzing': '分析中'
  }
  return statusTexts[status] || '未知状态'
}

const getQCScoreColor = (score) => {
  if (score >= 90) return '#52c41a'
  if (score >= 80) return '#1890ff'
  if (score >= 70) return '#faad14'
  if (score >= 60) return '#fa8c16'
  return '#f5222d'
}

const getIssueSeverityColor = (severity) => {
  const colors = {
    'critical': 'red',
    'major': 'orange',
    'minor': 'yellow',
    'info': 'blue'
  }
  return colors[severity] || 'default'
}

const formatRelativeTime = (dateTime) => {
  if (!dateTime) return ''
  const now = new Date()
  const date = new Date(dateTime)
  const diffMs = now.getTime() - date.getTime()
  const diffMins = Math.floor(diffMs / (1000 * 60))
  const diffHours = Math.floor(diffMs / (1000 * 60 * 60))
  
  if (diffMins < 1) return '刚刚'
  if (diffMins < 60) return `${diffMins}分钟前`
  if (diffHours < 24) return `${diffHours}小时前`
  return date.toLocaleDateString()
}

// 实时质控相关方法
const handleContentChange = () => {
  if (!realTimeQCEnabled.value) return
  
  // 清除之前的定时器
  if (debounceTimer.value) {
    clearTimeout(debounceTimer.value)
  }
  
  // 设置新的防抖定时器
  debounceTimer.value = setTimeout(() => {
    if (testContent.value.trim().length > 20) {
      performQCAnalysis()
    }
  }, 3000)
}

const manualAnalyze = () => {
  if (testContent.value.trim().length < 10) {
    message.warning('请输入至少10个字符的内容')
    return
  }
  performQCAnalysis()
}

const performQCAnalysis = async () => {
  analyzing.value = true
  qcResult.value = null
  
  try {
    // 模拟质控分析API调用
    await new Promise(resolve => setTimeout(resolve, 2000))
    
    // 模拟质控结果
    const mockResult = {
      qc_status: Math.random() > 0.7 ? 'passed' : Math.random() > 0.4 ? 'warning' : 'failed',
      qc_score: Math.floor(Math.random() * 40) + 60,
      results: [
        {
          rule_name: '主诉完整性检查',
          compliant: Math.random() > 0.3,
          message: '主诉描述不够详细',
          severity: 'major'
        },
        {
          rule_name: '现病史逻辑性检查',
          compliant: Math.random() > 0.5,
          message: '现病史时间逻辑存在问题',
          severity: 'minor'
        }
      ],
      suggestions: [
        '建议补充主诉的详细描述',
        '建议检查现病史的时间逻辑关系'
      ]
    }
    
    qcResult.value = mockResult
    message.success('质控分析完成')
    
  } catch (error) {
    console.error('质控分析失败:', error)
    message.error('质控分析失败')
  } finally {
    analyzing.value = false
  }
}

const clearResults = () => {
  qcResult.value = null
  testContent.value = ''
  if (debounceTimer.value) {
    clearTimeout(debounceTimer.value)
  }
}

const testBatchQC = async () => {
  batchAnalyzing.value = true
  batchResult.value = null
  
  try {
    // 模拟批量质控API调用
    await new Promise(resolve => setTimeout(resolve, 1500))
    
    const mockBatchResult = {
      success: true,
      batch_task_id: 'batch-test-' + Date.now(),
      record_id: 'test-record-1',
      total_documents: 4,
      queued_tasks: 3,
      task_ids: ['task-1', 'task-2', 'task-3'],
      message: '已为 3 个文档启动质控分析'
    }
    
    batchResult.value = mockBatchResult
    message.success('批量质控测试完成')
    
  } catch (error) {
    console.error('批量质控测试失败:', error)
    message.error('批量质控测试失败')
  } finally {
    batchAnalyzing.value = false
  }
}

const generateTestData = () => {
  testContent.value = `患者，男性，45岁，因"胸痛3小时"入院。
  
主诉：胸痛3小时。

现病史：患者于3小时前无明显诱因出现胸痛，呈压榨性，位于胸骨后，向左肩背部放射，伴有出汗、恶心，无发热、咳嗽。既往有高血压病史5年，规律服用降压药物。

体格检查：T 36.8℃，P 88次/分，R 20次/分，BP 150/90mmHg。神志清楚，精神可，心界不大，心率88次/分，律齐，各瓣膜听诊区未闻及病理性杂音。双肺呼吸音清，未闻及干湿性啰音。

辅助检查：心电图示：V1-V4导联ST段抬高。

初步诊断：急性ST段抬高型心肌梗死。`
  
  message.success('测试数据已生成')
}

onMounted(() => {
  message.info('质控集成功能测试页面已加载')
})
</script>

<style scoped>
.qc-integration-test {
  padding: 20px;
  max-width: 1200px;
  margin: 0 auto;
}

.test-card {
  margin-bottom: 20px;
}

.test-section {
  margin-bottom: 30px;
}

.test-section h3 {
  color: #1890ff;
  margin-bottom: 16px;
}

.document-cards {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 16px;
}

.test-document-card {
  border: 1px solid #d9d9d9;
  border-radius: 6px;
  padding: 16px;
  background: #fafafa;
}

.document-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.document-title {
  font-weight: 500;
  color: #1f2937;
}

.document-tags {
  display: flex;
  gap: 4px;
}

.document-meta {
  display: flex;
  gap: 12px;
  font-size: 12px;
  color: #666;
}

.qc-score {
  font-weight: 500;
}

.qc-test-form {
  margin-bottom: 20px;
}

.qc-result-display {
  margin-top: 20px;
}

.qc-summary {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 16px;
}

.qc-status-tag {
  margin-left: 8px;
}

.qc-issues {
  margin-bottom: 16px;
}

.qc-issues h4,
.qc-suggestions h4 {
  font-size: 14px;
  margin-bottom: 8px;
  color: #333;
}

.qc-issue-item {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.issue-message {
  font-size: 13px;
  color: #666;
}

.qc-suggestions ul {
  margin: 0;
  padding-left: 16px;
}

.qc-suggestions li {
  font-size: 13px;
  color: #666;
  margin-bottom: 4px;
}

.analyzing-status {
  text-align: center;
  padding: 40px;
  color: #666;
}

.analyzing-text {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
}

.batch-qc-test {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.batch-result {
  margin-top: 16px;
}
</style>
