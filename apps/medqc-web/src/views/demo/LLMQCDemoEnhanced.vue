<template>
  <div class="llm-qc-demo-enhanced">
    <!-- 页面头部 -->
    <div class="demo-header">
      <div class="header-content">
        <div class="title-section">
          <h1 class="demo-title">
            <ExperimentOutlined class="title-icon" />
            LLM集成质控系统演示
          </h1>
          <p class="demo-description">
            展示基于大语言模型的医疗质控规则执行系统 - 完整功能演示
          </p>
        </div>

        <!-- 右侧精简操作：仅保留“更多”菜单，减少首屏干扰 -->
        <div class="header-actions">
          <a-dropdown>
            <template #overlay>
              <a-menu @click="handleMenuAction">
                <a-menu-item key="export">
                  <DownloadOutlined />
                  导出演示数据
                </a-menu-item>
                <a-menu-item key="import">
                  <UploadOutlined />
                  导入演示数据
                </a-menu-item>
                <a-menu-divider />
                <a-menu-item key="clear">
                  <DeleteOutlined />
                  清除保存状态
                </a-menu-item>
                <a-menu-item key="config">
                  <SettingOutlined />
                  演示配置
                </a-menu-item>
              </a-menu>
            </template>
            <a-button size="small">
              <MoreOutlined />
              更多
            </a-button>
          </a-dropdown>
        </div>
      </div>
    </div>



    <!-- 统计卡片 / 日志 / 性能监控 已移动到页面下方折叠区，默认收起，减少首屏干扰 -->

    <!-- 演示配置模态框 - 使用子组件 -->
    <DemoConfigModal
      v-model:open="showConfigModal"
      v-model:config="demoConfig"
    />

    <!-- 原有的内容继续... -->
    <div class="demo-content-placeholder">
      <!-- 这里保留原有的步骤导航和其他内容 -->
      <div v-if="false" class="legacy-controls">
        <div class="demo-controls">
          <a-space wrap>
            <a-button
              type="primary"
              @click="handleStartDemo"
              :loading="demoStore.isRunning"
              :disabled="!demoStore.canStartDemo"
            >
              <PlayCircleOutlined />
              {{ demoStore.isRunning ? '分析进行中' : '开始分析' }}
            </a-button>

            <a-button
              v-if="demoStore.isRunning"
              @click="demoStore.togglePause"
            >
              <PauseCircleOutlined v-if="!demoStore.isPaused" />
              <PlayCircleOutlined v-else />
              {{ demoStore.isPaused ? '继续' : '暂停' }}
            </a-button>

            <a-button
              v-if="demoStore.isRunning"
              @click="handleStopDemo"
              danger
            >
              <StopOutlined />
              停止
            </a-button>

            <a-button @click="handleReplayDemo">
              <ReloadOutlined />
              重播
            </a-button>

            <a-divider type="vertical" />

            <!-- 步骤导航 -->
            <a-button
              :icon="h(LeftOutlined)"
              @click="demoStore.previousStep()"
              :disabled="demoStore.currentStep === 'target'"
              size="small"
            >
              上一步
            </a-button>

            <a-select
              :value="demoStore.currentStep"
              @change="handleStepJump"
              style="width: 120px"
              size="small"
            >
              <a-select-option value="target">测试对象</a-select-option>
              <a-select-option value="rules">规则配置</a-select-option>
              <a-select-option value="run">运行与结果</a-select-option>
            </a-select>

            <a-button
              :icon="h(RightOutlined)"
              @click="demoStore.nextStep()"
              :disabled="demoStore.currentStep === 'run'"
              size="small"
            >
              下一步
            </a-button>

            <a-divider type="vertical" />

            <!-- 更多操作 -->
            <a-dropdown>
              <template #overlay>
                <a-menu @click="handleMenuAction">
                  <a-menu-item key="export">
                    <DownloadOutlined />
                    导出演示数据
                  </a-menu-item>
                  <a-menu-item key="import">
                    <UploadOutlined />
                    导入演示数据
                  </a-menu-item>
                  <a-menu-divider />
                  <a-menu-item key="clear">
                    <DeleteOutlined />
                    清除保存状态
                  </a-menu-item>
                  <a-menu-item key="config">
                    <SettingOutlined />
                    演示配置
                  </a-menu-item>
                </a-menu>
              </template>
              <a-button size="small">
                <MoreOutlined />
                更多
              </a-button>
            </a-dropdown>
          </a-space>
        </div>
      </div>

      <!-- 进度条 -->
      <div class="progress-section" v-if="demoStore.isRunning || demoStore.progress > 0">
        <a-progress
          :percent="demoStore.progress"
          :status="demoStore.error ? 'exception' : 'active'"
          :stroke-color="getProgressColor()"
        />
        <div class="progress-steps">
          <div
            v-for="(step, index) in demoSteps"
            :key="step.key"
            class="step-item"
            :class="{
              active: demoStore.currentStep === step.key,
              completed: getStepIndex(demoStore.currentStep) > index
            }"
          >
            <div class="step-icon">
              <component :is="step.icon" />
            </div>
            <div class="step-label">{{ step.label }}</div>
          </div>
        </div>
      </div>
    </div>

    <!-- 顶部状态栏（精简：仅在“加载中/失败”时显示，成功时不显示） -->
    <div class="status-bar">
      <a-alert
        v-if="demoStore.isLoadingData"
        message="正在自动连接数据库..."
        type="info"
        show-icon
      >
        <template #icon>
          <LoadingOutlined spin />
        </template>
      </a-alert>
      <a-alert
        v-else-if="!demoStore.isDatabaseConnected"
        message="数据库连接失败，已自动切换到本地模拟数据"
        type="warning"
        show-icon
      >
        <template #action>
          <a-button size="small" @click="handleRefreshData" :loading="demoStore.isLoadingData">
            重试连接
          </a-button>
        </template>
      </a-alert>
    </div>

    <!-- 错误提示 -->
    <a-alert
      v-if="demoStore.error"
      :message="demoStore.error"
      type="error"
      show-icon
      closable
      @close="demoStore.error = null"
      class="error-alert"
    />

    <!-- 全屏主工作区 -->
    <div class="demo-content">
      <!-- 全屏主工作区 -->
      <div class="demo-display">
        <!-- 当前步骤指示器 -->
        <div class="step-indicator">
          <a-tag :color="getStepColor(demoStore.currentStep)" size="large">
            <component :is="getCurrentStepIcon()" />
            {{ getCurrentStepLabel() }}
          </a-tag>

          <div class="step-navigation" v-if="demoStore.isRunning">
            <a-button
              size="small"
              @click="demoStore.previousStep"
              :disabled="demoStore.currentStep === 'target'"
            >
              <LeftOutlined />
              上一步
            </a-button>
            <a-button
              size="small"
              type="primary"
              @click="demoStore.nextStep"
              :disabled="demoStore.currentStep === 'run'"
            >
              下一步
              <RightOutlined />
            </a-button>
          </div>
        </div>

        <!-- 条件引导提示（在非“测试对象”步骤时显示，且使用非 banner 样式，更克制） -->
        <div class="readiness-alert" v-if="demoStore.currentStep !== 'target'">
          <a-alert
            :type="readinessAlert.type"
            :message="readinessAlert.message"
            show-icon
          />
          <div class="readiness-actions" style="margin-top: 8px;">
            <a-space>
              <a-button
                v-if="!demoStore.testRecord || (demoStore.selectedDocumentList?.length||0)===0"
                size="small"
                @click="demoStore.currentStep = 'target' as any"
              >
                去选择对象
              </a-button>
              <a-button
                v-if="demoStore.selectedRules.length === 0"
                size="small"
                @click="demoStore.currentStep = 'rules' as any"
              >
                去规则配置
              </a-button>
              <a-button
                v-if="demoStore.canStartDemo"
                size="small"
                type="primary"
                @click="handleStartDemo"
              >
                立即分析
              </a-button>
            </a-space>
          </div>
        </div>

        <!-- 动态内容区域 -->
        <div class="content-area">
          <!-- 测试对象选择 -->
          <div v-if="demoStore.currentStep === 'target'" class="step-content">
            <!-- 快速开始提示 -->
            <a-alert
              v-if="!demoStore.testRecord"
              message="快速开始"
              description="点击下方按钮快速加载预置示例，或手动选择病历与文书"
              type="info"
              show-icon
              class="mb-4"
            />

            <!-- 已选病历信息卡片 -->
            <MedicalRecordInfoCard
              v-if="demoStore.testRecord && demoStore.currentRecordInfo"
              :record-info="demoStore.currentRecordInfo"
              :document-info="demoStore.currentDocumentInfo"
              class="mb-4"
            />

            <!-- 操作按钮 -->
            <a-space direction="vertical" style="width: 100%" :size="16">
              <a-button
                v-if="!demoStore.testRecord"
                type="primary"
                size="large"
                block
                @click="handleQuickStart"
              >
                <ThunderboltOutlined />
                快速开始（加载预置示例）
              </a-button>

              <a-button
                size="large"
                block
                @click="showTargetPicker = true"
              >
                <FileSearchOutlined />
                {{ demoStore.testRecord ? '重新选择病历与文书' : '手动选择病历与文书' }}
              </a-button>

              <!-- 已选择病历时仍可一键重置并加载预置示例 -->
              <a-button
                v-if="demoStore.testRecord"
                danger
                block
                @click="handleQuickStart(true)"
              >
                <ThunderboltOutlined />
                重置并快速开始
              </a-button>

              <a-button
                v-if="demoStore.testRecord && (demoStore.selectedDocumentList?.length||0) > 0"
                type="primary"
                size="large"
                block
                @click="demoStore.currentStep = 'rules' as any"
              >
                <RightOutlined />
                前往规则配置
              </a-button>
            </a-space>
          </div>

          <!-- 规则配置 -->
          <div v-else-if="demoStore.currentStep === 'rules'" class="step-content">
            <QCRulesDemoPanel
              :selected-rules="demoStore.selectedRules"
              :available-rules="demoStore.applicableRules"
              :test-record="demoStore.testRecord"
              :selected-documents="demoStore.selectedDocumentList"
              @rules-updated="handleRulesUpdated"
              @start-analysis="handleStartDemo"
            />
          </div>

          <!-- 运行与结果（合并原分析/完成等） -->
          <div v-else class="step-content">
            <!-- 有结果：显示总结 + 违规列表 -->
            <template v-if="demoStore.analysisResult">
              <QCResultSummary :result="demoStore.analysisResult" />
              <ViolationsList class="mt-4" :violations="demoStore.analysisResult.violations || []" />
            </template>

            <!-- 无结果且未运行：显示空态提示 -->
            <EmptyResultState
              v-else-if="!demoStore.isRunning"
              @start-analysis="handleStartDemo"
              @go-back="demoStore.currentStep = 'rules'"
            />

            <!-- 分析中或有结果：显示分析面板 -->
            <QCAnalysisDemoPanel
              v-if="demoStore.isRunning || demoStore.analysisResult"
              :analysis-steps="demoStore.analysisSteps"
              :analysis-result="demoStore.analysisResult"
              :is-running="demoStore.isRunning"
              @analysis-complete="handleAnalysisComplete"
            />
          </div>

          <!-- 暂停遮罩（覆盖整个演示区） -->
          <div v-if="demoStore.isPaused" class="paused-overlay">
            <span>已暂停</span>
          </div>
        </div>
      </div>
    </div>

    <!-- 折叠区：统计/日志/性能（默认收起，减少首屏信息量） -->
    <div class="mt-4">
      <a-collapse :default-active-key="[]">
        <a-collapse-panel key="stats" header="统计与进度">
          <StatisticsCards
            :selected-rules-count="demoStore.selectedRulesCount"
            :total-rules-count="demoStore.totalRulesCount"
            :analysis-completed-count="demoStore.analysisCompletedCount"
            :total-records-count="demoStore.totalRecordsCount"
            :unread-notifications-count="demoStore.unreadNotificationsCount"
            :total-notifications-count="demoStore.totalNotificationsCount"
            :pending-appeals-count="demoStore.pendingAppealsCount"
            :total-appeals-count="demoStore.totalAppealsCount"
            :average-q-c-score="demoStore.averageQCScore"
            :is-running="demoStore.isRunning"
            :start-time="demoStore.demoStartTime"
          />
        </a-collapse-panel>
        <a-collapse-panel key="logs" header="演示日志">
          <EnhancedLogPanel :logs="demoStore.demoLogs" @clear="demoStore.clearDemoLogs" />
        </a-collapse-panel>
        <a-collapse-panel key="perf" header="性能监控">
          <PerformanceMonitor
            v-if="demoStore.performanceMonitorEnabled"
            :step-timings="demoStore.stepTimings"
            :api-calls="demoStore.apiCalls"
            :memory-info="demoStore.memoryInfo"
            @export="handlePerformanceExport"
            @reset="demoStore.resetPerformanceData"
          />
          <a-alert v-else type="info" message="默认不启用性能监控，可通过菜单开启后查看" show-icon />
        </a-collapse-panel>
      </a-collapse>
    </div>


    <!-- 通知模态框 -->
    <QCNotificationModal
      v-model:visible="demoStore.showNotificationModal"
      :notification="demoStore.activeNotification"
      @action="handleNotificationModalAction"
    />

    <!-- 申诉模态框 -->
    <QCAppealModal
      v-model:visible="demoStore.showAppealModal"
      :notification="demoStore.activeNotification"
      @appeal-submitted="handleAppealSubmitted"
    />

    <!-- 演示配置模态框 -->
    <a-modal
      v-model:visible="showConfigModal"
      title="演示配置"
      width="600px"
      @ok="handleConfigSave"
    >
      <a-form layout="vertical">
        <a-form-item label="自动推进">


          <a-switch
            v-model:checked="configForm.autoAdvance"
            checked-children="开启"
            un-checked-children="关闭"
          />
          <div class="form-help">开启后演示将自动进行到下一步</div>
        </a-form-item>

        <a-form-item label="步骤间隔时间（秒）">
          <a-input-number
            v-model:value="configForm.stepDelay"
            :min="1"
            :max="60"
            style="width: 100%"
          />
        </a-form-item>

        <a-form-item label="显示详细日志">
          <a-switch
            v-model:checked="configForm.showDetailedLogs"
            checked-children="显示"
            un-checked-children="隐藏"
          />
        </a-form-item>

        <a-form-item label="模拟延迟">
          <a-switch
            v-model:checked="configForm.enableSimulationDelay"
            checked-children="启用"
            un-checked-children="禁用"
          />
          <div class="form-help">启用后会模拟真实的处理时间</div>
        </a-form-item>
      </a-form>
    </a-modal>


    <!-- 病历与文书合并选择器 -->
    <RecordDocumentPicker v-model="showTargetPicker" @picked="onTargetPicked" />

    <!-- 隐藏的文件输入 -->
    <input
      ref="fileInputRef"
      type="file"
      accept=".json"
      style="display: none"
      @change="handleFileImport"
    />

    <!-- 暂停遮罩 -->
    <PauseOverlay
      :visible="demoStore.isPaused"
      :current-step="demoStore.currentStep"
      :progress="demoStore.progress"
      :pause-start-time="demoStore.pauseStartTime"
      @resume="demoStore.togglePause"
      @stop="handleStopDemo"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, h, computed } from 'vue'
