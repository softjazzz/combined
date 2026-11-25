<template>
  <div :class="['ws-v2', { 'ws-v2-embedded': embedded }]">
    <!-- 侧边栏（仅独立模式） -->
    <aside
      v-if="!embedded"
      :class="['ws-v2-sidebar', { collapsed: sidebarCollapsed }]"
    >
      <div class="sidebar-header">
        <div
          v-if="!sidebarCollapsed"
          class="sidebar-title"
        >
          <ThunderboltOutlined style="color: #0a6cff" />
          <span>AI 质控工作站</span>
        </div>
        <a-button
          type="text"
          size="small"
          @click="sidebarCollapsed = !sidebarCollapsed"
        >
          <MenuFoldOutlined v-if="!sidebarCollapsed" />
          <MenuUnfoldOutlined v-else />
        </a-button>
      </div>

      <a-menu
        v-model:selected-keys="menuSelectedKeys"
        mode="inline"
        :inline-collapsed="sidebarCollapsed"
        @click="onMenuClick"
      >
        <a-menu-item key="workbench">
          <template #icon>
            <DesktopOutlined />
          </template>
          <span>工作台</span>
        </a-menu-item>

        <a-menu-divider />

        <a-sub-menu key="drg-sub">
          <template #icon>
            <ClusterOutlined />
          </template>
          <template #title>
            DRG/DIP
          </template>
          <a-menu-item key="pre-analysis">
            <template #icon>
              <FileSearchOutlined />
            </template>
            事前分析
          </a-menu-item>
          <a-menu-item key="mid-analysis">
            <template #icon>
              <DashboardOutlined />
            </template>
            事中监控
          </a-menu-item>
          <a-menu-item key="payment">
            <template #icon>
              <DollarOutlined />
            </template>
            付费监测
          </a-menu-item>
          <a-menu-item key="post-analysis">
            <template #icon>
              <BarChartOutlined />
            </template>
            事后分析
          </a-menu-item>
        </a-sub-menu>

        <a-menu-item key="icd-search">
          <template #icon>
            <SearchOutlined />
          </template>
          <span>ICD 编码查询</span>
        </a-menu-item>

        <a-menu-divider />

        <a-menu-item key="upload">
          <template #icon>
            <CloudUploadOutlined />
          </template>
          <span>数据上传</span>
        </a-menu-item>
        <a-menu-item key="messages">
          <template #icon>
            <BellOutlined />
          </template>
          <span>质控消息</span>
        </a-menu-item>
      </a-menu>
    </aside>

    <!-- 主内容区 -->
    <main class="ws-v2-main">
      <!-- 工作台视图 -->
      <div
        v-if="currentView === 'workbench'"
        class="workbench-layout"
      >
        <header class="workbench-hero">
          <div>
            <span class="workbench-eyebrow">工作台</span>
            <h2>病案质控工作台</h2>
            <p>集中查看病案原文、首页抽取、质控结果和 DRG/DIP 预分组。</p>
          </div>
          <div class="workbench-hero-actions">
            <a-tag color="blue">
              {{ testCases.length }} 份病历
            </a-tag>
            <a-button
              v-if="demoCase"
              type="primary"
              :loading="extracting"
              @click="extractStructuredData"
            >
              <ThunderboltOutlined /> AI 提取
            </a-button>
          </div>
        </header>

        <section class="workbench-metric-strip">
          <article class="workbench-metric-card">
            <span>当前病历</span>
            <strong>{{ currentCaseIndex >= 0 ? currentCaseIndex + 1 : '-' }}</strong>
            <small>当前工作序号</small>
          </article>
          <article class="workbench-metric-card">
            <span>结构化首页</span>
            <strong>{{ frontpage ? '已生成' : '待提取' }}</strong>
            <small>病案首页字段抽取</small>
          </article>
          <article class="workbench-metric-card">
            <span>DRG/DIP</span>
            <strong>{{ drgResult ? '已模拟' : '待分组' }}</strong>
            <small>预入组结果验证</small>
          </article>
        </section>

        <!-- 上方双栏区 -->
        <div
          ref="panelsRef"
          class="workbench-panels"
        >
          <!-- 左栏：病历原文 -->
          <div
            class="panel-left"
            :style="{ width: leftPanelWidth + '%' }"
          >
            <div class="panel-header">
              <span class="panel-title"> <FileTextOutlined /> 病历原文 </span>
              <a-space>
                <a-button
                  v-if="demoCase"
                  size="small"
                  type="primary"
                  :loading="extracting"
                  @click="extractStructuredData"
                >
                  <ThunderboltOutlined /> AI 提取
                </a-button>
              </a-space>
            </div>
            <div class="panel-body custom-scrollbar">
              <MedicalRecordPanel
                :medical-text="demoCase?.medical_text || ''"
                :loading="loading"
                :test-cases="testCases"
                @select-test-case="loadDemoCase"
              />
            </div>
          </div>

          <!-- 可拖拽分隔线 -->
          <div
            class="resize-handle"
            @mousedown="startResize"
          />

          <!-- 右栏：分析面板 -->
          <div
            class="panel-right"
            :style="{ width: 100 - leftPanelWidth + '%' }"
          >
            <div class="panel-header">
              <a-segmented
                v-model:value="activeTab"
                :options="analysisTabs"
                size="small"
              />
            </div>
            <div class="panel-body custom-scrollbar">
              <!-- Tab1: 首页结果 (M1) -->
              <StructuredDataView
                v-if="activeTab === 'frontpage'"
                :extracting="extracting"
                :extraction-progress="extractionProgress"
                :extraction-status="extractionStatus"
                :frontpage="frontpage"
                :has-medical-text="!!demoCase?.medical_text"
                @extract="extractStructuredData"
              />

              <!-- Tab2: 质控结果 (M2 + M3-A) -->
              <div
                v-else-if="activeTab === 'qc'"
                class="tab-placeholder"
              >
                <SafetyCertificateOutlined style="font-size: 48px; color: #0a6cff" />
                <h3>首页质控</h3>
                <p>形式质控（M2）+ 内涵质控（M3-A）</p>
                <p class="hint">
                  规则引擎接入后展示结构化问题与复核入口
                </p>
              </div>

              <!-- Tab3: DRG 分组 (M6) -->
              <DRGGroupingTab
                v-else-if="activeTab === 'drg'"
                :drg-result="drgResult"
                :loading="drgGrouping"
                :has-frontpage="!!frontpage"
                :main-diagnosis-code="
                  frontpage?.primary_diagnosis_code ||
                    frontpage?.diagnoses?.discharge_main_icd ||
                    ''
                "
                :main-diagnosis-text="
                  frontpage?.primary_diagnosis_name ||
                    frontpage?.diagnoses?.discharge_main_diagnosis_text ||
                    ''
                "
                :main-procedure-code="
                  frontpage?.main_procedure_code || frontpage?.procedures?.main?.code || ''
                "
                :main-procedure-name="
                  frontpage?.main_procedure_name || frontpage?.procedures?.main?.name || ''
                "
                @group="performDRGGrouping"
                @open-optimization="openOptimization"
              />

              <!-- Tab4: AI 画像 (M3-B) -->
              <AIProfileDashboard
                v-else-if="activeTab === 'profile'"
                :frontpage="frontpage"
              />

              <!-- Tab5: ICD 查询 (M4) -->
              <ICDSearchPanel v-else-if="activeTab === 'icd'" />
            </div>
          </div>
        </div>

        <!-- 底部：病历选择栏 -->
        <div class="workbench-footer">
          <div class="footer-header">
            <span class="panel-title"> <ProfileOutlined /> 病历队列 </span>
            <a-space>
              <a-tag color="blue">
                {{ testCases.length }} 份
              </a-tag>
            </a-space>
          </div>
          <div class="test-case-bar">
            <a-button
              v-for="(tc, idx) in testCases"
              :key="idx"
              :type="currentCaseIndex === idx ? 'primary' : 'default'"
              size="small"
              :loading="loading && currentCaseIndex === idx"
              @click="loadDemoCase(idx)"
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
      <InProcessMonitoringView v-else-if="currentView === 'mid-analysis'" />

      <!-- 付费监测 -->
      <PaymentMonitoringView v-else-if="currentView === 'payment'" />

      <!-- DRG 事后分析 -->
      <div
        v-else-if="currentView === 'post-analysis'"
        class="post-analysis-host"
      >
        <section
          v-if="uploadedAnalysis"
          class="uploaded-analysis-banner"
          data-testid="uploaded-analysis-summary"
        >
          <div class="uploaded-analysis-banner__head">
            <div>
              <strong>智能上传分析结果已就绪</strong>
              <span class="uploaded-analysis-banner__meta">
                共 {{ uploadedAnalysisCaseCount }} 条病例 · {{ uploadedAnalysisChartCount }} 个图表
              </span>
            </div>
            <a-button size="small" @click="clearUploadedAnalysis">清除上传结果</a-button>
          </div>
          <ul
            v-if="uploadedAnalysis.aiInsights.length"
            class="uploaded-analysis-banner__insights"
          >
            <li v-for="(insight, idx) in uploadedAnalysis.aiInsights" :key="idx">
              {{ insight }}
            </li>
          </ul>
        </section>
        <PostEventAnalysisView
          :session-id="selectedSessionId || undefined"
          :batch-id="selectedBatchId || undefined"
        />
      </div>

      <!-- 数据上传 -->
      <ExcelUploadView
        v-else-if="currentView === 'upload'"
        @go-analysis="handleGoAnalysis"
        @analysis-ready="handleAnalysisReady"
      />

      <!-- 质控消息 -->
      <div
        v-else-if="currentView === 'messages'"
        class="qc-message-page"
      >
        <header class="qc-message-header">
          <div>
            <span class="qc-message-eyebrow">质控消息</span>
            <h2>病案问题概览</h2>
            <p>集中推送当天高频病案问题，辅助质控人员快速定位科室和病历。</p>
          </div>
          <button
            type="button"
            class="qc-message-primary"
          >
            <RefreshCw class="qc-message-button-icon" />
            刷新消息
          </button>
        </header>

        <section class="qc-message-metrics">
          <article class="qc-message-metric-card">
            <ClipboardList class="qc-message-metric-icon" />
            <div>
              <span>今日问题</span>
              <strong>128</strong>
              <small>较昨日 +12</small>
            </div>
          </article>
          <article class="qc-message-metric-card">
            <AlertTriangle class="qc-message-metric-icon qc-message-metric-icon--risk" />
            <div>
              <span>高风险</span>
              <strong>36</strong>
              <small>优先复核</small>
            </div>
          </article>
          <article class="qc-message-metric-card">
            <Building2 class="qc-message-metric-icon" />
            <div>
              <span>涉及科室</span>
              <strong>12</strong>
              <small>前 5 科室集中</small>
            </div>
          </article>
          <article class="qc-message-metric-card qc-message-metric-card--safe">
            <ShieldCheck class="qc-message-metric-icon" />
            <div>
              <span>处理完成</span>
              <strong>74</strong>
              <small>闭环率 57.8%</small>
            </div>
          </article>
        </section>

        <section class="qc-message-grid">
          <div class="qc-message-panel qc-message-panel--list">
            <div class="qc-message-panel-head">
              <div>
                <h3>消息列表</h3>
                <p>按风险和集中度排序，默认显示需要优先处理的问题。</p>
              </div>
              <span class="qc-message-chip">实时</span>
            </div>
            <div class="qc-message-list">
              <article class="qc-message-item qc-message-item--risk">
                <span class="qc-message-item-dot" />
                <div>
                  <h4>出院诊断与首页主诊断不一致</h4>
                  <p>普通外科 12 份病历集中出现，建议优先核对首页诊断和出院记录诊断。</p>
                  <small>最近更新 09:42 · 12 份病历</small>
                </div>
                <button type="button">
                  查看
                </button>
              </article>
              <article class="qc-message-item">
                <span class="qc-message-item-dot" />
                <div>
                  <h4>术后 24 小时内未完成手术记录</h4>
                  <p>骨科、普外科存在时限风险，需核对手术时间和文书记录时间。</p>
                  <small>最近更新 09:18 · 8 份病历</small>
                </div>
                <button type="button">
                  查看
                </button>
              </article>
              <article class="qc-message-item">
                <span class="qc-message-item-dot" />
                <div>
                  <h4>CT/MRI 阳性结果未在病程中分析</h4>
                  <p>影像报告已出具，但病程记录未见对应分析，建议补充诊疗依据。</p>
                  <small>最近更新 08:56 · 6 份病历</small>
                </div>
                <button type="button">
                  查看
                </button>
              </article>
            </div>
          </div>

          <aside class="qc-message-panel qc-message-panel--insight">
            <div class="qc-message-panel-head">
              <div>
                <h3>科室集中度</h3>
                <p>按今日问题数排序</p>
              </div>
            </div>
            <div class="qc-message-rank-list">
              <div class="qc-message-rank-item">
                <span>1</span>
                <strong>普通外科</strong>
                <em>24</em>
              </div>
              <div class="qc-message-rank-bar">
                <i style="width: 92%" />
              </div>
              <div class="qc-message-rank-item">
                <span>2</span>
                <strong>骨科</strong>
                <em>18</em>
              </div>
              <div class="qc-message-rank-bar">
                <i style="width: 72%" />
              </div>
              <div class="qc-message-rank-item">
                <span>3</span>
                <strong>消化内科</strong>
                <em>15</em>
              </div>
              <div class="qc-message-rank-bar">
                <i style="width: 60%" />
              </div>
              <div class="qc-message-rank-item">
                <span>4</span>
                <strong>神经内科</strong>
                <em>11</em>
              </div>
              <div class="qc-message-rank-bar">
                <i style="width: 44%" />
              </div>
            </div>
          </aside>
        </section>
      </div>

      <!-- ICD 编码查询（独立全屏视图） -->
      <div
        v-else-if="currentView === 'icd-search'"
        class="icd-fullpage"
      >
        <ICDSearchPanel />
      </div>
    </main>

    <!-- 编码优化建议抽屉 -->
    <CodingOptimizationDrawer
      :open="suggestionDrawerVisible"
      :loading="suggestionsLoading"
      :suggestions="suggestions"
      :get-suggestion-title="getSuggestionTitle"
      @update:open="suggestionDrawerVisible = $event"
      @handle="handleSuggestionAction"
    />

    <!-- 质控提醒浮动窗口 -->
    <QCAlertPanel
      :frontpage="frontpage"
      :analyzing="extracting"
      @refresh="extractStructuredData"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { message } from 'ant-design-vue'
