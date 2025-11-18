<template>
  <a-layout class="llm-qc-demo-layout">
    <!-- 顶部导航栏 -->
    <a-layout-header class="demo-header">
      <div class="header-content">
        <div class="header-left">
          <h1 class="page-title">
            <ExperimentOutlined />
            LLM 质控演示系统
          </h1>
          <a-breadcrumb>
            <a-breadcrumb-item>
              <HomeOutlined />
              <span>首页</span>
            </a-breadcrumb-item>
            <a-breadcrumb-item>演示中心</a-breadcrumb-item>
            <a-breadcrumb-item>LLM 质控演示</a-breadcrumb-item>
          </a-breadcrumb>
        </div>
        <div class="header-right">
          <a-space :size="16">
            <a-badge :count="demoStore.unreadNotificationsCount">
              <BellOutlined style="font-size: 18px; cursor: pointer" />
            </a-badge>
            <a-avatar>U</a-avatar>
          </a-space>
        </div>
      </div>
    </a-layout-header>

    <!-- 主内容区 -->
    <a-layout-content class="demo-content">
      <!-- 固定控制栏 -->
      <DemoControlPanel />

      <!-- 主工作区 + 侧边栏 -->
      <a-row :gutter="20" class="main-area">
        <!-- 左侧主工作区 (70%) -->
        <a-col :xs="24" :lg="17">
          <div class="work-area">
            <!-- 步骤指示器 -->
            <a-steps
              :current="currentStepIndex"
              :items="stepItems"
              class="step-indicator"
            />

            <!-- 步骤内容 -->
            <a-card :bordered="false" class="step-content-card">
              <!-- 测试对象选择步骤 - P1 组件 -->
              <TargetSelectionStep v-if="demoStore.currentStep === 'target'" />

              <!-- 规则配置步骤 -->
              <QCRulesDemoPanel
                v-else-if="demoStore.currentStep === 'rules'"
                :selected-rules="demoStore.selectedRules"
                :available-rules="demoStore.applicableRules"
                :test-record="demoStore.testRecord"
                :selected-documents="demoStore.selectedDocumentList"
                @rules-updated="(rules) => demoStore.selectedRules = rules"
                @start-analysis="demoStore.startDemo"
              />

              <!-- 运行与结果步骤 -->
              <QCAnalysisDemoPanel
                v-else-if="demoStore.currentStep === 'run'"
                :analysis-steps="analysisSteps"
                :analysis-result="analysisResult"
                :is-running="isAnalysisRunning"
              />
            </a-card>

            <div class="step-footer">
              <a-space :size="12">
                <a-button
                  size="large"
                  :icon="h(LeftOutlined)"
                  shape="round"
                  :disabled="currentStepIndex === 0 || demoStore.isRunning"
                  @click="handlePrevStep"
                >
                  上一步
                </a-button>
                <a-button
                  size="large"
                  type="primary"
                  shape="round"
                  :icon="h(RightOutlined)"
                  :disabled="currentStepIndex === 2 || demoStore.isRunning"
                  @click="handleNextStep"
                >
                  下一步
                </a-button>
              </a-space>
            </div>
          </div>
        </a-col>

        <!-- 右侧边栏 (30%) -->
        <a-col :xs="24" :lg="7">
          <a-card :bordered="false" class="sidebar-card">
            <a-tabs v-model:active-key="sidebarTab" size="small" class="sidebar-tabs">
              <a-tab-pane key="notifications">
                <template #tab>
                  <a-badge :count="demoStore.unreadNotificationsCount" :offset="[10, 0]">
                    <BellOutlined />
                    通知管理
                  </a-badge>
                </template>
                <NotificationManager />
              </a-tab-pane>

              <a-tab-pane key="appeals">
                <template #tab>
                  <a-badge :count="demoStore.pendingAppealsCount" :offset="[10, 0]">
                    <FileTextOutlined />
                    申诉管理
                  </a-badge>
                </template>
                <AppealManager />
              </a-tab-pane>
            </a-tabs>
          </a-card>
        </a-col>
      </a-row>

      <!-- 底部折叠面板 -->
      <BottomCollapsePanels />
    </a-layout-content>
  </a-layout>
</template>