import { message, Modal } from 'ant-design-vue'
import {
  ExperimentOutlined,
  PlayCircleOutlined,
  PauseCircleOutlined,
  StopOutlined,
  ReloadOutlined,
  SettingOutlined,
  FileTextOutlined,
  LeftOutlined,
  RightOutlined,
  CheckCircleOutlined,
  MoreOutlined,
  DownloadOutlined,
  UploadOutlined,
  DeleteOutlined,
  LoadingOutlined,
  ThunderboltOutlined,
  FileSearchOutlined
} from '@ant-design/icons-vue'

import QCResultSummary from '@/components/demo/QCResultSummary.vue'
import ViolationsList from '@/components/demo/ViolationsList.vue'

// 导入新的子组件（精简：移除顶部 DemoControls/StepProgress）
import DemoConfigModal from '@/components/demo/DemoConfigModal.vue'
import PauseOverlay from '@/components/demo/PauseOverlay.vue'
import StatisticsCards from '@/components/demo/StatisticsCards.vue'
import EnhancedLogPanel from '@/components/demo/EnhancedLogPanel.vue'
import PerformanceMonitor from '@/components/demo/PerformanceMonitor.vue'
import MedicalRecordInfoCard from '@/components/demo/MedicalRecordInfoCard.vue'
import EmptyResultState from '@/components/demo/EmptyResultState.vue'

