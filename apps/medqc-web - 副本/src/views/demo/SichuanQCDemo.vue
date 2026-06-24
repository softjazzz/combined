<!--
  四川质控引擎演示主页面
  展示完整的质控分析流程
-->
<template>
  <div class="sichuan-qc-demo">
    <!-- 页面标题 -->
    <a-page-header
      title="四川质控引擎演示"
      sub-title="首次病程记录质控分析 - 基于阿里云百炼 LLM"
      @back="() => $router.back()"
    >
      <template #extra>
        <a-space>
          <a-button @click="handleReset">
            <template #icon>
              <ReloadOutlined />
            </template>
            重置
          </a-button>
          <a-button
            type="primary"
            @click="handleViewDocs"
          >
            <template #icon>
              <QuestionCircleOutlined />
            </template>
            使用说明
          </a-button>
        </a-space>
      </template>
    </a-page-header>

    <!-- 统计卡片区域 -->
    <StatisticsCards
      mode="sichuan"
      :total-rules="sichuanStore.totalRules"
      :compliance-rate="sichuanStore.complianceRate"
      :critical-violations="sichuanStore.criticalViolations"
      :processing-time="sichuanStore.processingTime"
      :token-usage="sichuanStore.tokenUsage"
      :token-savings-rate="sichuanStore.tokenSavingsRate"
    />

    <!-- 主内容区域 -->
    <a-row :gutter="24">
      <!-- 左侧：病历内容 -->
      <a-col
        :xs="24"
        :lg="12"
      >
        <!-- 病历选择器 -->
        <MedicalRecordSelector
          @load-preset="sichuanStore.loadPresetExample"
          @set-custom="sichuanStore.setCustomDocument"
        />

        <!-- 病历信息卡片 -->
        <a-card
          title="病历信息"
          class="mt-4"
          :bordered="false"
        >
          <a-descriptions
            :column="2"
            bordered
            size="small"
          >
            <a-descriptions-item label="患者姓名">
              {{ sichuanStore.medicalRecordInfo.patientName }}
            </a-descriptions-item>
            <a-descriptions-item label="年龄/性别">
              {{ sichuanStore.medicalRecordInfo.age }}岁/{{ sichuanStore.medicalRecordInfo.gender }}
            </a-descriptions-item>
            <a-descriptions-item label="科室">
              {{ sichuanStore.medicalRecordInfo.department }}
            </a-descriptions-item>
            <a-descriptions-item label="住院号">
              {{ sichuanStore.medicalRecordInfo.admissionNumber }}
            </a-descriptions-item>
            <a-descriptions-item label="床号">
              {{ sichuanStore.medicalRecordInfo.bedNumber }}
            </a-descriptions-item>
            <a-descriptions-item label="入院时间">
              {{ sichuanStore.medicalRecordInfo.admissionTime }}
            </a-descriptions-item>
            <a-descriptions-item label="记录时间">
              {{ sichuanStore.medicalRecordInfo.recordTime }}
            </a-descriptions-item>
            <a-descriptions-item
              label="初步诊断"
              :span="2"
            >
              {{ sichuanStore.medicalRecordInfo.diagnosis }}
            </a-descriptions-item>
          </a-descriptions>
        </a-card>

        <!-- 开始分析按钮 -->
        <a-button
          type="primary"
          size="large"
          block
          :loading="sichuanStore.isAnalyzing"
          :disabled="!sichuanStore.documentContent"
          class="mt-4"
          @click="handleStartAnalysis"
        >
          <template #icon>
            <ThunderboltOutlined />
          </template>
          {{ sichuanStore.isAnalyzing ? '分析中...' : '开始质控分析' }}
        </a-button>

        <!-- 分析进度 -->
        <a-card
          v-if="sichuanStore.isAnalyzing"
          class="mt-4"
          :bordered="false"
        >
          <a-spin>
            <template #tip>
              <div class="analysis-progress">
                <p>正在调用四川质控引擎...</p>
                <p class="progress-detail">
                  使用阿里云百炼 LLM API（qwen2.5-14b-instruct）
                </p>
                <p class="progress-detail">
                  单次 Prompt 模式，预计耗时 20-30 秒
                </p>
              </div>
            </template>
          </a-spin>
        </a-card>
      </a-col>

      <!-- 右侧：质控结果 -->
      <a-col
        :xs="24"
        :lg="12"
      >
        <!-- 空状态 -->
        <a-empty
          v-if="!sichuanStore.qcResult"
          description="暂无质控结果"
          :image="Empty.PRESENTED_IMAGE_SIMPLE"
          class="empty-result"
        >
          <template #description>
            <p>请先选择病历并点击"开始质控分析"</p>
          </template>
        </a-empty>

        <!-- 质控结果总结 -->
        <QCResultSummary
          v-if="sichuanStore.qcResult"
          :result="sichuanStore.qcResult"
        />

        <!-- 违规项列表 -->
        <ViolationsList
          v-if="sichuanStore.qcResult"
          :violations="sichuanStore.violations"
          class="mt-4"
        />

        <!-- 操作按钮 -->
        <a-card
          v-if="sichuanStore.qcResult"
          class="mt-4"
          :bordered="false"
        >
          <a-space
            direction="vertical"
            style="width: 100%"
          >
            <a-button-group style="width: 100%">
              <a-button
                style="width: 50%"
                @click="handleExportJSON"
              >
                <template #icon>
                  <FileTextOutlined />
                </template>
                导出 JSON
              </a-button>
              <a-button
                style="width: 50%"
                @click="handleExportMarkdown"
              >
                <template #icon>
                  <FileMarkdownOutlined />
                </template>
                导出 Markdown
              </a-button>
            </a-button-group>

            <a-button
              block
              @click="handleViewFullReport"
            >
              <template #icon>
                <EyeOutlined />
              </template>
              查看完整报告
            </a-button>
          </a-space>
        </a-card>
      </a-col>
    </a-row>

    <!-- 底部：日志和性能监控 -->
    <a-row
      :gutter="24"
      class="mt-6"
    >
      <a-col
        :xs="24"
        :lg="12"
      >
        <EnhancedLogPanel
          :logs="formattedLogs"
          @clear="sichuanStore.clearLogs"
        />
      </a-col>

      <a-col
        :xs="24"
        :lg="12"
      >
        <a-card
          title="性能监控"
          :bordered="false"
        >
          <a-empty
            v-if="!sichuanStore.qcResult"
            description="暂无性能数据"
            :image="Empty.PRESENTED_IMAGE_SIMPLE"
          />

          <div v-else>
            <a-descriptions
              :column="1"
              bordered
              size="small"
            >
              <a-descriptions-item label="处理时间">
                <a-tag color="blue">
                  {{ sichuanStore.processingTime.toFixed(2) }} 秒
                </a-tag>
              </a-descriptions-item>
              <a-descriptions-item label="Token 使用量">
                <a-tag color="purple">
                  {{ sichuanStore.tokenUsage.toLocaleString() }}
                </a-tag>
              </a-descriptions-item>
              <a-descriptions-item label="Token 节省率">
                <a-tag color="green">
                  {{ (sichuanStore.tokenSavingsRate * 100).toFixed(1) }}%
                </a-tag>
              </a-descriptions-item>
              <a-descriptions-item label="预估成本">
                <a-tag color="orange">
                  ${{ sichuanStore.qcResult.performance_metrics.estimated_cost.toFixed(6) }}
                  (约 ¥{{ (sichuanStore.qcResult.performance_metrics.estimated_cost * 7).toFixed(4) }})
                </a-tag>
              </a-descriptions-item>
              <a-descriptions-item label="评估模式">
                <a-tag color="cyan">
                  {{ sichuanStore.qcResult.mode === 'single_prompt' ? '单次Prompt模式' : '多次调用模式' }}
                </a-tag>
              </a-descriptions-item>
            </a-descriptions>
          </div>
        </a-card>
      </a-col>
    </a-row>

    <!-- 完整报告模态框 -->
    <a-modal
      v-model:open="fullReportVisible"
      title="完整质控报告"
      width="80%"
      :footer="null"
    >
      <div class="full-report-content">
        <pre>{{ JSON.stringify(sichuanStore.qcResult, null, 2) }}</pre>
      </div>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { message, Empty } from 'ant-design-vue'
