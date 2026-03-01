<template>
  <div class="ws-v2">
    <!-- 侧边栏 -->
    <aside :class="['ws-v2-sidebar', { collapsed: sidebarCollapsed }]">
      <div class="sidebar-header">
        <div v-if="!sidebarCollapsed" class="sidebar-title">
          <ThunderboltOutlined style="color: #1677ff" />
          <span>AI 质控工作站</span>
        </div>
        <a-button type="text" size="small" @click="sidebarCollapsed = !sidebarCollapsed">
          <MenuFoldOutlined v-if="!sidebarCollapsed" />
          <MenuUnfoldOutlined v-else />
        </a-button>
      </div>

      <a-menu
        v-model:selectedKeys="menuSelectedKeys"
        mode="inline"
        :inline-collapsed="sidebarCollapsed"
        @click="onMenuClick"
      >
        <a-menu-item key="workbench">
          <template #icon><DesktopOutlined /></template>
          <span>工作台</span>
        </a-menu-item>

        <a-menu-divider />

        <a-sub-menu key="drg-sub">
          <template #icon><ClusterOutlined /></template>
          <template #title>DRG/DIP</template>
          <a-menu-item key="pre-analysis">
            <template #icon><FileSearchOutlined /></template>
            事前分析
          </a-menu-item>
          <a-menu-item key="mid-analysis">
            <template #icon><DashboardOutlined /></template>
            事中监控
          </a-menu-item>
          <a-menu-item key="payment">
            <template #icon><DollarOutlined /></template>
            付费监测
          </a-menu-item>
          <a-menu-item key="post-analysis">
            <template #icon><BarChartOutlined /></template>
            事后分析
          </a-menu-item>
        </a-sub-menu>

        <a-menu-divider />

        <a-menu-item key="upload">
          <template #icon><CloudUploadOutlined /></template>
          <span>数据上传</span>
        </a-menu-item>
        <a-menu-item key="messages">
          <template #icon><BellOutlined /></template>
          <span>质控消息</span>
        </a-menu-item>
      </a-menu>
    </aside>

    <!-- 主内容区 -->
    <main class="ws-v2-main">
      <!-- 工作台视图 -->
      <div v-if="currentView === 'workbench'" class="workbench-layout">
        <!-- 上方双栏区 -->
        <div class="workbench-panels" ref="panelsRef">
          <!-- 左栏：病历原文 -->
          <div class="panel-left" :style="{ width: leftPanelWidth + '%' }">
            <div class="panel-header">
              <span class="panel-title">
                <FileTextOutlined /> 病历原文
              </span>
              <a-space>
                <a-button v-if="demoCase" size="small" type="primary" :loading="extracting" @click="extractStructuredData">
                  <ThunderboltOutlined /> AI 提取
                </a-button>
              </a-space>
            </div>
            <div class="panel-body custom-scrollbar">
              <MedicalRecordPanel
                :medical-text="demoCase?.medical_text || ''"
                :loading="loading"
              />
            </div>
          </div>

          <!-- 可拖拽分隔线 -->
          <div class="resize-handle" @mousedown="startResize"></div>

          <!-- 右栏：分析面板 -->
          <div class="panel-right" :style="{ width: (100 - leftPanelWidth) + '%' }">
            <div class="panel-header">
              <a-segmented v-model:value="activeTab" :options="analysisTabs" size="small" />
            </div>
            <div class="panel-body custom-scrollbar">
              <!-- Tab1: 首页结果 (M1) -->
              <StructuredDataView
                v-if="activeTab === 'frontpage'"
                :extracting="extracting"
                :frontpage="frontpage"
                :has-medical-text="!!demoCase?.medical_text"
                @extract="extractStructuredData"
              />

              <!-- Tab2: 质控结果 (M2 + M3-A) -->
              <div v-else-if="activeTab === 'qc'" class="tab-placeholder">
                <SafetyCertificateOutlined style="font-size: 48px; color: #1677ff" />
                <h3>首页质控</h3>
                <p>形式质控（M2）+ 内涵质控（M3-A）</p>
                <p class="hint">Phase 2 开发：≥160 条质控规则引擎</p>
              </div>

              <!-- Tab3: DRG 分组 (M6) -->
              <DRGGroupingTab
                v-else-if="activeTab === 'drg'"
                :drg-result="drgResult"
                :loading="drgGrouping"
                :has-frontpage="!!frontpage"
                :main-diagnosis-code="frontpage?.primary_diagnosis_code || frontpage?.diagnoses?.discharge_main_icd || ''"
                :main-diagnosis-text="frontpage?.primary_diagnosis_name || frontpage?.diagnoses?.discharge_main_diagnosis_text || ''"
                :main-procedure-code="frontpage?.main_procedure_code || frontpage?.procedures?.main?.code || ''"
                :main-procedure-name="frontpage?.main_procedure_name || frontpage?.procedures?.main?.name || ''"
                @group="performDRGGrouping"
                @open-optimization="openOptimization"
              />

              <!-- Tab4: AI 画像 (M3-B) -->
              <AIProfileDashboard
                v-else-if="activeTab === 'profile'"
                :frontpage="frontpage"
              />

              <!-- Tab5: ICD 查询 (M4) -->
              <div v-else-if="activeTab === 'icd'" class="tab-placeholder">
                <SearchOutlined style="font-size: 48px; color: #1677ff" />
                <h3>ICD 编码查询</h3>
                <p>ICD-10 疾病编码 + ICD-9-CM-3 手术编码</p>
                <p class="hint">Phase 2 开发：对接 /api/v1/icd/search</p>
              </div>
            </div>
          </div>
        </div>

        <!-- 底部：测试用例列表 -->
        <div class="workbench-footer">
          <div class="footer-header">
            <span class="panel-title">
              <ProfileOutlined /> 测试用例
            </span>
            <a-space>
              <a-tag color="blue">{{ testCases.length }} 份</a-tag>
            </a-space>
          </div>
          <div class="test-case-bar">
            <a-button
              v-for="(tc, idx) in testCases"
              :key="idx"
              :type="currentCaseIndex === idx ? 'primary' : 'default'"
              size="small"
              @click="loadDemoCase(idx)"
              :loading="loading && currentCaseIndex === idx"
            >
              {{ tc.name }}
            </a-button>
          </div>
        </div>
      </div>

      <!-- DRG 事前分析 -->
      <PreAnalysisView
        v-else-if="currentView === 'pre-analysis'"
        :session-id="selectedSessionId"
        :batch-id="selectedBatchId"
      />

      <!-- DRG 事中监控 -->
      <InProcessMonitoringView
        v-else-if="currentView === 'mid-analysis'"
      />

      <!-- 付费监测 -->
      <PaymentMonitoringView
        v-else-if="currentView === 'payment'"
      />

      <!-- DRG 事后分析 -->
      <PostEventAnalysisView
        v-else-if="currentView === 'post-analysis'"
      />

      <!-- 数据上传 -->
      <ExcelUploadView
        v-else-if="currentView === 'upload'"
        @go-analysis="handleGoAnalysis"
      />

      <!-- 质控消息 -->
      <div v-else-if="currentView === 'messages'" class="tab-placeholder" style="height: 100%; display: flex; align-items: center; justify-content: center; flex-direction: column;">
        <BellOutlined style="font-size: 48px; color: #1677ff" />
        <h3>质控消息概览</h3>
        <p>M5：每日问题汇总 + 科室分布</p>
      </div>
    </main>

    <!-- 编码优化建议抽屉 -->
    <CodingOptimizationDrawer
      :visible="suggestionDrawerVisible"
      :loading="suggestionsLoading"
      :suggestions="suggestions"
      :get-suggestion-title="getSuggestionTitle"
      @update:visible="suggestionDrawerVisible = $event"
      @handle="handleSuggestion"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { message } from 'ant-design-vue'