<script setup lang="ts">
import { ref, computed, h, onMounted } from 'vue'
import { useQCDemoStore } from '@/stores/qcDemo'
import DemoControlPanel from '@/components/demo/DemoControlPanel.vue'
import NotificationManager from '@/components/demo/NotificationManager.vue'
import AppealManager from '@/components/demo/AppealManager.vue'
import BottomCollapsePanels from '@/components/demo/BottomCollapsePanels.vue'
// P1 步骤组件
import TargetSelectionStep from '@/components/demo/TargetSelectionStep.vue'
// 使用现有组件作为步骤内容
import QCRulesDemoPanel from '@/components/demo/QCRulesDemoPanel.vue'
import QCAnalysisDemoPanel from '@/components/demo/QCAnalysisDemoPanel.vue'
import {
  ExperimentOutlined,
  HomeOutlined,
  BellOutlined,
  FileTextOutlined,
  FileSearchOutlined,
  SettingOutlined,
  ThunderboltOutlined,
  LeftOutlined,
  RightOutlined
} from '@ant-design/icons-vue'

const demoStore = useQCDemoStore()

// 侧边栏标签页
const sidebarTab = ref('notifications')

// 步骤配置
const stepItems = [
  { title: '测试对象选择', icon: h(FileSearchOutlined) },
  { title: '规则配置', icon: h(SettingOutlined) },
  { title: '运行与结果', icon: h(ThunderboltOutlined) }
]

// 当前步骤索引
const currentStepIndex = computed(() => {
  const steps = ['target', 'rules', 'run']
  return steps.indexOf(demoStore.currentStep)
})

// 当前步骤组件
const currentStepComponent = computed(() => {
  const components = {
    target: TargetSelectionStep,  // P1: 测试对象选择
    rules: QCRulesDemoPanel,      // 规则配置面板
    run: QCAnalysisDemoPanel      // 分析面板
  }
  return components[demoStore.currentStep as keyof typeof components]
})

// 为 QCAnalysisDemoPanel 提供必需的 props
const analysisSteps = computed(() => demoStore.analysisSteps || [])
const analysisResult = computed(() => demoStore.analysisResult || null)
const isAnalysisRunning = computed(() => demoStore.isRunning)

const handlePrevStep = async () => {
  if (demoStore.isRunning || currentStepIndex.value === 0) return
  await demoStore.previousStep()
}

const handleNextStep = async () => {
  if (demoStore.isRunning || currentStepIndex.value === 2) return
  await demoStore.nextStep()
}

// 初始化
onMounted(async () => {
  await demoStore.loadTestData()
})
</script>

<style scoped lang="less">
.llm-qc-demo-layout {
  min-height: 100vh;
  background: var(--background-page);
}

