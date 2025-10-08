<template>
  <div class="api-test-container">
    <div class="header">
      <h1>医疗质控API测试</h1>
      <p>测试三层漏斗Token优化技术的后端API集成</p>
    </div>

    <!-- 系统状态 -->
    <a-card title="系统状态" class="mb-4">
      <div class="status-grid">
        <a-statistic
          title="服务状态"
          :value="systemStatus?.status || '未知'"
          :value-style="{ color: systemStatus?.status === 'running' ? '#3f8600' : '#cf1322' }"
        />
        <a-statistic
          title="服务版本"
          :value="systemStatus?.version || '未知'"
        />
        <a-statistic
          title="健康状态"
          :value="healthStatus?.status || '未知'"
          :value-style="{ color: healthStatus?.status === 'healthy' ? '#3f8600' : '#cf1322' }"
        />
      </div>
      
      <a-button @click="checkSystemStatus" :loading="statusLoading" class="mt-4">
        刷新状态
      </a-button>
    </a-card>

    <!-- 优化演示 -->
    <a-card title="三层漏斗优化演示" class="mb-4">
      <div v-if="demoData" class="demo-content">
        <div class="optimization-stats">
          <a-row :gutter="16">
            <a-col :span="6">
              <a-statistic
                title="压缩比例"
                :value="demoData.benefits?.average_compression_ratio || '未知'"
              />
            </a-col>
            <a-col :span="6">
              <a-statistic
                title="Token节省率"
                :value="demoData.benefits?.token_savings_rate || '未知'"
              />
            </a-col>
            <a-col :span="6">
              <a-statistic
                title="成本降低"
                :value="demoData.benefits?.cost_reduction || '未知'"
              />
            </a-col>
            <a-col :span="6">
              <a-statistic
                title="处理时间减少"
                :value="demoData.benefits?.processing_time_reduction || '未知'"
              />
            </a-col>
          </a-row>
        </div>

        <div class="workflow-steps mt-4">
          <h4>优化工作流程：</h4>
          <a-steps direction="vertical" size="small">
            <a-step
              v-for="(step, index) in demoData.workflow"
              :key="index"
              :title="step"
              status="finish"
            />
          </a-steps>
        </div>

        <div class="real-world-impact mt-4">
          <h4>实际效果：</h4>
          <ul>
            <li><strong>年度成本节省：</strong>{{ demoData.real_world_impact?.annual_cost_savings }}</li>
            <li><strong>Token使用减少：</strong>{{ demoData.real_world_impact?.token_usage_reduction }}</li>
            <li><strong>准确率保持：</strong>{{ demoData.real_world_impact?.accuracy_maintained }}</li>
          </ul>
        </div>
      </div>
      
      <a-button @click="loadDemo" :loading="demoLoading" class="mt-4">
        加载演示数据
      </a-button>
    </a-card>

    <!-- 质控分析测试 -->
    <a-card title="质控分析测试" class="mb-4">
      <a-form layout="vertical">
        <a-form-item label="病历ID">
          <a-input v-model:value="testRequest.record_id" placeholder="例如：MR_20241223_001" />
        </a-form-item>
        
        <a-form-item label="病历内容">
          <a-textarea
            v-model:value="testRequest.record_text"
            :rows="6"
            placeholder="请输入病历内容进行质控分析..."
          />
        </a-form-item>
        
        <a-form-item label="质控规则">
          <a-select
            v-model:value="testRequest.rule_ids"
            mode="multiple"
            placeholder="选择要应用的质控规则"
          >
            <a-select-option value="S3.5.1">主诉与主要诊断一致性</a-select-option>
            <a-select-option value="S4.13.2b">病史逻辑合理性</a-select-option>
            <a-select-option value="S5.10.1">治疗方案适宜性</a-select-option>
          </a-select>
        </a-form-item>
        
        <a-form-item>
          <a-checkbox v-model:checked="testRequest.enable_optimization">
            启用三层漏斗优化
          </a-checkbox>
        </a-form-item>
        
        <a-form-item>
          <a-button type="primary" @click="runAnalysis" :loading="analysisLoading">
            开始分析
          </a-button>
          <a-button @click="loadSampleData" class="ml-2">
            加载示例数据
          </a-button>
        </a-form-item>
      </a-form>
      
      <!-- 分析结果 -->
      <div v-if="analysisResult" class="analysis-result mt-4">
        <a-divider>分析结果</a-divider>
        
        <!-- 优化统计 -->
        <div v-if="analysisResult.optimization_stats" class="optimization-stats mb-4">
          <h4>Token优化效果：</h4>
          <a-row :gutter="16">
            <a-col :span="8">
              <a-statistic
                title="原始Token数"
                :value="analysisResult.optimization_stats.original_tokens"
              />
            </a-col>
            <a-col :span="8">
              <a-statistic
                title="优化后Token数"
                :value="analysisResult.optimization_stats.optimized_tokens"
              />
            </a-col>
            <a-col :span="8">
              <a-statistic
                title="压缩率"
                :value="(analysisResult.optimization_stats.compression_ratio * 100).toFixed(1)"
                suffix="%"
              />
            </a-col>
          </a-row>
        </div>
        
        <!-- 质控结果 -->
        <div class="qc-results">
          <h4>质控结果：</h4>
          <a-table
            :dataSource="analysisResult.rule_results"
            :columns="resultColumns"
            :pagination="false"
            size="small"
          />
        </div>
        
        <!-- 总体统计 -->
        <div class="total-stats mt-4">
          <a-row :gutter="16">
            <a-col :span="8">
              <a-statistic
                title="总处理时间"
                :value="analysisResult.total_processing_time"
                suffix="秒"
                :precision="2"
              />
            </a-col>
            <a-col :span="8">
              <a-statistic
                title="总Token使用"
                :value="analysisResult.total_tokens_used"
              />
            </a-col>
            <a-col :span="8">
              <a-statistic
                title="预估成本"
                :value="analysisResult.total_cost_estimate"
                prefix="$"
                :precision="3"
              />
            </a-col>
          </a-row>
        </div>
      </div>
    </a-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import { medicalQcApi, type QCAnalysisRequest, type QCAnalysisResponse, type SystemStatus } from '@/services/medicalQcApi'

