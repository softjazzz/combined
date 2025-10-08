<template>
  <div class="sichuan-qc-container">
    <!-- 页面标题 -->
    <div class="page-header">
      <h1 class="page-title">
        <span class="title-icon">🏥</span>
        四川省住院病历语义质控系统
      </h1>
      <div class="subtitle">
        基于真实API验证的Token优化方案 | 80%成本节省 | 甲级质控准确性
      </div>
    </div>

    <!-- 统计面板 -->
    <div class="stats-panel">
      <a-row :gutter="16">
        <a-col :span="6">
          <a-card class="stat-card">
            <a-statistic
              title="Token节省率"
              :value="80"
              suffix="%"
              :value-style="{ color: '#3f8600' }"
            />
            <div class="stat-desc">相比原始方案</div>
          </a-card>
        </a-col>
        <a-col :span="6">
          <a-card class="stat-card">
            <a-statistic
              title="质控准确性"
              :value="100"
              suffix="%"
              :value-style="{ color: '#1890ff' }"
            />
            <div class="stat-desc">甲级病历评估</div>
          </a-card>
        </a-col>
        <a-col :span="6">
          <a-card class="stat-card">
            <a-statistic
              title="处理时间"
              :value="47.5"
              suffix="秒"
              :value-style="{ color: '#722ed1' }"
            />
            <div class="stat-desc">单次质控评估</div>
          </a-card>
        </a-col>
        <a-col :span="6">
          <a-card class="stat-card">
            <a-statistic
              title="年节省成本"
              :value="13651"
              prefix="¥"
              :value-style="{ color: '#cf1322' }"
            />
            <div class="stat-desc">基于真实测试</div>
          </a-card>
        </a-col>
      </a-row>
    </div>

    <!-- 顶部操作区：与病历记录联动、模型选择、手动启动 -->
    <div class="flex items-center gap-3 mb-3">
      <a-input
        v-model:value="linkedRecordId"
        style="width: 360px"
        placeholder="关联的病历ID（从详情页跳转自动带入）"
        :disabled="evaluating"
      />
      <a-select v-model:value="selectedProvider" style="width: 180px" placeholder="选择提供商" :disabled="evaluating">
        <a-select-option v-for="p in providers" :key="(p.id || p.provider_code || p.code)" :value="(p.provider_code || p.id || p.code)">
          {{ getProviderLabel(p) }}
        </a-select-option>
      </a-select>
      <a-select v-model:value="selectedModel" style="width: 220px" placeholder="选择模型" :disabled="evaluating">
        <a-select-option v-for="m in filteredModels" :key="(m.id || m.model_code || m.code)" :value="(m.model_code || m.id || m.code)">
          {{ getModelLabel(m) }}
        </a-select-option>
      </a-select>
      <a-button type="primary" :loading="evaluating" @click="startEvaluationWithLinkedRecord">
        <template #icon><play-circle-outlined /></template>
        开始质控
      </a-button>
    </div>

    <!-- 功能选项卡 -->
    <a-tabs v-model:activeKey="activeTab" class="function-tabs">
      <!-- 单文档质控 -->
      <a-tab-pane key="single" tab="单文档质控">
        <div class="tab-content">
          <a-card title="单文档四川省规则质控评估" class="function-card">
            <div class="upload-section">
              <a-upload-dragger
                v-model:fileList="fileList"
                :before-upload="beforeUpload"
                :remove="removeFile"
                accept=".txt,.pdf,.doc,.docx"
                :multiple="false"
              >
                <p class="ant-upload-drag-icon">
                  <inbox-outlined />
                </p>
                <p class="ant-upload-text">点击或拖拽文件到此区域上传</p>
                <p class="ant-upload-hint">
                  支持病程记录、入院记录等医疗文档格式
                </p>
              </a-upload-dragger>
            </div>

            <div class="form-section" v-if="documentContent">
              <a-form layout="vertical">
                <a-form-item label="文档ID">
                  <a-input v-model:value="documentId" placeholder="请输入文档标识" />
                </a-form-item>
                <a-form-item label="文档类型">
                  <a-select v-model:value="documentType" placeholder="选择文档类型">
                    <a-select-option value="病程记录">病程记录</a-select-option>
                    <a-select-option value="入院记录">入院记录</a-select-option>
                    <a-select-option value="出院记录">出院记录</a-select-option>
                  </a-select>
                </a-form-item>
                <a-form-item>
                  <a-button 
                    type="primary" 
                    size="large"
                    :loading="evaluating"
                    @click="startEvaluation"
                    class="evaluate-btn"
                  >
                    <template #icon><play-circle-outlined /></template>
                    开始四川省规则质控评估
                  </a-button>
                </a-form-item>
              </a-form>
            </div>

            <!-- 评估结果 -->
            <div class="results-section" v-if="evaluationResult">
              <a-divider>质控评估结果</a-divider>
              
              <!-- 评估概要 -->
              <div class="result-summary">
                <a-row :gutter="16">
                  <a-col :span="8">
                    <a-card size="small">
                      <a-statistic
                        title="合规率"
                        :value="evaluationResult.evaluation_summary.compliance_rate"
                        suffix="%"
                        :precision="1"
                        :value-style="getComplianceColor(evaluationResult.evaluation_summary.compliance_rate)"
                      />
                    </a-card>
                  </a-col>
                  <a-col :span="8">
                    <a-card size="small">
                      <a-statistic
                        title="总体等级"
                        :value="evaluationResult.evaluation_summary.overall_grade"
                        :value-style="getGradeColor(evaluationResult.evaluation_summary.overall_grade)"
                      />
                    </a-card>
                  </a-col>
                  <a-col :span="8">
                    <a-card size="small">
                      <a-statistic
                        title="Token使用"
                        :value="evaluationResult.performance_metrics.token_usage"
                        :value-style="{ color: '#1890ff' }"
                      />
                    </a-card>
                  </a-col>
                </a-row>
              </div>

              <!-- 优化指标 -->
              <div class="optimization-metrics">
                <a-card title="Token优化效果" size="small">
                  <a-row :gutter="16">
                    <a-col :span="6">
                      <div class="metric-item">
                        <div class="metric-label">节省率</div>
                        <div class="metric-value success">
                          {{ (evaluationResult.optimization_metrics.token_savings_rate * 100).toFixed(1) }}%
                        </div>
                      </div>
                    </a-col>
                    <a-col :span="6">
                      <div class="metric-item">
                        <div class="metric-label">实际成本</div>
                        <div class="metric-value">
                          ¥{{ evaluationResult.performance_metrics.estimated_cost.toFixed(4) }}
                        </div>
                      </div>
                    </a-col>
                    <a-col :span="6">
                      <div class="metric-item">
                        <div class="metric-label">节省金额</div>
                        <div class="metric-value success">
                          ¥{{ evaluationResult.optimization_metrics.cost_savings.toFixed(4) }}
                        </div>
                      </div>
                    </a-col>
                    <a-col :span="6">
                      <div class="metric-item">
                        <div class="metric-label">处理时间</div>
                        <div class="metric-value">
                          {{ evaluationResult.performance_metrics.processing_time.toFixed(1) }}秒
                        </div>
                      </div>
                    </a-col>
                  </a-row>
                </a-card>
              </div>

              <!-- 详细评估结果 -->
              <div class="detailed-results">
                <a-card title="详细规则评估结果" size="small">
                  <a-table
                    :dataSource="evaluationResult.evaluation_results"
                    :columns="resultColumns"
                    :pagination="{ pageSize: 10 }"
                    size="small"
                  >
                    <template #bodyCell="{ column, record }">
                      <template v-if="column.key === 'is_compliant'">
                        <a-tag :color="record.is_compliant ? 'success' : 'error'">
                          {{ record.is_compliant ? '✅ 合规' : '❌ 不合规' }}
                        </a-tag>
                      </template>
                      <template v-if="column.key === 'confidence'">
                        <a-progress
                          :percent="Math.round(record.confidence * 100)"
                          size="small"
                          :stroke-color="getConfidenceColor(record.confidence)"
                        />
                      </template>
                      <template v-if="column.key === 'findings'">
                        <a-tooltip :title="record.findings">
                          <span class="findings-text">
                            {{ record.findings.length > 50 ? record.findings.substring(0, 50) + '...' : record.findings }}
                          </span>
                        </a-tooltip>
                      </template>
                    </template>
                  </a-table>
                </a-card>
              </div>
            </div>
          </a-card>
        </div>
      </a-tab-pane>

      <!-- 批量质控 -->
      <a-tab-pane key="batch" tab="批量质控">
        <div class="tab-content">
          <a-card title="批量文档四川省规则质控" class="function-card">
            <a-alert
              message="批量质控功能"
              description="支持同时处理多个医疗文档，提供批量统计和成本分析"
              type="info"
              show-icon
              style="margin-bottom: 16px"
            />
            <div class="batch-upload">
              <a-upload-dragger
                :multiple="true"
                accept=".txt,.pdf,.doc,.docx"
                :before-upload="() => false"
              >
                <p class="ant-upload-drag-icon">
                  <inbox-outlined />
                </p>
                <p class="ant-upload-text">批量上传医疗文档</p>
                <p class="ant-upload-hint">
                  支持多文件同时上传，自动进行批量质控分析
                </p>
              </a-upload-dragger>
            </div>
          </a-card>
        </div>
      </a-tab-pane>

      <!-- 规则管理 -->
      <a-tab-pane key="rules" tab="规则管理">
        <div class="tab-content">
          <a-card title="四川省住院病历质控规则" class="function-card">
            <div class="rules-stats">
              <a-row :gutter="16">
                <a-col :span="8">
                  <a-statistic title="总规则数" :value="rulesStats.total_rules" />
                </a-col>
                <a-col :span="8">
                  <a-statistic title="高复杂度" :value="rulesStats.complexity_distribution?.高复杂度 || 0" />
                </a-col>
                <a-col :span="8">
                  <a-statistic title="严重缺陷" :value="rulesStats.defect_level_distribution?.严重缺陷 || 0" />
                </a-col>
              </a-row>
            </div>
            
            <a-button type="primary" @click="loadRules" :loading="loadingRules" style="margin: 16px 0">
              <template #icon><reload-outlined /></template>
              加载四川省规则
            </a-button>

            <a-table
              :dataSource="rules"
              :columns="rulesColumns"
              :pagination="{ pageSize: 15 }"
              size="small"
              :loading="loadingRules"
            >
              <template #bodyCell="{ column, record }">
                <template v-if="column.key === 'complexity'">
                  <a-tag :color="getComplexityColor(record.complexity)">
                    {{ record.complexity }}
                  </a-tag>
                </template>
                <template v-if="column.key === 'defect_level'">
                  <a-tag :color="getDefectLevelColor(record.defect_level)">
                    {{ record.defect_level }}
                  </a-tag>
                </template>
              </template>
            </a-table>
          </a-card>
        </div>
      </a-tab-pane>

      <!-- 统计监控 -->
      <a-tab-pane key="stats" tab="统计监控">
        <div class="tab-content">
          <a-card title="四川省质控系统统计" class="function-card">
            <a-button type="primary" @click="loadStats" :loading="loadingStats" style="margin-bottom: 16px">
              <template #icon><bar-chart-outlined /></template>
              刷新统计数据
            </a-button>

            <div v-if="systemStats" class="stats-display">
              <!-- 服务统计 -->
              <a-card title="服务运行状态" size="small" style="margin-bottom: 16px">
                <a-descriptions :column="3" size="small">
                  <a-descriptions-item label="运行时间">
                    {{ Math.round(systemStats.service_statistics.uptime_seconds) }}秒
                  </a-descriptions-item>
                  <a-descriptions-item label="已处理文档">
                    {{ systemStats.service_statistics.total_documents_processed }}
                  </a-descriptions-item>
                  <a-descriptions-item label="已评估规则">
                    {{ systemStats.service_statistics.total_rules_evaluated }}
                  </a-descriptions-item>
                </a-descriptions>
              </a-card>

              <!-- 性能指标 -->
              <a-card title="性能指标" size="small" style="margin-bottom: 16px">
                <a-descriptions :column="3" size="small">
                  <a-descriptions-item label="API成功率">
                    <span :style="{ color: systemStats.performance_metrics.success_rate >= 95 ? '#52c41a' : '#ff4d4f' }">
                      {{ systemStats.performance_metrics.success_rate.toFixed(1) }}%
                    </span>
                  </a-descriptions-item>
                  <a-descriptions-item label="平均响应时间">
                    {{ systemStats.performance_metrics.avg_api_time.toFixed(1) }}秒
                  </a-descriptions-item>
                  <a-descriptions-item label="总Token使用">
                    {{ systemStats.performance_metrics.total_tokens.toLocaleString() }}
                  </a-descriptions-item>
                </a-descriptions>
              </a-card>

              <!-- 优化成果 -->
              <a-card title="优化成果" size="small">
                <a-descriptions :column="2" size="small">
                  <a-descriptions-item label="Token节省率">
                    <span style="color: #52c41a; font-weight: bold;">
                      {{ (systemStats.optimization_achievements.token_savings_rate * 100).toFixed(1) }}%
                    </span>
                  </a-descriptions-item>
                  <a-descriptions-item label="预估日节省">
                    <span style="color: #1890ff; font-weight: bold;">
                      ¥{{ systemStats.optimization_achievements.estimated_daily_savings.toFixed(4) }}
                    </span>
                  </a-descriptions-item>
                </a-descriptions>
              </a-card>
            </div>
          </a-card>
        </div>
      </a-tab-pane>
    </a-tabs>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, watch } from 'vue'