import type { MenuInfo } from 'ant-design-vue/es/menu/src/interface'
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
import { AlertTriangle, Building2, ClipboardList, RefreshCw, ShieldCheck } from 'lucide-vue-next'
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
} from '@/views/workstation-v4/frontpage/components'
import ICDSearchPanel from './components/ICDSearchPanel.vue'
import QCAlertPanel from './components/QCAlertPanel.vue'
import '@/views/workstation-v4/frontpage/components/drg-dip-workbench.css'
// 复用 composables
import {
  useMedicalTextExtraction,
  useDRGGrouping,
} from '@/views/workstation-v4/frontpage/composables'

// ==================== Props ====================
const props = withDefaults(
  defineProps<{
    embedded?: boolean
    initialView?: string
  }>(),
  {
    embedded: false,
    initialView: 'workbench',
  },
)

interface UploadedAnalysisPayload {
  charts: Record<string, any>
  aiInsights: string[]
  analysisResults: Record<string, any>
}

const UPLOADED_ANALYSIS_STORAGE_KEY = 'medqc:smart-upload-analysis-ready'

const emit = defineEmits<{
  (e: 'analysis-ready', data: UploadedAnalysisPayload): void
}>()

// ==================== 布局状态 ====================
const sidebarCollapsed = ref(false)
const menuSelectedKeys = ref([props.initialView || 'workbench'])
const currentView = ref(props.initialView || 'workbench')
const activeTab = ref('frontpage')