import { useQCDemoStore } from '@/stores/qcDemo'
import type { QualityControlRule, Appeal } from '@/types/quality-control'

// 引入子组件
import QCRulesDemoPanel from '@/components/demo/QCRulesDemoPanel.vue'
import QCAnalysisDemoPanel from '@/components/demo/QCAnalysisDemoPanel.vue'
import QCNotificationModal from '@/components/demo/QCNotificationModal.vue'
import QCAppealModal from '@/components/demo/QCAppealModal.vue'
import RecordDocumentPicker from '@/components/demo/RecordDocumentPicker.vue'

// Store
const demoStore = useQCDemoStore()

// 响应式数据
const demoSpeed = ref(2000)
const showConfigModal = ref(false)
const fileInputRef = ref<HTMLInputElement>()
const showTargetPicker = ref(false)

// 演示配置（用于 DemoConfigModal）
const demoConfig = ref({
  autoAdvance: true,
  stepDelay: 1000,
  showLogs: true,
  simulateDelay: true,
  debugMode: false,
  autoNotifications: true,
  notificationInterval: 3,
  persistState: true,
  stateExpiryHours: 24
})

// 配置表单数据（保留旧的，用于兼容）
const configForm = ref({
  autoAdvance: false,
  stepDelay: 3,
  showDetailedLogs: true,
  enableSimulationDelay: true
})