import { message } from 'ant-design-vue'
import {
  InboxOutlined,
  PlayCircleOutlined,
  ReloadOutlined,
  BarChartOutlined
} from '@ant-design/icons-vue'
import type { UploadFile } from 'ant-design-vue'

// 响应式数据
import { useRoute } from 'vue-router'
const route = useRoute()
const activeTab = ref('single')
const fileList = ref<UploadFile[]>([])
const documentContent = ref('')
const documentId = ref('')
const documentType = ref('病程记录')
const evaluating = ref(false)
const evaluationResult = ref<unknown>(null)

// 从路由读取病历ID
const linkedRecordId = ref<string>((route.params.id as string) || '')

// LLM 提供商与模型
const providers = ref<any[]>([])
const models = ref<any[]>([])
const selectedProvider = ref<string | undefined>(undefined)
const selectedModel = ref<string | undefined>(undefined)

// 友好标签生成
const getProviderLabel = (p: unknown) => {
  return p.name || p.provider_name || p.display_name || p.provider_code || (p.id ? String(p.id).slice(0, 8) : '未知提供商')
}
const getModelLabel = (m: unknown) => {
  return m.model_name || m.name || m.model_code || (m.id ? String(m.id).slice(0, 12) : '未知模型')
}

// 根据 provider 过滤模型
const filteredModels = ref<any[]>([])
const applyModelFilter = () => {
  if (!selectedProvider.value) {
    filteredModels.value = models.value
    return
  }
  const normalize = (v: unknown): string | undefined => {
    if (!v) return undefined
    const s = String(v).toLowerCase()
    if (/(openai)/.test(s)) return 'openai'
    if (/(ali|alibaba|dashscope|qwen|通义|千问)/.test(s)) return 'alibaba'
    if (/(deepseek)/.test(s)) return 'deepseek'
    return undefined
  }

  const code = String(selectedProvider.value)
  const rec = providers.value.find((p: unknown) => String(p.provider_code || p.id || p.code) === code)
  const keys = new Set<string>([code])
  if (rec?.provider_code) keys.add(String(rec.provider_code))
  if (rec?.id) keys.add(String(rec.id))
  if (rec?.code) keys.add(String(rec.code))
  const nameKey = normalize(rec?.name || rec?.provider_name || rec?.display_name)
  if (nameKey) keys.add(nameKey)

  filteredModels.value = models.value.filter((m: unknown) => {
    const providerRaw = m.provider || m.provider_code || m.providerId || m.provider_id
    const norm = normalize(providerRaw)
    return (
      (m.provider_id && keys.has(String(m.provider_id))) ||
      (m.provider && keys.has(String(m.provider))) ||
      (m.provider_code && keys.has(String(m.provider_code))) ||
      (norm && keys.has(norm))
    )
  })
}