// 响应式数据
const systemStatus = ref<SystemStatus | null>(null)
const healthStatus = ref<unknown>(null)
const demoData = ref<unknown>(null)
const analysisResult = ref<QCAnalysisResponse | null>(null)

// 加载状态
const statusLoading = ref(false)
const demoLoading = ref(false)
const analysisLoading = ref(false)

// 测试请求数据
const testRequest = ref<QCAnalysisRequest>({
  record_id: 'MR_20241223_001',
  record_text: '',
  rule_ids: ['S3.5.1'],
  max_tokens: 500,
  enable_optimization: true
})

// 表格列定义
const resultColumns = [
  { title: '规则ID', dataIndex: 'rule_id', key: 'rule_id' },
  { title: '规则名称', dataIndex: 'rule_name', key: 'rule_name' },
  { title: '结果', dataIndex: 'result', key: 'result' },
  { title: '置信度', dataIndex: 'confidence', key: 'confidence' },
  { title: '缺陷等级', dataIndex: 'defect_level', key: 'defect_level' },
  { title: '推理过程', dataIndex: 'reasoning', key: 'reasoning' },
]

// 检查系统状态
const checkSystemStatus = async () => {
  statusLoading.value = true
  try {
    const [status, health] = await Promise.all([
      medicalQcApi.getSystemStatus(),
      medicalQcApi.healthCheck()
    ])
    systemStatus.value = status
    healthStatus.value = health
    message.success('系统状态检查完成')
  } catch (error) {
    message.error('系统状态检查失败')
    console.error(error)
  } finally {
    statusLoading.value = false
  }
}

// 加载演示数据
const loadDemo = async () => {
  demoLoading.value = true
  try {
    const demo = await medicalQcApi.getOptimizationDemo()
    demoData.value = demo
    message.success('演示数据加载完成')
  } catch (error) {
    message.error('演示数据加载失败')
    console.error(error)
  } finally {
    demoLoading.value = false
  }
}

// 运行质控分析
const runAnalysis = async () => {
  if (!testRequest.value.record_text.trim()) {
    message.warning('请输入病历内容')
    return
  }
  
  analysisLoading.value = true
  try {
    const result = await medicalQcApi.analyzeRecord(testRequest.value)
    analysisResult.value = result
    message.success('质控分析完成')
  } catch (error) {
    message.error('质控分析失败')
    console.error(error)
  } finally {
    analysisLoading.value = false
  }
}

// 加载示例数据
const loadSampleData = () => {
  testRequest.value = {
    record_id: 'MR_20241223_001',
    record_text: `患者张某，男，45岁，因胸痛3小时入院。
    
主诉：胸痛3小时。

现病史：患者于3小时前无明显诱因出现胸痛，呈压榨性，伴有出汗、恶心，无放射痛。疼痛持续不缓解，遂来我院就诊。

既往史：高血压病史5年，规律服药控制。

体格检查：T 36.5℃，P 88次/分，R 20次/分，BP 150/90mmHg。神志清楚，精神可，心率88次/分，律齐，各瓣膜听诊区未闻及病理性杂音。

辅助检查：心电图示：V1-V4导联ST段抬高。

诊断：急性前壁心肌梗死

治疗：给予阿司匹林、氯吡格雷双抗血小板，阿托伐他汀调脂，美托洛尔控制心率等治疗。`,
    rule_ids: ['S3.5.1', 'S4.13.2b', 'S5.10.1'],
    max_tokens: 500,
    enable_optimization: true
  }
  message.success('示例数据已加载')
}

// 组件挂载时检查系统状态
onMounted(() => {
  checkSystemStatus()
  loadDemo()
})
</script>

<style scoped>
.api-test-container {
  padding: 24px;
  max-width: 1200px;
  margin: 0 auto;
}

.header {
  text-align: center;
  margin-bottom: 32px;
}

.header h1 {
  font-size: 2rem;
  margin-bottom: 8px;
  color: #1f2937;
}

.header p {
  color: #6b7280;
  font-size: 1.1rem;
}

.status-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 16px;
  margin-bottom: 16px;
}

.demo-content {
  background: #f9fafb;
  padding: 16px;
  border-radius: 8px;
}

.optimization-stats {
  background: white;
  padding: 16px;
  border-radius: 8px;
  margin-bottom: 16px;
}

.workflow-steps {
  background: white;
  padding: 16px;
  border-radius: 8px;
  margin-bottom: 16px;
}

.real-world-impact {
  background: white;
  padding: 16px;
  border-radius: 8px;
}

.real-world-impact ul {
  margin: 8px 0;
  padding-left: 20px;
}

.real-world-impact li {
  margin: 4px 0;
}

.analysis-result {
  background: #f9fafb;
  padding: 16px;
  border-radius: 8px;
}

.qc-results {
  margin: 16px 0;
}

.total-stats {
  background: white;
  padding: 16px;
  border-radius: 8px;
}

.mb-4 {
  margin-bottom: 16px;
}

.mt-4 {
  margin-top: 16px;
}

.ml-2 {
  margin-left: 8px;
}
</style>