// 演示步骤配置
const demoSteps = [
  { key: 'target', label: '测试对象', icon: FileTextOutlined },
  { key: 'rules', label: '规则配置', icon: FileTextOutlined },
  { key: 'run', label: '运行与结果', icon: CheckCircleOutlined }
]

// 计算属性
const getCurrentStepLabel = () => {
  const step = demoSteps.find(s => s.key === demoStore.currentStep)
  return step?.label || '运行与结果'
}

const getCurrentStepIcon = () => {
  const step = demoSteps.find(s => s.key === demoStore.currentStep)
  return step?.icon || CheckCircleOutlined
}

const getStepIndex = (stepKey: string) => {
  return demoSteps.findIndex(s => s.key === stepKey)
}

const getStepColor = (stepKey: string) => {
  const colors = {
    target: 'blue',
    rules: 'orange',
    run: 'green'
  }
  return colors[stepKey as keyof typeof colors] || 'default'
}

const getProgressColor = () => {
  if (demoStore.error) return '#ff4d4f'
  if (demoStore.currentStep === 'run' && demoStore.analysisResult) return '#52c41a'
  return '#1890ff'
}

// 条件引导提示计算属性（加入文书选择）
const readinessAlert = computed(() => {
  const hasRecord = !!demoStore.testRecord
  const hasDoc = (demoStore.selectedDocumentList?.length || 0) > 0
  const hasRules = demoStore.selectedRules.length > 0

  if (hasRecord && hasDoc && hasRules) {
    return { type: 'success', message: '条件满足，点击“开始分析”进入运行与结果' }
  }
  if (!hasRecord) {
    return { type: 'warning', message: '请先选择测试对象（病历+文书）' }
  }
  if (hasRecord && !hasDoc) {
    return { type: 'warning', message: '已选择病历，请继续选择文书' }
  }
  if (!hasRules) {
    return { type: 'warning', message: '请在右侧“质控规则管理”中选择要应用的规则' }
  }
  return { type: 'info', message: '请完善测试对象与规则' }
})