// 嵌入模式下，跟随路由 prop 变化切换视图
watch(
  () => props.initialView,
  (newView) => {
    if (newView && props.embedded) {
      currentView.value = newView
      menuSelectedKeys.value = [newView]
    }
  },
)

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

function readStoredUploadedAnalysis(): UploadedAnalysisPayload | null {
  try {
    const raw = window.sessionStorage?.getItem(UPLOADED_ANALYSIS_STORAGE_KEY)
    if (!raw) return null
    const parsed = JSON.parse(raw)
    if (!parsed || typeof parsed !== 'object') return null
    return {
      charts: parsed.charts && typeof parsed.charts === 'object' ? parsed.charts : {},
      aiInsights: Array.isArray(parsed.aiInsights) ? parsed.aiInsights : [],
      analysisResults:
        parsed.analysisResults && typeof parsed.analysisResults === 'object'
          ? parsed.analysisResults
          : {},
    }
  } catch {
    return null
  }
}

const uploadedAnalysis = ref<UploadedAnalysisPayload | null>(readStoredUploadedAnalysis())
const uploadedAnalysisChartCount = computed(
  () => Object.keys(uploadedAnalysis.value?.charts || {}).length,
)
const uploadedAnalysisCaseCount = computed(() =>
  Number(uploadedAnalysis.value?.analysisResults?.overview?.total_cases || 0),
)