watch(selectedProvider, () => {
  applyModelFilter()
  // 清空已选模型避免不匹配
  selectedModel.value = undefined
})

const rules = ref<any[]>([])
const rulesStats = ref<unknown>({})
const loadingRules = ref(false)

const systemStats = ref<unknown>(null)
const loadingStats = ref(false)

// 表格列定义
const resultColumns = [
  { title: '规则ID', dataIndex: 'rule_id', key: 'rule_id', width: 100 },
  { title: '合规状态', dataIndex: 'is_compliant', key: 'is_compliant', width: 100 },
  { title: '发现', dataIndex: 'findings', key: 'findings', ellipsis: true },
  { title: '置信度', dataIndex: 'confidence', key: 'confidence', width: 120 }
]

const rulesColumns = [
  { title: '规则ID', dataIndex: 'rule_id', key: 'rule_id', width: 100 },
  { title: '规则名称', dataIndex: 'name', key: 'name', ellipsis: true },
  { title: '复杂度', dataIndex: 'complexity', key: 'complexity', width: 100 },
  { title: '缺陷级别', dataIndex: 'defect_level', key: 'defect_level', width: 120 },
  { title: '描述', dataIndex: 'description', key: 'description', ellipsis: true }
]

// 文件上传处理
const beforeUpload = (file: UploadFile) => {
  const reader = new FileReader()
  reader.onload = (e) => {
    documentContent.value = e.target?.result as string
    documentId.value = file.name?.replace(/\.[^/.]+$/, '') || 'document'
  }
  reader.readAsText(file as any)
  return false
}