// 事件处理
const handleStartDemo = async () => {
  try {
    demoStore.demoConfig.stepDelay = demoSpeed.value
    await demoStore.startDemo()
    message.success('分析已开始')
  } catch (error) {
    message.error(`启动分析失败: ${error instanceof Error ? error.message : '未知错误'}`)
  }
}


// 规则选择现在完全在右侧规则演示面板处理，通过 handleRulesUpdated 事件

const handleRefreshData = async () => {
  try {
    const loadingMessage = message.loading('正在重新连接数据库并刷新数据...', 0)
    console.log('[LLM质控演示] 开始手动刷新数据...')
    console.log('[LLM质控演示] 刷新前状态:', {
      records: demoStore.availableRecords.length,
      rules: demoStore.availableRules.length,
      connected: demoStore.isDatabaseConnected
    })

    // 使用新的重置连接方法
    await demoStore.resetConnection()

    loadingMessage()

    console.log('[LLM质控演示] 刷新后状态:', {
      records: demoStore.availableRecords.length,
      rules: demoStore.availableRules.length,
      connected: demoStore.isDatabaseConnected
    })

/*

//   
const onTargetPicked = ({ record, document }: { record: unknown; document: { id: string; title?: string; type?: string; created_at?: string } }) => {
  demoStore.testRecord = record as any
  demoStore.setSelectedDocument(document)
  message.success(` a已选择：${record.patient_name} · ${document.title}`)
*/



    // 根据连接状态显示不同的成功消息
    if (demoStore.isDatabaseConnected) {
      message.success(`✅ 数据库重连成功！已加载 ${demoStore.availableRecords.length} 条记录和 ${demoStore.availableRules.length} 条规则`, 3)
    } else {
      message.warning(`⚠️ 数据库连接失败，已切换到模拟数据模式 (${demoStore.availableRecords.length} 条记录，${demoStore.availableRules.length} 条规则)`, 4)
    }

  } catch (error) {
    console.error('[LLM质控演示] 刷新数据失败:', error)
    const errorMessage = error instanceof Error ? error.message : '未知错误'
    message.error(`❌ 数据刷新失败: ${errorMessage}`, 5)
  }
}



// 事件处理函数
const handleRulesUpdated = (rules: QualityControlRule[]) => {
  const previousCount = demoStore.selectedRules.length
  demoStore.selectedRules = rules

  // 如果是首次选择规则（从0到有规则），且已选择测试对象，提示可以开始分析
  if (previousCount === 0 && rules.length > 0) {
    if (demoStore.testRecord && demoStore.selectedDocument) {
      setTimeout(() => {
        message.success(`✅ 已选择 ${rules.length} 条规则，条件已满足，可以点击"开始分析"`, 3)
      }, 300)
    } else {
      message.info(`已选择 ${rules.length} 条规则`, 2)
    }
  }
}

const handleAnalysisComplete = () => {
  message.success('质控分析完成')
}



// 快速开始 - 加载预置示例（支持可选重置）
const handleQuickStart = async (reset = false) => {
  try {
    if (reset) {
      // 清除保存状态并重置演示
      await demoStore.clearSavedState()
      await demoStore.resetDemoState()
    }

    const examples = demoStore.getPresetExamples()
    if (examples.length === 0) {
      message.warning('暂无预置示例')
      return
    }

    // 加载第一个预置示例（使用 key 而不是 id）
    demoStore.loadPresetExample(examples[0].key)
    message.success(`✅ 已加载预置示例：${examples[0].title}`, 3)

    // 自动跳转到下一步（规则配置）
    setTimeout(() => {
      if (demoStore.currentStep === 'target') {
        demoStore.currentStep = 'rules'
        message.info('📋 已自动进入"规则配置"步骤，请选择质控规则', 3)
      }
    }, 300)

  } catch (error) {
    console.error('快速开始失败:', error)
    message.error('加载预置示例失败，请重试')
  }
}