import {
  ThunderboltOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
  DesktopOutlined,
  ClusterOutlined,
  FileSearchOutlined,
  DashboardOutlined,
  DollarOutlined,
  BarChartOutlined,
  CloudUploadOutlined,
  BellOutlined,
  FileTextOutlined,
  SafetyCertificateOutlined,
  SearchOutlined,
  ProfileOutlined,
} from '@ant-design/icons-vue'
// 复用 demo 组件（保持 Tailwind 内部样式）
import {
  AIProfileDashboard,
  InsuranceClaimView,
  MedicalRecordPanel,
  StructuredDataView,
  DRGGroupingTab,
  CodingOptimizationDrawer,
  InProcessMonitoringView,
  PaymentMonitoringView,
  PostEventAnalysisView,
  ExcelUploadView,
  PreAnalysisView,
} from '@/views/demo/frontpage/components'
// 复用 composables
import { useMedicalTextExtraction, useDRGGrouping } from '@/views/demo/frontpage/composables'

// ==================== 布局状态 ====================
const sidebarCollapsed = ref(false)
const menuSelectedKeys = ref(['workbench'])
const currentView = ref('workbench')
const activeTab = ref('frontpage')

const analysisTabs = [
  { label: '首页', value: 'frontpage' },
  { label: '质控', value: 'qc' },
  { label: 'DRG', value: 'drg' },
  { label: '画像', value: 'profile' },
  { label: 'ICD', value: 'icd' },
]