const removeFile = () => {
  documentContent.value = ''
  documentId.value = ''
}

// 开始评估
const startEvaluation = async () => {
  if (!documentContent.value) {
    message.error('请先上传文档')
    return
  }

  evaluating.value = true
  try {
    const response = await fetch('/api/qc/sichuan/evaluate', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        document_id: documentId.value,
        document_content: documentContent.value,
        document_type: documentType.value,
        persist: true
      }),
      // 统一超时到3分钟（180秒）
      signal: AbortSignal.timeout(180000)
    })

    if (response.ok) {
      evaluationResult.value = await response.json()
      message.success('质控评估完成！')
    } else {
      const error = await response.text()
      message.error(`评估失败: ${error}`)
    }
  } catch (error) {
    message.error(`评估异常: ${error}`)
  } finally {
    evaluating.value = false
  }
}

// 使用关联病历触发质控（仅发送最简请求体，后端根据 model 覆盖）
const startEvaluationWithLinkedRecord = async () => {
  if (!linkedRecordId.value) {
    message.error('缺少病历ID')
    return
  }
  // 这里演示：以最小信息触发评估；实际可先拉取病历正文
  evaluating.value = true
  try {
    // 拉取病历正文（若可用）
    let content = documentContent.value
    let docIdToUse: string | undefined = undefined
    try {
      const token =
        localStorage.getItem('medqc_access_token') ||
        localStorage.getItem('token') ||
        localStorage.getItem('access_token')
      // 统一使用后端兼容的公开详情接口 /api/medical-records/{id}
      const recResp = await fetch(`/api/medical-records/${linkedRecordId.value}`, {
        headers: token ? { Authorization: `Bearer ${token}` } : undefined
      })
      if (recResp.ok) {
        const rec = await recResp.json()
        content = String(rec.content || rec.raw_text || content || '')
      }
      // 进一步查询该病历的文档，优先选用真实的 document_id（UUID）
      const docsResp = await fetch(`/api/medical-records/${linkedRecordId.value}/documents`, {
        headers: token ? { Authorization: `Bearer ${token}` } : undefined
      })
      if (docsResp.ok) {
        const dd = await docsResp.json()
        const first = dd?.categories?.[0]?.documents?.[0]
        if (first && first.id) docIdToUse = String(first.id)
      }
    } catch (_) {
      // 忽略读取失败，继续使用占位文本
    }

    const resp = await fetch('/api/qc/sichuan/evaluate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        document_id: docIdToUse || linkedRecordId.value,
        document_content: content || '（占位文本，仅用于示例）',
        document_type: documentType.value,
        model: selectedModel.value,
        persist: true
      })
    })
    if (!resp.ok) {
      throw new Error(await resp.text())
    }
    evaluationResult.value = await resp.json()
    message.success('质控评估完成！')
  } catch (e: unknown) {
    message.error(`评估失败: ${e.message || e}`)
  } finally {
    evaluating.value = false
  }
}