// 选择病历+文书回调（供 RecordDocumentPicker 使用）
const onTargetPicked = async ({ record, document, documents }: any) => {
  try {
    // 设置选择的记录和文档
    if (record) {
      demoStore.testRecord = record
    }

    if (documents && documents.length > 0) {
      demoStore.setSelectedDocument(documents)
    } else if (document) {
      demoStore.setSelectedDocument([document])
    }

    const count = documents?.length || (document ? 1 : 0)
    const docLabel = count > 1 ? `已选${count}份文书` : (document?.title || '文书')
    const patientName = record?.patient_name || '病历'
    message.success(`✅ 已选择：${patientName} · ${docLabel}`)

    // 自动跳转到下一步（规则配置）
    if (demoStore.currentStep === 'target') {
      demoStore.currentStep = 'rules'
      message.info('📋 已自动进入"规则配置"步骤，请选择质控规则', 3)
    }

    // 如果已经选择了规则，提示可以开始分析
    if (demoStore.selectedRules.length > 0) {
      setTimeout(() => {
        message.success('✨ 条件已满足，可以点击"开始分析"按钮', 3)
      }, 500)
    }

  } catch (error) {
    console.error('选择测试对象失败:', error)
    message.error('选择测试对象失败，请重试')
  }
}


// 性能监控导出处理
const handlePerformanceExport = () => {
  console.log('性能数据已导出')
}

const handleNotificationModalAction = (action: string, notification?: unknown) => {
  console.log('通知模态框操作:', action, notification)

  switch (action) {
    case 'confirm':
      demoStore.handleNotificationAction('confirm', notification || demoStore.activeNotification)
      demoStore.showNotificationModal = false
      message.success('通知已确认处理')
      break
    case 'ignore':
      demoStore.handleNotificationAction('ignore', notification || demoStore.activeNotification)
      demoStore.showNotificationModal = false


      message.info('通知已忽略')
      break
    case 'appeal':
      demoStore.handleNotificationAction('appeal', notification || demoStore.activeNotification)
      demoStore.showNotificationModal = false
      message.info('申诉流程已启动')
      break
    case 'share':
      message.info('分享功能开发中')
      break
    case 'print':
      message.info('打印功能开发中')
      break
    case 'history':
      message.info('历史记录功能开发中')
      break
    case 'mark-read':
      demoStore.handleNotificationAction('mark-read', notification || demoStore.activeNotification)
      message.success('已标记为已读')
      break
    default:
      demoStore.showNotificationModal = false
      break
  }
}



// 停止演示确认
const handleStopDemo = () => {
  Modal.confirm({
    title: '确认停止演示',
    content: '停止后将清除当前演示进度，是否继续？',
    okText: '确认停止',
    cancelText: '取消',
    okType: 'danger',
    onOk() {
      demoStore.stopDemo()
      message.success('演示已停止')
    }
  })
}

const handleAppealSubmitted = (appeal: Appeal) => {
  console.log('申诉已提交:', appeal)
  demoStore.createAppeal(appeal)
  demoStore.showAppealModal = false
  message.success('申诉已提交，等待审核')
}





// 处理重播演示
const handleReplayDemo = async () => {
  try {
    await demoStore.replayDemo()
    message.success('演示已重置，可以重新开始')
  } catch (error) {
    message.error('重置演示失败')
    console.error('重置演示失败:', error)
  }
}

// 处理步骤跳转
const handleStepJump = async (step: string) => {
  try {
    await demoStore.jumpToStep(step as any)
    message.success(`已跳转到: ${getStepLabel(step)}`)
  } catch (error) {
    message.error('跳转失败')
    console.error('步骤跳转失败:', error)
  }
}

// 获取步骤标签
const getStepLabel = (step: string) => {
  const labels: Record<string, string> = {
    target: '测试对象',
    rules: '规则配置',
    run: '运行与结果'
  }
  return labels[step] || step
}

// 处理菜单操作
const handleMenuAction = async ({ key }: { key: string }) => {
  switch (key) {
    case 'export':
      try {
        demoStore.exportDemoData()
        message.success('演示数据已导出')
      } catch (error) {
        message.error('导出失败')
        console.error('导出失败:', error)
      }
      break

    case 'import':
      fileInputRef.value?.click()
      break

    case 'clear':
      try {
        demoStore.clearSavedState()
        message.success('已清除保存的演示状态')
      } catch (error) {
        message.error('清除状态失败')
        console.error('清除状态失败:', error)
      }
      break

    case 'config':
      // 打开配置模态框（使用新的 DemoConfigModal 组件）
      showConfigModal.value = true
      break
  }
}