// ===== Composables =====
const { extracting, extractionProgress, extractionStatus, extractStructuredData } =
  useMedicalTextExtraction({
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
import { getBuiltinTestCases } from '@/views/workstation-v4/frontpage/data/testCases'

const testCases = ref(getBuiltinTestCases())

// 加载测试用例
async function loadDemoCase(idx: number) {
  if (idx < 0 || idx >= testCases.value.length) return
  loading.value = true
  currentCaseIndex.value = idx
  try {
    const tc = testCases.value[idx]
    await new Promise((resolve) => setTimeout(resolve, 300))
    demoCase.value = {
      case_id: `case_${idx + 1}`,
      description: tc.description,
      medical_text: tc.medical_text,
      frontpage: null,
      insurance_claim: null,
    }
    message.success(`${tc.name} 加载成功`)
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

function handleSuggestionAction(id: number, action: 'accept' | 'reject') {
  const caseId = demoCase.value?.case_id
  if (!caseId) {
    message.warning('未找到当前病历，无法处理建议')
    return
  }
  handleSuggestion(id, action, caseId)
}

// ==================== 导航 ====================
function onMenuClick(info: MenuInfo) {
  const key = String(info.key)
  currentView.value = key
  menuSelectedKeys.value = [key]
}

function handleGoAnalysis(sessionId: string, batchId: string) {
  selectedSessionId.value = sessionId
  selectedBatchId.value = batchId
  currentView.value = 'pre-analysis'
  menuSelectedKeys.value = ['pre-analysis']
}

function handleAnalysisReady(data: { charts: any; aiInsights: string[]; analysisResults: any }) {
  const payload: UploadedAnalysisPayload = {
    charts: data?.charts && typeof data.charts === 'object' ? data.charts : {},
    aiInsights: Array.isArray(data?.aiInsights) ? [...data.aiInsights] : [],
    analysisResults:
      data?.analysisResults && typeof data.analysisResults === 'object'
        ? data.analysisResults
        : {},
  }
  uploadedAnalysis.value = payload
  try {
    window.sessionStorage?.setItem(UPLOADED_ANALYSIS_STORAGE_KEY, JSON.stringify(payload))
  } catch {
    // 忽略存储配额限制，保留内存态
  }
  emit('analysis-ready', payload)
  // 智能上传分析完成后，自动切换到事后分析视图
  currentView.value = 'post-analysis'
  menuSelectedKeys.value = ['post-analysis']
}

function clearUploadedAnalysis() {
  uploadedAnalysis.value = null
  try {
    window.sessionStorage?.removeItem(UPLOADED_ANALYSIS_STORAGE_KEY)
  } catch {
    // 忽略存储异常
  }
}

defineExpose({
  uploadedAnalysis,
  clearUploadedAnalysis,
})

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
  background: #f5f5f7;
  overflow: hidden;
  color: #1d1d1f;
  font-family:
    'Source Han Sans SC', 'San Francisco', 'SF Pro Text', 'SF Pro Display', Inter, 'PingFang SC',
    'Microsoft YaHei UI', 'Microsoft YaHei', system-ui, sans-serif;
}

/* ==================== 侧边栏 ==================== */
.ws-v2-sidebar {
  width: 220px;
  background: rgba(255, 255, 255, 0.86);
  border-right: 1px solid rgba(0, 0, 0, 0.08);
  -webkit-backdrop-filter: blur(18px);
  backdrop-filter: blur(18px);
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
  border-bottom: 1px solid rgba(0, 0, 0, 0.08);
}
.sidebar-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 600;
  font-size: 15px;
  color: #1d1d1f;
  white-space: nowrap;
}

.ws-v2-sidebar :deep(.ant-menu) {
  flex: 1;
  border-inline-end: 0;
  background: transparent;
  color: rgba(29, 29, 31, 0.68);
  font-family:
    'Source Han Sans SC', 'San Francisco', 'SF Pro Text', 'SF Pro Display', Inter, 'PingFang SC',
    'Microsoft YaHei UI', 'Microsoft YaHei', system-ui, sans-serif;
}

.ws-v2-sidebar :deep(.ant-menu-item),
.ws-v2-sidebar :deep(.ant-menu-submenu-title) {
  width: calc(100% - 16px);
  height: 38px;
  margin: 4px 8px;
  border-radius: 10px;
  color: rgba(29, 29, 31, 0.68);
  font-size: 13px;
  font-weight: 600;
  line-height: 38px;
  transition:
    background 0.25s cubic-bezier(0.25, 0.1, 0.25, 1),
    color 0.25s cubic-bezier(0.25, 0.1, 0.25, 1),
    transform 0.25s cubic-bezier(0.25, 0.1, 0.25, 1);
}

.ws-v2-sidebar :deep(.ant-menu-item:hover),
.ws-v2-sidebar :deep(.ant-menu-submenu-title:hover) {
  background: rgba(0, 0, 0, 0.05);
  color: #1d1d1f;
  transform: translateX(1px);
}

.ws-v2-sidebar :deep(.ant-menu-item-selected) {
  background: rgba(10, 108, 255, 0.1);
  color: #0a6cff;
}

.ws-v2-sidebar :deep(.ant-menu-item-selected::after) {
  display: none;
}

.ws-v2-sidebar :deep(.ant-menu-item-selected::before) {
  position: absolute;
  top: 9px;
  bottom: 9px;
  left: 0;
  width: 3px;
  border-radius: 999px;
  background: #0a6cff;
  content: '';
}

.ws-v2-sidebar :deep(.ant-menu-submenu-selected > .ant-menu-submenu-title),
.ws-v2-sidebar :deep(.ant-menu-submenu-open > .ant-menu-submenu-title) {
  color: #0a6cff;
}

.ws-v2-sidebar :deep(.ant-menu-sub) {
  margin: 2px 8px 8px;
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.62);
}

.ws-v2-sidebar :deep(.ant-menu-item-divider) {
  margin: 10px 16px;
  border-color: rgba(0, 0, 0, 0.08);
}

.ws-v2 :deep(.ant-btn),
.workbench-layout :deep(.ant-segmented),
.workbench-layout :deep(.ant-tag) {
  font-family:
    'Source Han Sans SC', 'San Francisco', 'SF Pro Text', 'SF Pro Display', Inter, 'PingFang SC',
    'Microsoft YaHei UI', 'Microsoft YaHei', system-ui, sans-serif;
}

.ws-v2 :deep(.ant-btn) {
  border-radius: 8px;
  font-size: 13px;
  font-weight: 600;
}

.ws-v2 :deep(.ant-btn-primary) {
  border-color: #0a6cff;
  background: #0a6cff;
  box-shadow: 0 5px 14px rgba(10, 108, 255, 0.16);
}

.ws-v2 :deep(.ant-btn-primary:not(:disabled):hover) {
  border-color: #0a5fd6;
  background: #0a5fd6;
}

.workbench-layout :deep(.ant-tag-blue) {
  border-color: rgba(10, 108, 255, 0.14);
  background: rgba(10, 108, 255, 0.06);
  color: #0a6cff;
  font-size: 12px;
  font-weight: 650;
}

.workbench-layout :deep(.ant-segmented) {
  border: 1px solid rgba(0, 0, 0, 0.08);
  border-radius: 10px;
  background: rgba(0, 0, 0, 0.04);
  padding: 3px;
}

.workbench-layout :deep(.ant-segmented-item) {
  border-radius: 7px;
  color: rgba(29, 29, 31, 0.58);
  font-size: 13px;
  font-weight: 600;
}

.workbench-layout :deep(.ant-segmented-item-selected) {
  color: #0a6cff;
}

/* ==================== 嵌入模式 ====================  */
.ws-v2-embedded {
  height: calc(100vh - 64px);
  background: #f5f5f7;
}

/* ==================== 主内容区 ==================== */
.ws-v2-main {
  flex: 1;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  background: #f5f5f7;
}

/* ==================== 工作台布局 ==================== */
.workbench-layout {
  display: flex;
  flex-direction: column;
  height: 100%;
  gap: 16px;
  padding: 24px;
  overflow: hidden;
  background: #f5f5f7;
  color: #1d1d1f;
  font-family:
    'Source Han Sans SC', 'San Francisco', 'SF Pro Text', 'SF Pro Display', Inter, 'PingFang SC',
    'Microsoft YaHei UI', 'Microsoft YaHei', system-ui, sans-serif;
}
.workbench-hero {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  flex-shrink: 0;
}
.workbench-eyebrow {
  display: block;
  margin-bottom: 6px;
  color: #0a6cff;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0;
  line-height: 1;
}
.workbench-hero h2 {
  margin: 0;
  color: #1d1d1f;
  font-size: 28px;
  font-weight: 700;
  line-height: 31px;
}
.workbench-hero p {
  margin: 8px 0 0;
  color: rgba(29, 29, 31, 0.6);
  font-size: 14px;
  font-weight: 500;
  line-height: 22px;
}
.workbench-hero-actions {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}
.workbench-metric-strip {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 14px;
  flex-shrink: 0;
}
.workbench-metric-card {
  min-height: 94px;
  padding: 18px 20px;
  border: 1px solid rgba(0, 0, 0, 0.08);
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.86);
  -webkit-backdrop-filter: blur(18px);
  backdrop-filter: blur(18px);
  box-shadow:
    0 1px 4px rgba(0, 0, 0, 0.045),
    0 2px 8px rgba(0, 0, 0, 0.035);
  transition:
    border-color 0.25s cubic-bezier(0.25, 0.1, 0.25, 1),
    box-shadow 0.25s cubic-bezier(0.25, 0.1, 0.25, 1),
    transform 0.25s cubic-bezier(0.25, 0.1, 0.25, 1);
}
.workbench-metric-card:hover,
.workbench-panels:hover,
.workbench-footer:hover,
.qc-message-metric-card:hover,
.qc-message-panel:hover {
  border-color: rgba(0, 0, 0, 0.14);
  box-shadow:
    0 2px 12px rgba(0, 0, 0, 0.1),
    0 6px 22px rgba(0, 0, 0, 0.075);
  transform: translateY(-2px);
}
.workbench-metric-card span,
.workbench-metric-card small {
  display: block;
  color: rgba(29, 29, 31, 0.56);
  font-size: 12px;
  font-weight: 600;
  line-height: 18px;
}
.workbench-metric-card strong {
  display: block;
  margin: 4px 0 2px;
  color: #1d1d1f;
  font-size: 26px;
  font-weight: 700;
  line-height: 32px;
}
.workbench-panels {
  flex: 1;
  display: flex;
  gap: 0;
  min-height: 0;
  overflow: hidden;
  border: 1px solid rgba(0, 0, 0, 0.08);
  border-radius: 20px;
  background: rgba(255, 255, 255, 0.86);
  -webkit-backdrop-filter: blur(18px);
  backdrop-filter: blur(18px);
  box-shadow:
    0 1px 4px rgba(0, 0, 0, 0.045),
    0 2px 8px rgba(0, 0, 0, 0.035);
  transition:
    border-color 0.25s cubic-bezier(0.25, 0.1, 0.25, 1),
    box-shadow 0.25s cubic-bezier(0.25, 0.1, 0.25, 1),
    transform 0.25s cubic-bezier(0.25, 0.1, 0.25, 1);
}

