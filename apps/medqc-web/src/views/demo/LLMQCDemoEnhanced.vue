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

        <!-- 演示控制面板 -->
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
          :percent="demoStore.demoProgress"
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

    <!-- 顶部状态栏 -->
    <div class="status-bar">
      <!-- 数据库连接状态 -->
      <a-alert
        v-if="demoStore.isLoadingData"
        message="正在自动连接数据库..."
        type="info"
        show-icon
        banner
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
        banner
      >
        <template #action>
          <a-button size="small" @click="handleRefreshData" :loading="demoStore.isLoadingData">
            重试连接
          </a-button>
        </template>
      </a-alert>
      <a-alert
        v-else
        message="已自动连接到数据库，使用真实数据"
        type="success"
        show-icon
        banner
      >
        <template #action>
          <a-button size="small" @click="handleRefreshData" :loading="demoStore.isLoadingData">
            刷新数据
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

        <!-- 条件引导提示 -->
        <div class="readiness-alert">
          <a-alert
            :type="readinessAlert.type"
            :message="readinessAlert.message"
            show-icon
            banner
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
            <a-result
              :status="demoStore.testRecord && (demoStore.selectedDocumentList?.length||0) > 0 ? 'success' : 'info'"
              :title="demoStore.testRecord && (demoStore.selectedDocumentList?.length||0) > 0 ? '已选择测试对象' : '请选择测试对象（病历 + 文书）'"
            >
              <template #subTitle>
                <div v-if="demoStore.testRecord && (demoStore.selectedDocumentList?.length||0) > 0">
                  {{ demoStore.testRecord.patient_name }} · {{ demoStore.selectedDocumentList.length>1 ? `已选${demoStore.selectedDocumentList.length}份文书` : (demoStore.selectedDocumentList[0]?.title || '文书') }}
                </div>
                <div v-else>点击下方按钮打开选择器</div>
              </template>
              <template #extra>
                <a-space>
                  <a-button type="primary" @click="showTargetPicker = true">选择病历与文书</a-button>
                  <a-button v-if="demoStore.testRecord && (demoStore.selectedDocumentList?.length||0) > 0" @click="demoStore.currentStep = 'rules' as any">前往规则配置</a-button>
                </a-space>
              </template>
            </a-result>
          </div>

          <!-- 规则配置 -->
          <div v-else-if="demoStore.currentStep === 'rules'" class="step-content">
            <QCRulesDemoPanel
              :selected-rules="demoStore.selectedRules"
              :available-rules="demoStore.availableRules"
              :test-record="demoStore.testRecord"
              :selected-documents="demoStore.selectedDocumentList"
              @rules-updated="handleRulesUpdated"
            />
          </div>

          <!-- 运行与结果（合并原分析/完成等） -->
          <div v-else class="step-content">
            <QCAnalysisDemoPanel
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
  LoadingOutlined
} from '@ant-design/icons-vue'

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

// 配置表单数据
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
const onTargetPicked = ({ record, document }: { record: any; document: { id: string; title?: string; type?: string; created_at?: string } }) => {
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
  demoStore.selectedRules = rules
}

const handleAnalysisComplete = () => {
  message.success('质控分析完成')
}



// 选择病历+文书回调（供 RecordDocumentPicker 使用）
const onTargetPicked = async ({ record, document, documents }: { record: any; document: { id: string; title?: string; type?: string; created_at?: string } | null; documents: Array<{ id: string; title?: string; type?: string; created_at?: string }> }) => {
  try {
    // 设置选择的记录和文档
    demoStore.testRecord = record as any
    demoStore.setSelectedDocument(documents && documents.length > 0 ? documents : (document ? [document] : []))

    const count = documents?.length || (document ? 1 : 0)
    const docLabel = count > 1 ? `已选${count}份文书` : (document?.title || '文书')
    message.success(`已选择：${record.patient_name} · ${docLabel}`)

    // 自动启动质控演示
    console.log('🚀 自动启动质控演示...')
    await demoStore.startDemo()
    message.success('质控演示已开始！', 2)

  } catch (error) {
    console.error('启动质控演示失败:', error)
    message.error('启动质控演示失败，请重试')
  }
}


const handleNotificationModalAction = (action: string, notification?: any) => {
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
      // 加载当前配置
      configForm.value = {
        autoAdvance: demoStore.demoConfig.autoAdvance,
        stepDelay: demoStore.demoConfig.stepDelay / 1000, // 转换为秒
        showDetailedLogs: true,
        enableSimulationDelay: true
      }
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
  // 清除旧的本地存储状态（临时调试）
  localStorage.removeItem('qc-demo-state')

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


</style>