// 处理文件导入
const handleFileImport = async (event: Event) => {
  const file = (event.target as HTMLInputElement).files?.[0]
  if (file) {
    try {
      await demoStore.importDemoData(file)
      message.success('演示数据导入成功')
    } catch (error) {
      message.error('导入失败: ' + (error as Error).message)
      console.error('导入失败:', error)
    }
  }
  // 清空文件输入
  if (fileInputRef.value) {
    fileInputRef.value.value = ''
  }
}

// 保存配置
const handleConfigSave = async () => {
  try {
    await demoStore.initializeDemo({
      autoAdvance: configForm.value.autoAdvance,
      stepDelay: configForm.value.stepDelay * 1000 // 转换为毫秒
    }, false) // 不恢复状态，只更新配置

    message.success('配置已保存')
    showConfigModal.value = false
  } catch (error) {
    message.error('保存配置失败')
    console.error('保存配置失败:', error)
  }
}

// 生命周期
onMounted(async () => {
  // 检查 URL 参数
  const urlParams = new URLSearchParams(window.location.search)
  const forceClear = urlParams.get('clear') === 'true'

  // 首次访问体验：自动清除旧状态并给出引导提示（一次性）
  const FIRST_VISIT_KEY = 'llm_qc_demo_layout_v2_seen'
  const isFirstVisit = !localStorage.getItem(FIRST_VISIT_KEY)

  if (isFirstVisit || forceClear) {
    // 清理旧状态
    await demoStore.clearSavedState()
    await demoStore.resetDemoState()

    // 标记已访问（除非是强制清除）
    if (!forceClear) {
      localStorage.setItem(FIRST_VISIT_KEY, '1')
    }

    // 回到步骤1，确保看到快速开始入口
    demoStore.currentStep = 'target'

    // 显示引导提示
    message.info('欢迎使用：点击“快速开始”加载预置示例，或“手动选择”自定义测试对象', 5)
  } else {
    // 非首次访问：检查状态是否过期（超过24小时）
    const savedState = localStorage.getItem('qc-demo-state')
    if (savedState) {
      try {
        const state = JSON.parse(savedState)
        const savedTime = new Date(state.timestamp).getTime()
        const now = Date.now()
        const hoursPassed = (now - savedTime) / (1000 * 60 * 60)

        if (hoursPassed > 24) {
          localStorage.removeItem('qc-demo-state')
          console.log('[LLM质控演示] 状态已过期（超过24小时），已清除')
        } else {
          console.log(`[LLM质控演示] 恢复保存的状态（${hoursPassed.toFixed(1)}小时前）`)
        }
      } catch (error) {
        console.error('[LLM质控演示] 解析保存状态失败，清除无效数据', error)
        localStorage.removeItem('qc-demo-state')
      }
    }
  }

  console.log('[LLM质控演示] 页面加载，开始自动初始化...')

  try {
    // 显示友好的加载提示
    message.loading('正在自动连接数据库并初始化演示环境...', 0)

    // 自动初始化演示环境（包括数据库连接）
    await demoStore.initializeDemo({}, false)

    // 关闭加载提示
    message.destroy()

    // 根据连接状态显示不同的提示
    if (demoStore.isDatabaseConnected) {
      message.success('✅ 已自动连接到数据库，演示环境初始化完成！', 3)
      console.log('[LLM质控演示] 数据库连接成功 - 可用记录:', demoStore.availableRecords.length)
      console.log('[LLM质控演示] 数据库连接成功 - 可用规则:', demoStore.availableRules.length)
    } else {
      message.warning('⚠️ 数据库连接失败，已自动切换到本地模拟数据', 4)
      console.log('[LLM质控演示] 使用模拟数据 - 可用记录:', demoStore.availableRecords.length)
      console.log('[LLM质控演示] 使用模拟数据 - 可用规则:', demoStore.availableRules.length)
    }

    console.log('[LLM质控演示] 初始化完成 - 当前测试记录:', demoStore.testRecord?.id)

  } catch (error) {
    message.destroy()
    console.error('[LLM质控演示] 自动初始化失败:', error)

    // 显示友好的错误提示
    const errorMessage = error instanceof Error ? error.message : '未知错误'
    message.error(`❌ 演示环境初始化失败: ${errorMessage}`, 5)

    // 设置错误状态，让用户知道发生了什么
    demoStore.error = `自动初始化失败: ${errorMessage}`
  }

  // 延迟添加示例通知，确保初始化完成后再添加
  setTimeout(() => {
    if (demoStore.availableRecords.length > 0) {
      demoStore.simulateRandomNotification()
    }
  }, 2000)

  setTimeout(() => {
    if (demoStore.availableRecords.length > 0) {
      demoStore.simulateRandomNotification()
    }
  }, 4000)

  // 添加示例申诉
  setTimeout(() => {
    if (demoStore.notifications.length > 0) {
      const sampleAppeal = {
        id: 'appeal-demo-001',
        appealType: 'quality_dispute',
        reason: 'rule_misapplication',
        description: '该质控规则在此病历场景下应用不当，患者的特殊情况未被考虑在内。',
        priority: 'high',
        contact: 'doctor@example.com',
        attachments: [],
        submittedBy: '张医生',
        submittedAt: new Date(Date.now() - 2 * 24 * 60 * 60 * 1000), // 2天前
        status: 'reviewing'
      }
      ;(sampleAppeal as any).notificationId = demoStore.notifications[0].id
      demoStore.createAppeal(sampleAppeal)
    }
  }, 6000)
})
</script>