.demo-header {
  background: var(--color-bg-card, #ffffff);
  border-bottom: 1px solid rgba(11, 100, 212, 0.08);
  padding: 0 32px;
  height: 72px;
  display: flex;
  align-items: center;
  box-shadow: 0 2px 12px rgba(15, 23, 42, 0.05);

  .header-content {
    display: flex;
    align-items: center;
    justify-content: space-between;
    width: 100%;
  }

  .header-left {
    display: flex;
    align-items: center;
    gap: 20px;
  }

  .page-title {
    margin: 0;
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 20px;
    font-weight: 600;
    color: var(--primary-color);

    :deep(.anticon) {
      font-size: 24px;
    }
  }
}

.demo-content {
  padding: 24px 32px 48px;
  max-width: 1280px;
  margin: 0 auto;
}

.main-area {
  margin-top: 20px;
}

.work-area {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.step-indicator {
  background: var(--color-bg-card, #ffffff);
  border-radius: 16px;
  padding: 24px;
  box-shadow: var(--shadow-light, 0 6px 18px rgba(14, 110, 209, 0.08));
  border: 1px solid rgba(11, 100, 212, 0.08);

  :deep(.ant-steps) {
    align-items: center;
  }

  :deep(.ant-steps-item-icon) {
    width: 36px;
    height: 36px;
  }

  :deep(.ant-steps-item-title) {
    font-weight: 600;
    color: var(--text-secondary);
  }

  :deep(.ant-steps-item-process .ant-steps-item-icon) {
    background: linear-gradient(135deg, rgba(30, 136, 255, 0.9), rgba(11, 100, 212, 0.9));
    border: none;
    box-shadow: 0 8px 16px rgba(11, 100, 212, 0.25);
  }

  :deep(.ant-steps-item-finish .ant-steps-item-icon) {
    border-color: rgba(11, 100, 212, 0.4);

    .ant-steps-icon {
      color: var(--primary-color);
    }
  }

  :deep(.ant-steps-item-process .ant-steps-item-icon .ant-steps-icon) {
    color: #ffffff;
  }

  :deep(.ant-steps-item-wait .ant-steps-item-icon) {
    background: rgba(11, 100, 212, 0.08);
    border: none;

    .ant-steps-icon {
      color: var(--primary-color);
    }
  }
}

.step-content-card {
  min-height: 520px;
  border-radius: 16px;
  border: 1px solid rgba(11, 100, 212, 0.08);
  box-shadow: var(--shadow-light, 0 6px 18px rgba(14, 110, 209, 0.08));

  :deep(> div) {
    animation: fadeInUp 0.35s ease-out;
  }
}

.step-footer {
  display: flex;
  justify-content: center;
  align-items: center;
  padding: 12px 0 4px;

  :deep(.ant-btn) {
    min-width: 120px;
    font-weight: 600;
  }

  :deep(.ant-btn-primary) {
    background: var(--primary-color);
    border-color: var(--primary-color);

    &:hover {
      background: var(--primary-color-dark);
      border-color: var(--primary-color-dark);
    }
  }
}

.sidebar-card {
  position: sticky;
  top: 100px;
  border-radius: 16px;
  border: 1px solid rgba(11, 100, 212, 0.08);
  box-shadow: var(--shadow-light, 0 6px 18px rgba(14, 110, 209, 0.08));
  max-height: calc(100vh - 140px);
  overflow: hidden;

  :deep(.ant-card-body) {
    padding: 0;
  }
}

.sidebar-tabs {
  :deep(.ant-tabs-nav) {
    margin: 0;
    padding: 16px 20px;
  }

  :deep(.ant-tabs-nav::before) {
    border: none;
  }

  :deep(.ant-tabs-tab) {
    border: none;
    background: transparent;
    border-radius: 20px;
    padding: 6px 16px;
    font-size: 14px;
    color: var(--text-secondary);
    transition: all 0.2s ease;
  }

  :deep(.ant-tabs-tab:hover) {
    background: rgba(11, 100, 212, 0.08);
    color: var(--primary-color);
  }

  :deep(.ant-tabs-tab-active) {
    background: var(--primary-color-subtle);
    color: var(--primary-color);
    box-shadow: inset 0 0 0 1px rgba(11, 100, 212, 0.25);
  }

  :deep(.ant-tabs-ink-bar) {
    display: none;
  }
}

:deep(.sidebar-card .ant-tabs-content) {
  padding: 0 20px 20px;
  max-height: calc(100vh - 210px);
  overflow-y: auto;
}

:deep(.sidebar-card .ant-tabs-content::-webkit-scrollbar) {
  width: 6px;
}

:deep(.sidebar-card .ant-tabs-content::-webkit-scrollbar-thumb) {
  background: rgba(11, 100, 212, 0.25);
  border-radius: 3px;
}

@keyframes fadeInUp {
  from {
    opacity: 0;
    transform: translateY(16px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@media (max-width: 1200px) {
  .demo-content {
    padding: 20px;
  }
}

@media (max-width: 992px) {
  .demo-header {
    padding: 0 20px;
    height: auto;
  }

  .demo-content {
    padding: 16px;
  }

  .sidebar-card {
    position: static;
    max-height: none;
    margin-top: 16px;
  }
}

@media (max-width: 768px) {
  .demo-header {
    .header-left {
      gap: 12px;
    }

    .page-title {
      font-size: 18px;
    }

    :deep(.ant-breadcrumb) {
      display: none;
    }
  }

  .demo-content {
    padding: 12px;
  }

  .control-panel-wrapper {
    padding: 8px;
  }

  .step-indicator {
    padding: 16px;
  }

  .step-content-card {
    min-height: 420px;
  }
}
</style>