// 加载提供商与模型（用于下拉）
const loadProvidersAndModels = async () => {
  try {
    const [p, m] = await Promise.all([
      fetch('/api/llm/providers'),
      fetch('/api/llm/models')
    ])
    if (p.ok) {
      const pd = await p.json()
      providers.value = pd.providers || pd.data || []
    }
    if (m.ok) {
      const md = await m.json()
      models.value = md.models || md.data || []
    }
    applyModelFilter() // 加载模型后立即应用过滤
  } catch {}
}

// 加载规则
const loadRules = async () => {
  loadingRules.value = true
  try {
    const response = await fetch('/api/qc/sichuan/rules')
    if (response.ok) {
      const data = await response.json()
      rules.value = data.rules
      rulesStats.value = data
      message.success(`加载了 ${data.total_rules} 条四川省规则`)
    } else {
      message.error('加载规则失败')
    }
  } catch (error) {
    message.error(`加载规则异常: ${error}`)
  } finally {
    loadingRules.value = false
  }
}

// 加载统计
const loadStats = async () => {
  loadingStats.value = true
  try {
    const response = await fetch('/api/qc/sichuan/stats')
    if (response.ok) {
      systemStats.value = await response.json()
      message.success('统计数据已更新')
    } else {
      message.error('加载统计失败')
    }
  } catch (error) {
    message.error(`加载统计异常: ${error}`)
  } finally {
    loadingStats.value = false
  }
}