<style scoped lang="less">
/* TEMPORARILY DISABLE STYLES TO FIX LESS COMPILE ERROR

.llm-qc-demo-enhanced {
  padding: 24px;
  background: #f5f5f5;
  min-height: 100vh;

  .demo-header {
    background: white;
    border-radius: 8px;
    padding: 24px;
    margin-bottom: 24px;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  }

  // 顶部状态栏样式
  .status-bar {
    margin-bottom: 16px;

    .ant-alert {
      border-radius: 6px;
    }
  }

  // 错误提示样式
  .error-alert {
    margin-bottom: 16px;
  }

    .header-content {
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      margin-bottom: 24px;

      .title-section {
        .demo-title {
          font-size: 28px;
          font-weight: 600;
          color: #1890ff;
          margin: 0 0 8px 0;
          display: flex;
          align-items: center;
          gap: 12px;

          .title-icon {
            font-size: 32px;
          }
        }

        .demo-description {
          font-size: 16px;
          color: #666;
          margin: 0;
        }
      }

      .demo-controls {
        flex-shrink: 0;
      }
    }

    .progress-section {
      .progress-steps {
        display: flex;
        justify-content: space-between;
        margin-top: 16px;

        .step-item {
          display: flex;
          flex-direction: column;
          align-items: center;
          opacity: 0.5;
          transition: all 0.3s;

          &.active {
            opacity: 1;
            color: #1890ff;
          }

          &.completed {
            opacity: 1;
            color: #52c41a;
          }

          .step-icon {
            font-size: 20px;
            margin-bottom: 8px;
          }

          .step-label {
            font-size: 12px;
            text-align: center;
          }
        }
      }
    }
  }

  .error-alert {
    margin-bottom: 24px;
  }

  .demo-content {
    .demo-display {
      background: white;
      border-radius: 8px;
      padding: 32px;
      box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
      min-height: 700px;
      position: relative;
      width: 100%;
      max-width: none;

      .step-indicator {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 24px;
        padding-bottom: 16px;
        border-bottom: 1px solid #f0f0f0;

        .step-navigation {
          display: flex;
          gap: 8px;
        }
      }

      .readiness-alert {
        margin-bottom: 16px;
      }

      .paused-overlay {
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background: rgba(0, 0, 0, 0.3);
        display: flex;
        align-items: center;
        justify-content: center;
        z-index: 10;
        border-radius: 8px;

        span {
          background: rgba(0, 0, 0, 0.8);
          color: white;
          padding: 12px 24px;
          border-radius: 6px;
          font-size: 16px;
          font-weight: 500;
        }
      }

      .content-area {
        .step-content {
          min-height: 500px;
        }

        .completion-summary {
          display: flex;
          justify-content: center;
          align-items: center;
          height: 500px;
        }
      }
    }
*/

/* Minimal active styles during refactor */
.status-bar {
  margin-top: 16px;   /* 增加与上方按钮区的间距 */
  margin-bottom: 16px;
}


/* Tighten header typography and spacing */
.llm-qc-demo-enhanced .demo-header {
  padding: 12px 16px;
  margin-bottom: 12px;
}
.llm-qc-demo-enhanced .header-content {
  margin-bottom: 8px;
}
.llm-qc-demo-enhanced .title-section .demo-title {
  font-size: 22px;
  line-height: 1.2;
  margin: 0 0 4px 0;
}
.llm-qc-demo-enhanced .title-section .demo-description {
  font-size: 13px;
  line-height: 1.35;
  color: #666;
  margin: 0;
}

/* Compress progress section spacing */
.llm-qc-demo-enhanced .progress-section {
  margin: 8px 0;
}
.llm-qc-demo-enhanced .progress-section .progress-steps {
  margin-top: 8px;
}

</style>