// ==================== 业务状态 ====================
interface DemoCase {
  case_id: string
  description?: string
  medical_text?: string
  frontpage?: any
  insurance_claim?: any
}

const loading = ref(false)
const demoCase = ref<DemoCase | null>(null)
const currentCaseIndex = ref(-1)
const selectedBatchId = ref<string | null>(null)
const selectedSessionId = ref<string | null>(null)

// ===== Composables =====
const { extracting, extractStructuredData } = useMedicalTextExtraction({
  demoCase,
  onStartExtract: () => {
    console.log('[workstation-v2] AI 提取开始')
  },
  onExtracted: () => {
    console.log('[workstation-v2] AI 提取完成')
  },
})

const {
  drgLoading: drgGrouping,
  drgResult,
  suggestionDrawerVisible,
  suggestionsLoading,
  suggestions,
  performDRGGrouping: doDRGGrouping,
  openOptimizationDrawer,
  handleSuggestion,
  getSuggestionTitle,
} = useDRGGrouping()

// 计算属性
const frontpage = computed(() => demoCase.value?.frontpage || null)

// ==================== 测试用例 ====================
const testCases = ref([
  {
    name: '测试病历1',
    description: '冠心病支架植入术完整住院病历',
    medical_text: '', // 将在 onMounted 中从 API 或内置数据加载
  },
  {
    name: '测试病历2',
    description: '肛瘘手术完整住院病历',
    medical_text: '',
  },
])

// 加载测试用例（复用 FrontPageDemoView 的数据加载逻辑）
async function loadDemoCase(idx: number) {
  if (idx < 0 || idx >= testCases.value.length) return
  loading.value = true
  currentCaseIndex.value = idx
  try {
    const tc = testCases.value[idx]
    // 如果测试用例还没有文本，尝试从后端加载
    if (!tc.medical_text) {
      try {
        const resp = await fetch('/api/v1/test-cases')
        const json = await resp.json()
        if (json.data?.length > 0) {
          json.data.forEach((item: any, i: number) => {
            if (i < testCases.value.length) {
              testCases.value[i].medical_text = item.medical_text || ''
              testCases.value[i].name = item.name || testCases.value[i].name
            }
          })
        }
      } catch {
        // 后端未运行，使用提示
        message.info('后端未运行，请在左侧粘贴病历原文或通过数据上传导入')
      }
    }

    await new Promise(resolve => setTimeout(resolve, 300))
    demoCase.value = {
      case_id: `case_${idx + 1}`,
      description: tc.description,
      medical_text: tc.medical_text,
      frontpage: null,
      insurance_claim: null,
    }
    if (tc.medical_text) {
      message.success(`${tc.name} 加载成功`)
    }
  } finally {
    loading.value = false
  }
}

// ==================== DRG 分组 ====================
function performDRGGrouping() {
  if (demoCase.value?.case_id) {
    doDRGGrouping(demoCase.value.case_id, frontpage.value?.costs?.total_cost)
  }
}

function openOptimization() {
  if (demoCase.value?.case_id) {
    openOptimizationDrawer(demoCase.value.case_id)
  }
}

// ==================== 导航 ====================
function onMenuClick({ key }: { key: string }) {
  currentView.value = key
  menuSelectedKeys.value = [key]
}

function handleGoAnalysis(sessionId: string, batchId: string) {
  selectedSessionId.value = sessionId
  selectedBatchId.value = batchId
  currentView.value = 'pre-analysis'
  menuSelectedKeys.value = ['pre-analysis']
}