/* 面板通用 */
.panel-left,
.panel-right {
  display: flex;
  flex-direction: column;
  overflow: hidden;
  min-width: 0;
}
.panel-header {
  height: 52px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 18px;
  background: rgba(255, 255, 255, 0.82);
  border-bottom: 1px solid rgba(0, 0, 0, 0.08);
  flex-shrink: 0;
}
.panel-title {
  font-weight: 650;
  font-size: 14px;
  color: #1d1d1f;
  display: flex;
  align-items: center;
  gap: 6px;
}
.panel-body {
  flex: 1;
  overflow-y: auto;
  padding: 18px;
  background: rgba(250, 250, 252, 0.72);
}

/* 分隔线 */
.resize-handle {
  width: 5px;
  cursor: col-resize;
  background: rgba(0, 0, 0, 0.06);
  transition: background 0.15s;
  flex-shrink: 0;
}
.resize-handle:hover {
  background: rgba(10, 108, 255, 0.42);
}

/* ==================== 底部测试用例栏 ==================== */
.workbench-footer {
  border: 1px solid rgba(0, 0, 0, 0.08);
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.86);
  -webkit-backdrop-filter: blur(18px);
  backdrop-filter: blur(18px);
  box-shadow:
    0 1px 4px rgba(0, 0, 0, 0.045),
    0 2px 8px rgba(0, 0, 0, 0.035);
  flex-shrink: 0;
  overflow: hidden;
  transition:
    border-color 0.25s cubic-bezier(0.25, 0.1, 0.25, 1),
    box-shadow 0.25s cubic-bezier(0.25, 0.1, 0.25, 1),
    transform 0.25s cubic-bezier(0.25, 0.1, 0.25, 1);
}
.footer-header {
  height: 42px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 18px;
  border-bottom: 1px solid rgba(0, 0, 0, 0.08);
}
.test-case-bar {
  display: flex;
  gap: 8px;
  padding: 10px 18px 12px;
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

/* ==================== ICD 全页面 ==================== */
.icd-fullpage {
  height: 100%;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background: #f5f5f7;
}

/* ==================== 质控消息页 ==================== */
.qc-message-page {
  display: flex;
  flex-direction: column;
  gap: 18px;
  height: 100%;
  overflow: auto;
  padding: 24px;
  background: #f5f5f7;
  color: #1d1d1f;
  font-family:
    'Source Han Sans SC', 'San Francisco', 'SF Pro Text', 'SF Pro Display', Inter, 'PingFang SC',
    'Microsoft YaHei UI', 'Microsoft YaHei', system-ui, sans-serif;
  font-feature-settings:
    'rlig' 1,
    'calt' 1;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

.qc-message-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.qc-message-eyebrow {
  display: block;
  margin-bottom: 6px;
  color: #0a6cff;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0;
  line-height: 1;
}

.qc-message-header h2 {
  margin: 0;
  color: #1d1d1f;
  font-size: 28px;
  font-weight: 700;
  line-height: 31px;
}

.qc-message-header p {
  margin: 8px 0 0;
  color: rgba(29, 29, 31, 0.6);
  font-size: 14px;
  font-weight: 500;
  line-height: 22px;
}

.qc-message-primary {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 7px;
  height: 36px;
  padding: 0 14px;
  border: 1px solid #0a6cff;
  border-radius: 10px;
  background: #0a6cff;
  color: #fff;
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.18),
    0 5px 14px rgba(10, 108, 255, 0.18);
  font-size: 13px;
  font-weight: 600;
  transition:
    background 0.25s cubic-bezier(0.25, 0.1, 0.25, 1),
    border-color 0.25s cubic-bezier(0.25, 0.1, 0.25, 1),
    box-shadow 0.25s cubic-bezier(0.25, 0.1, 0.25, 1);
}

.qc-message-primary:hover {
  background: #0a5fd6;
  border-color: #0a5fd6;
}

.qc-message-button-icon {
  width: 15px;
  height: 15px;
  stroke-width: 2.1;
}

.qc-message-metrics {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 14px;
}

.qc-message-metric-card,
.qc-message-panel {
  border: 1px solid rgba(0, 0, 0, 0.08);
  border-radius: 20px;
  background: rgba(255, 255, 255, 0.86);
  -webkit-backdrop-filter: blur(18px);
  backdrop-filter: blur(18px);
  box-shadow:
    0 1px 4px rgba(0, 0, 0, 0.045),
    0 2px 8px rgba(0, 0, 0, 0.035);
}

.qc-message-metric-card {
  display: flex;
  align-items: center;
  gap: 14px;
  min-height: 118px;
  padding: 20px;
}

.qc-message-metric-icon {
  flex: none;
  width: 46px;
  height: 46px;
  padding: 11px;
  border: 1px solid rgba(10, 108, 255, 0.16);
  border-radius: 15px;
  background: rgba(10, 108, 255, 0.08);
  color: #0a6cff;
  stroke-width: 1.9;
}

.qc-message-metric-icon--risk {
  border-color: rgba(239, 68, 68, 0.18);
  background: rgba(239, 68, 68, 0.08);
  color: #ef4444;
}

.qc-message-metric-card--safe .qc-message-metric-icon {
  border-color: rgba(16, 185, 129, 0.18);
  background: rgba(16, 185, 129, 0.08);
  color: #059669;
}

.qc-message-metric-card span,
.qc-message-metric-card small {
  display: block;
  color: rgba(29, 29, 31, 0.56);
  font-size: 12px;
  font-weight: 600;
  line-height: 18px;
}

.qc-message-metric-card strong {
  display: block;
  margin: 4px 0 2px;
  color: #1d1d1f;
  font-size: 30px;
  font-weight: 700;
  line-height: 34px;
  font-variant-numeric: tabular-nums;
}

.qc-message-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 340px;
  gap: 18px;
  min-height: 0;
}