import { useSichuanQCStore } from '@/stores/sichuanQC'
import StatisticsCards from '@/components/demo/StatisticsCards.vue'
import MedicalRecordSelector from '@/components/demo/MedicalRecordSelector.vue'
import QCResultSummary from '@/components/demo/QCResultSummary.vue'
import ViolationsList from '@/components/demo/ViolationsList.vue'
import EnhancedLogPanel from '@/components/demo/EnhancedLogPanel.vue'
import {
  ReloadOutlined,
  QuestionCircleOutlined,
  ThunderboltOutlined,
  FileTextOutlined,
  FileMarkdownOutlined,
  EyeOutlined
} from '@ant-design/icons-vue'

// ========== 初始化 ==========

const router = useRouter()
const sichuanStore = useSichuanQCStore()

// 完整报告模态框
const fullReportVisible = ref(false)

// ========== 计算属性 ==========

/**
 * 格式化日志（转换为 EnhancedLogPanel 需要的格式）
 */
const formattedLogs = computed(() => {
  return sichuanStore.logs.map(log => ({
    timestamp: log.timestamp,
    level: log.level,
    message: log.message,
    details: log.details ? JSON.stringify(log.details) : undefined
  }))
})

// ========== 方法 ==========

/**
 * 开始质控分析
 */
const handleStartAnalysis = async () => {
  await sichuanStore.startQCAnalysis()
}

/**
 * 导出 JSON 报告
 */
const handleExportJSON = () => {
  sichuanStore.exportReport('json')
}

/**
 * 导出 Markdown 报告
 */
const handleExportMarkdown = () => {
  sichuanStore.exportReport('markdown')
}

/**
 * 查看完整报告
 */
const handleViewFullReport = () => {
  fullReportVisible.value = true
}

/**
 * 重置
 */
const handleReset = () => {
  sichuanStore.reset()
  message.info('已重置所有状态')
}

/**
 * 查看使用说明
 */
const handleViewDocs = () => {
  message.info('使用说明功能开发中...')
}

// ========== 生命周期 ==========

// 页面加载时自动加载预置示例
sichuanStore.loadPresetExample()
</script>

<style scoped lang="less">
.sichuan-qc-demo {
  padding: 24px;
  background-color: #f0f2f5;
  min-height: 100vh;

  .mt-4 {
    margin-top: 16px;
  }

  .mt-6 {
    margin-top: 24px;
  }

  .empty-result {
    padding: 60px 0;
    background-color: #fff;
    border-radius: 8px;
  }

  .analysis-progress {
    text-align: center;
    padding: 20px;

    p {
      margin: 8px 0;
      font-size: 14px;
      color: rgba(0, 0, 0, 0.85);
    }

    .progress-detail {
      font-size: 12px;
      color: rgba(0, 0, 0, 0.45);
    }
  }

  .full-report-content {
    max-height: 600px;
    overflow-y: auto;

    pre {
      background-color: #f5f5f5;
      padding: 16px;
      border-radius: 4px;
      font-size: 12px;
      line-height: 1.6;
    }
  }
}
</style>