// ==================== 拖拽分隔线 ====================
const leftPanelWidth = ref(50)
const isResizing = ref(false)
const panelsRef = ref<HTMLElement | null>(null)

function startResize(e: MouseEvent) {
  isResizing.value = true
  document.body.style.cursor = 'col-resize'
  document.body.style.userSelect = 'none'
  e.preventDefault()
}

function doResize(e: MouseEvent) {
  if (!isResizing.value || !panelsRef.value) return
  const rect = panelsRef.value.getBoundingClientRect()
  const pct = ((e.clientX - rect.left) / rect.width) * 100
  leftPanelWidth.value = Math.min(75, Math.max(25, pct))
}

function stopResize() {
  isResizing.value = false
  document.body.style.cursor = ''
  document.body.style.userSelect = ''
}

onMounted(() => {
  document.addEventListener('mousemove', doResize)
  document.addEventListener('mouseup', stopResize)
})

onUnmounted(() => {
  document.removeEventListener('mousemove', doResize)
  document.removeEventListener('mouseup', stopResize)
})
</script>

<style scoped>
/* ==================== 整体布局 ==================== */
.ws-v2 {
  display: flex;
  height: 100vh;
  background: #f5f7fa;
  overflow: hidden;
}

/* ==================== 侧边栏 ==================== */
.ws-v2-sidebar {
  width: 220px;
  background: #fff;
  border-right: 1px solid #e8e8e8;
  display: flex;
  flex-direction: column;
  transition: width 0.2s ease;
  flex-shrink: 0;
}
.ws-v2-sidebar.collapsed {
  width: 64px;
}
.sidebar-header {
  height: 56px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 12px;
  border-bottom: 1px solid #f0f0f0;
}
.sidebar-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 600;
  font-size: 15px;
  color: #1a1a1a;
  white-space: nowrap;
}

/* ==================== 主内容区 ==================== */
.ws-v2-main {
  flex: 1;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

/* ==================== 工作台布局 ==================== */
.workbench-layout {
  display: flex;
  flex-direction: column;
  height: 100%;
}
.workbench-panels {
  flex: 1;
  display: flex;
  overflow: hidden;
  min-height: 0;
}

/* 面板通用 */
.panel-left, .panel-right {
  display: flex;
  flex-direction: column;
  overflow: hidden;
  min-width: 0;
}
.panel-header {
  height: 48px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 16px;
  background: #fff;
  border-bottom: 1px solid #f0f0f0;
  flex-shrink: 0;
}
.panel-title {
  font-weight: 600;
  font-size: 14px;
  color: #333;
  display: flex;
  align-items: center;
  gap: 6px;
}
.panel-body {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
  background: #fafafa;
}

/* 分隔线 */
.resize-handle {
  width: 6px;
  cursor: col-resize;
  background: #e8e8e8;
  transition: background 0.15s;
  flex-shrink: 0;
}
.resize-handle:hover {
  background: #1677ff;
}

/* ==================== 底部测试用例栏 ==================== */
.workbench-footer {
  border-top: 1px solid #e8e8e8;
  background: #fff;
  flex-shrink: 0;
}
.footer-header {
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 16px;
  border-bottom: 1px solid #f0f0f0;
}
.test-case-bar {
  display: flex;
  gap: 8px;
  padding: 8px 16px;
  overflow-x: auto;
}

/* ==================== 占位区 ==================== */
.tab-placeholder {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60px 20px;
  text-align: center;
}
.tab-placeholder h3 {
  margin: 16px 0 8px;
  font-size: 18px;
  color: #333;
}
.tab-placeholder p {
  color: #999;
  font-size: 14px;
  margin: 0;
}
.tab-placeholder .hint {
  margin-top: 8px;
  color: #bbb;
  font-size: 12px;
}

/* ==================== 滚动条 ==================== */
.custom-scrollbar::-webkit-scrollbar {
  width: 6px;
  height: 6px;
}
.custom-scrollbar::-webkit-scrollbar-track {
  background: transparent;
}
.custom-scrollbar::-webkit-scrollbar-thumb {
  background: #d9d9d9;
  border-radius: 3px;
}
.custom-scrollbar::-webkit-scrollbar-thumb:hover {
  background: #bfbfbf;
}
</style>