.qc-message-panel {
  min-width: 0;
  overflow: hidden;
}

.qc-message-panel-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  padding: 18px 20px 14px;
  border-bottom: 1px solid rgba(0, 0, 0, 0.08);
}

.qc-message-panel-head h3 {
  margin: 0;
  color: #1d1d1f;
  font-size: 17px;
  font-weight: 650;
  line-height: 22px;
}

.qc-message-panel-head p {
  margin: 5px 0 0;
  color: rgba(29, 29, 31, 0.56);
  font-size: 13px;
  font-weight: 500;
  line-height: 20px;
}

.qc-message-chip {
  display: inline-flex;
  align-items: center;
  height: 26px;
  padding: 0 9px;
  border: 1px solid rgba(10, 108, 255, 0.14);
  border-radius: 999px;
  background: rgba(10, 108, 255, 0.06);
  color: #0a6cff;
  font-size: 12px;
  font-weight: 650;
}

.qc-message-list {
  padding: 8px 10px 12px;
}

.qc-message-item {
  display: grid;
  grid-template-columns: 10px minmax(0, 1fr) auto;
  align-items: center;
  gap: 12px;
  padding: 14px 12px;
  border-radius: 14px;
  transition:
    background 0.25s cubic-bezier(0.25, 0.1, 0.25, 1),
    transform 0.25s cubic-bezier(0.25, 0.1, 0.25, 1);
}