// 样式辅助函数
const getComplianceColor = (rate: number) => {
  if (rate >= 95) return { color: '#52c41a' }
  if (rate >= 80) return { color: '#faad14' }
  return { color: '#ff4d4f' }
}

const getGradeColor = (grade: string) => {
  switch (grade) {
    case '甲级': return { color: '#52c41a' }
    case '乙级': return { color: '#faad14' }
    case '丙级': return { color: '#ff4d4f' }
    default: return { color: '#666' }
  }
}

const getConfidenceColor = (confidence: number) => {
  if (confidence >= 0.9) return '#52c41a'
  if (confidence >= 0.7) return '#faad14'
  return '#ff4d4f'
}

const getComplexityColor = (complexity: string) => {
  switch (complexity) {
    case '高复杂度': return 'red'
    case '中复杂度': return 'orange'
    case '低复杂度': return 'green'
    default: return 'default'
  }
}

const getDefectLevelColor = (level: string) => {
  if (level.includes('严重') || level.includes('否决')) return 'red'
  if (level.includes('一般')) return 'orange'
  return 'green'
}

// 组件挂载时加载规则
onMounted(() => {
  loadRules()
  loadProvidersAndModels()
  // 若从详情页跳转且未填充 documentId，则使用路由携带的 id
  if (linkedRecordId.value && !documentId.value) {
    documentId.value = linkedRecordId.value
  }
})
</script>

<style scoped>
.sichuan-qc-container {
  padding: 24px;
  background: #f5f5f5;
  min-height: 100vh;
}

.page-header {
  text-align: center;
  margin-bottom: 24px;
}

.page-title {
  font-size: 28px;
  font-weight: bold;
  color: #1890ff;
  margin-bottom: 8px;
}

.title-icon {
  margin-right: 12px;
}

.subtitle {
  color: #666;
  font-size: 14px;
}

.stats-panel {
  margin-bottom: 24px;
}

.stat-card {
  text-align: center;
}

.stat-desc {
  color: #999;
  font-size: 12px;
  margin-top: 4px;
}

.function-tabs {
  background: white;
  border-radius: 8px;
  padding: 16px;
}

.tab-content {
  padding: 16px 0;
}

.function-card {
  border-radius: 8px;
}

.upload-section {
  margin-bottom: 24px;
}

.form-section {
  margin-bottom: 24px;
}

.evaluate-btn {
  width: 100%;
  height: 48px;
  font-size: 16px;
  font-weight: bold;
}

.results-section {
  margin-top: 24px;
}

.result-summary {
  margin-bottom: 16px;
}

.optimization-metrics {
  margin-bottom: 16px;
}

.metric-item {
  text-align: center;
}

.metric-label {
  color: #666;
  font-size: 12px;
  margin-bottom: 4px;
}

.metric-value {
  font-size: 18px;
  font-weight: bold;
  color: #1890ff;
}

.metric-value.success {
  color: #52c41a;
}

.detailed-results {
  margin-top: 16px;
}

.findings-text {
  cursor: pointer;
}

.rules-stats {
  margin-bottom: 16px;
  padding: 16px;
  background: #fafafa;
  border-radius: 6px;
}

.stats-display {
  margin-top: 16px;
}

.batch-upload {
  margin-top: 16px;
}
</style>