.qc-message-item:hover {
  background: rgba(0, 0, 0, 0.025);
  transform: translateY(-1px);
}

.qc-message-item-dot {
  width: 8px;
  height: 8px;
  border-radius: 999px;
  background: #0a6cff;
}

.qc-message-item--risk .qc-message-item-dot {
  background: #ef4444;
}

.qc-message-item h4 {
  margin: 0;
  color: #1d1d1f;
  font-size: 14px;
  font-weight: 650;
  line-height: 20px;
}

.qc-message-item p {
  margin: 4px 0 0;
  color: rgba(29, 29, 31, 0.6);
  font-size: 13px;
  font-weight: 500;
  line-height: 20px;
}

.qc-message-item small {
  display: block;
  margin-top: 6px;
  color: rgba(29, 29, 31, 0.38);
  font-size: 12px;
  font-weight: 500;
}

.qc-message-item button {
  height: 32px;
  padding: 0 12px;
  border: 1px solid rgba(10, 108, 255, 0.16);
  border-radius: 9px;
  background: rgba(10, 108, 255, 0.06);
  color: #0a6cff;
  font-size: 13px;
  font-weight: 650;
}

.qc-message-rank-list {
  padding: 16px 18px 20px;
}

.qc-message-rank-item {
  display: grid;
  grid-template-columns: 26px minmax(0, 1fr) auto;
  align-items: center;
  gap: 8px;
  margin-top: 10px;
}

.qc-message-rank-item:first-child {
  margin-top: 0;
}

.qc-message-rank-item span {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  border-radius: 8px;
  background: rgba(10, 108, 255, 0.08);
  color: #0a6cff;
  font-size: 12px;
  font-weight: 700;
}

.qc-message-rank-item strong {
  min-width: 0;
  overflow: hidden;
  color: #1d1d1f;
  font-size: 13px;
  font-weight: 650;
  line-height: 18px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.qc-message-rank-item em {
  color: #1d1d1f;
  font-size: 13px;
  font-style: normal;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
}

.qc-message-rank-bar {
  height: 6px;
  margin: 8px 0 12px 34px;
  border-radius: 999px;
  background: rgba(0, 0, 0, 0.06);
  overflow: hidden;
}

.qc-message-rank-bar i {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: #0a6cff;
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
  background: rgba(29, 29, 31, 0.16);
  border-radius: 3px;
}
.custom-scrollbar::-webkit-scrollbar-thumb:hover {
  background: rgba(29, 29, 31, 0.26);
}

/* ===== v7.1 液态玻璃覆盖：工作台内嵌时的容器与各子页页头 ===== */
.ws-v2,
.ws-v2-embedded,
.ws-v2-main,
.workbench-layout,
.icd-fullpage,
.qc-message-page {
  background: transparent;
}

/* 外壳已无顶栏，嵌入高度不再扣除 64px */
.ws-v2-embedded {
  height: 100vh;
}

.ws-v2-main :deep(.pre-analysis-shell),
.ws-v2-main :deep(.in-process-page),
.ws-v2-main :deep(.payment-monitoring-page),
.ws-v2-main :deep(.post-event-analysis-page),
.ws-v2-main :deep(.upload-workstation),
.ws-v2-main :deep(.icd-search-hero) {
  --bg: transparent;
  background: transparent !important;
  font-family: var(--mq-font-family);
}

/* 页头标题统一 40px */
.ws-v2-main :deep(.command-header .title-block h1),
.ws-v2-main :deep(.in-process-page .page-header h2),
.ws-v2-main :deep(.payment-title),
.ws-v2-main :deep(.analysis-header h2),
.ws-v2-main :deep(.upload-header h2) {
  margin: 4px 0 0;
  color: var(--mq-text-primary);
  font-family: var(--mq-font-display);
  font-size: var(--mq-font-title) !important;
  font-weight: 700 !important;
  letter-spacing: -0.03em;
  line-height: 1.1;
}

/* 眉标统一灰色、无底色 */
.ws-v2-main :deep(.command-header .eyebrow),
.ws-v2-main :deep(.payment-eyebrow),
.ws-v2-main :deep(.upload-eyebrow),
.ws-v2-main :deep(.in-process-page .breadcrumb) {
  padding: 0;
  border: 0;
  background: transparent;
  color: var(--mq-text-tertiary);
  font-size: var(--mq-font-13);
  font-weight: 600;
  letter-spacing: 0;
  text-transform: none;
}

/* 事前分析顶部主卡与各子页白卡：统一玻璃卡 */
.ws-v2-main :deep(.command-header),
.ws-v2-main :deep(.drg-workbench-page .panel),
.ws-v2-main :deep(.upload-page > section),
.ws-v2-main :deep(.icd-fullpage .rounded-2xl) {
  border-color: var(--mq-glass-border) !important;
  border-radius: var(--mq-radius-card) !important;
  background: var(--mq-glass-bg) !important;
  box-shadow: var(--mq-glass-shadow) !important;
}

.post-analysis-host {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.uploaded-analysis-banner {
  margin: 16px 24px 0;
  padding: 14px 18px;
  border: 1px solid rgba(10, 108, 255, 0.18);
  border-radius: 14px;
  background: rgba(10, 108, 255, 0.05);
}

.uploaded-analysis-banner__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}

.uploaded-analysis-banner__meta {
  margin-left: 10px;
  font-size: 13px;
  color: rgba(29, 29, 31, 0.65);
}

.uploaded-analysis-banner__insights {
  margin: 10px 0 0;
  padding-left: 18px;
  font-size: 13px;
  color: #1d1d1f;
}
</style>
