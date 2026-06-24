<template>
  <div class="workstation-container">
    <!-- 顶部工具栏 -->
    <div class="workstation-toolbar">
      <div class="toolbar-left">
        <a-input-search
          v-model:value="searchText"
          placeholder="搜索患者姓名、住院号、病案号..."
          style="width: 320px"
          allow-clear
          @search="onSearch"
          @change="onSearchChange"
        >
          <template #prefix>
            <SearchOutlined />
          </template>
        </a-input-search>
        <a-select
          v-model:value="selectedDept"
          placeholder="选择科室"
          style="width: 160px; margin-left: 12px"
          allow-clear
          @change="filterRecords"
        >
          <a-select-option value="all">
            全部科室
          </a-select-option>
          <a-select-option
            v-for="dept in deptList"
            :key="dept"
            :value="dept"
          >
            {{ dept }}
          </a-select-option>
        </a-select>
        <a-select
          v-model:value="selectedStatus"
          placeholder="状态"
          style="width: 120px; margin-left: 8px"
          allow-clear
          @change="filterRecords"
        >
          <a-select-option value="all">
            全部
          </a-select-option>
          <a-select-option value="pending">
            待质控
          </a-select-option>
          <a-select-option value="completed">
            已质控
          </a-select-option>
        </a-select>
      </div>
      <div class="toolbar-right">
        <a-button @click="router.push('/workstation-v4/qc-overview')">
          <AlertOutlined />
          质控概览
        </a-button>
        <a-button
          type="primary"
          @click="router.push('/dashboard/workstation/import')"
        >
          <UploadOutlined />
          导入病历数据
        </a-button>
      </div>
    </div>

    <!-- 三栏布局主体 -->
    <div class="workstation-body">
      <!-- 左侧：病历列表 -->
      <div
        class="panel panel-left"
        :style="{ width: leftPanelWidth + 'px' }"
      >
        <div class="panel-header">
          <span class="panel-title">病历列表</span>
          <a-badge
            :count="filteredRecords.length"
            :number-style="{ backgroundColor: '#1677ff' }"
          />
        </div>
        <div class="record-list">
          <div
            v-for="record in filteredRecords"
            :key="record.visitId"
            class="record-item"
            :class="{ active: selectedRecord?.visitId === record.visitId }"
            @click="selectRecord(record)"
          >
            <div class="record-item-header">
              <span class="patient-name">{{ record.name }}</span>
              <a-tag
                :color="record.status === 'completed' ? 'green' : 'processing'"
                size="small"
              >
                {{ record.status === 'completed' ? '已质控' : '待质控' }}
              </a-tag>
            </div>
            <div class="record-item-meta">
              <span>{{ record.deptName }} · {{ record.bedNo }} · {{ record.inpatNo }}</span>
            </div>
            <div class="record-item-diag">
              {{ record.diagnosisMain }}
            </div>
            <div class="record-item-date">
              {{ record.admissionDate }} ~ {{ record.dischargeDate || '在院' }}
            </div>
          </div>
          <!-- 空状态 -->
          <div
            v-if="filteredRecords.length === 0"
            class="empty-state"
          >
            <InboxOutlined style="font-size: 48px; color: #d9d9d9" />
            <p>暂无匹配的病历</p>
          </div>
        </div>
      </div>

      <!-- 可拖动分隔条 -->
      <div
        class="divider"
        @mousedown="startResize('left', $event)"
      />

      <!-- 中间：病历文书内容 -->
      <div class="panel panel-center">
        <template v-if="selectedRecord">
          <div class="panel-header">
            <a-segmented
              v-model:value="activeDocTab"
              :options="docTabs"
              size="small"
            />
            <div class="panel-header-extra">
              <a-tag color="blue">
                {{ selectedRecord.deptName }}
              </a-tag>
              <span class="header-name">{{ selectedRecord.name }} · {{ selectedRecord.age }} ·
                {{ selectedRecord.sex }}</span>
            </div>
          </div>
          <div class="document-content">
            <div
              v-if="activeDocTab === 'admission'"
              class="doc-text"
              v-html="selectedRecord.admissionNote || noDataHtml('入院记录')"
            />
            <div
              v-else-if="activeDocTab === 'discharge'"
              class="doc-text"
              v-html="selectedRecord.dischargeNote || noDataHtml('出院记录')"
            />
            <div
              v-else-if="activeDocTab === 'progress'"
              class="doc-text"
              v-html="selectedRecord.progressNote || noDataHtml('病程记录')"
            />
            <div
              v-else-if="activeDocTab === 'surgery'"
              class="doc-text"
              v-html="selectedRecord.surgeryNote || noDataHtml('手术记录')"
            />
          </div>
        </template>
        <template v-else>
          <div class="empty-state-full">
            <FileSearchOutlined style="font-size: 64px; color: #d9d9d9" />
            <h3>请从左侧选择一份病历</h3>
            <p>选择病历后可浏览文书内容，右侧面板将展示质控和分析结果</p>
          </div>
        </template>
      </div>

      <!-- 可拖动分隔条 -->
      <div
        class="divider"
        @mousedown="startResize('right', $event)"
      />

      <!-- 右侧：质控/分析面板 -->
      <div
        class="panel panel-right"
        :style="{ width: rightPanelWidth + 'px' }"
      >
        <div class="panel-header">
          <a-segmented
            v-model:value="activeAnalysisTab"
            :options="analysisTabs"
            size="small"
          />
        </div>
        <div class="analysis-content">
          <!-- Tab1: 首页生成（复用 StructuredDataView） -->
          <div
            v-if="activeAnalysisTab === 'frontpage'"
            class="tab-content"
          >
            <div
              v-if="!selectedRecord"
              class="empty-hint"
            >
              <FileTextOutlined style="font-size: 32px; color: #d9d9d9" />
              <p>选择病历后自动生成首页</p>
            </div>
            <StructuredDataView
              v-else
              :extracting="bridge.extracting.value"
              :extraction-progress="null"
              :extraction-status="'idle'"
              :frontpage="bridge.frontpage.value"
              :has-medical-text="bridge.hasMedicalText.value"
              @extract="bridge.extractStructuredData"
            />
          </div>

          <!-- Tab2: 质控结果 -->
          <div
            v-if="activeAnalysisTab === 'qc'"
            class="tab-content"
          >
            <div
              v-if="!selectedRecord"
              class="empty-hint"
            >
              <CheckCircleOutlined style="font-size: 32px; color: #d9d9d9" />
              <p>选择病历后运行质控</p>
            </div>
            <div v-else>
              <a-button
                type="primary"
                block
                :loading="qcRunning"
                style="margin-bottom: 16px"
                @click="runQualityControl"
              >
                <SafetyCertificateOutlined />
                运行质控检查
              </a-button>
              <div v-if="qcResults.length > 0">
                <!-- 汇总 -->
                <div class="qc-summary">
                  <div class="qc-stat pass">
                    <CheckCircleOutlined />
                    <span>{{ qcResults.filter((r) => r.passed).length }} 通过</span>
                  </div>
                  <div class="qc-stat fail">
                    <CloseCircleOutlined />
                    <span>{{ qcResults.filter((r) => !r.passed).length }} 不通过</span>
                  </div>
                  <div class="qc-stat score">
                    <span>扣分：{{ qcResults.reduce((s, r) => s + r.deduction, 0) }}</span>
                  </div>
                </div>
                <!-- 规则列表 -->
                <a-collapse
                  :bordered="false"
                  style="background: transparent"
                >
                  <a-collapse-panel
                    v-for="result in qcResults"
                    :key="result.ruleId"
                    :style="{
                      borderLeft: `3px solid ${result.passed ? '#52c41a' : result.severity === 'error' ? '#ff4d4f' : '#faad14'}`,
                    }"
                  >
                    <template #header>
                      <div class="qc-rule-header">
                        <span>{{ result.ruleName }}</span>
                        <a-tag
                          :color="
                            result.passed ? 'green' : result.severity === 'error' ? 'red' : 'orange'
                          "
                          size="small"
                        >
                          {{ result.passed ? '✓' : result.severity === 'error' ? '✗' : '⚠' }}
                        </a-tag>
                      </div>
                    </template>
                    <p class="qc-detail">
                      {{ result.detail }}
                    </p>
                    <div class="qc-meta">
                      <a-tag size="small">
                        {{ result.category }}
                      </a-tag>
                      <span
                        v-if="result.deduction > 0"
                        class="qc-deduction"
                      >-{{ result.deduction }}分</span>
                    </div>
                  </a-collapse-panel>
                </a-collapse>
              </div>
            </div>
          </div>

          <!-- Tab3: ICD编码 -->
          <div
            v-if="activeAnalysisTab === 'icd'"
            class="tab-content"
          >
            <div
              v-if="icdStats"
              class="icd-stats"
            >
              <a-tag color="blue">
                ICD-10: {{ icdStats.icd10_count?.toLocaleString() }} 条
              </a-tag>
              <a-tag color="green">
                ICD-9-CM-3: {{ icdStats.icd9cm3_count?.toLocaleString() }} 条
              </a-tag>
            </div>
            <div style="display: flex; gap: 8px; margin-bottom: 12px">
              <a-input-search
                v-model:value="icdSearchText"
                placeholder="搜索疾病名称、编码、拼音首字母..."
                :loading="icdLoading"
                style="flex: 1"
                @search="searchICD"
              />
              <a-select
                v-model:value="icdCodeType"
                style="width: 130px"
                @change="() => icdSearchText && searchICD(icdSearchText)"
              >
                <a-select-option value="all">
                  全部
                </a-select-option>
                <a-select-option value="icd10">
                  ICD-10
                </a-select-option>
                <a-select-option value="icd9cm3">
                  ICD-9-CM-3
                </a-select-option>
              </a-select>
            </div>
            <div
              v-if="icdTotal > 0"
              class="icd-match-info"
            >
              找到 {{ icdTotal }} 条匹配（显示前 {{ icdResults.length }} 条）
            </div>
            <a-spin :spinning="icdLoading">
              <div
                v-if="icdResults.length > 0"
                class="icd-results"
              >
                <div
                  v-for="item in icdResults"
                  :key="item.code + item.type"
                  class="icd-item"
                >
                  <a-tag
                    :color="item.type === 'icd10' ? 'blue' : 'green'"
                    size="small"
                    style="flex-shrink: 0"
                  >
                    {{ item.type === 'icd10' ? '诊断' : '手术' }}
                  </a-tag>
                  <span class="icd-code">{{ item.code }}</span>
                  <span class="icd-name">{{ item.name }}</span>
                </div>
              </div>
              <div
                v-else-if="icdSearchText && !icdLoading"
                class="empty-hint"
              >
                <p>未找到匹配的编码</p>
              </div>
            </a-spin>
          </div>

          <!-- Tab4: DRG分组 -->
          <div
            v-if="activeAnalysisTab === 'drg'"
            class="tab-content"
          >
            <div
              v-if="!selectedRecord"
              class="empty-hint"
            >
              <ClusterOutlined style="font-size: 32px; color: #d9d9d9" />
              <p>选择病历后进行 DRG 入组</p>
            </div>
            <DRGGroupingTab
              v-else
              :drg-result="bridge.drgResult.value"
              :loading="bridge.drgLoading.value"
              :has-frontpage="bridge.hasFrontpage.value"
              :main-diagnosis-code="bridge.mainDiagnosisCode.value"
              :main-diagnosis-text="bridge.mainDiagnosisText.value"
              :main-procedure-code="bridge.mainProcedureCode.value"
              :main-procedure-name="bridge.mainProcedureName.value"
              @group="bridge.performDRGGrouping"
              @open-optimization="bridge.openOptimizationDrawer"
            />
          </div>
        </div>
      </div>
    </div>

    <!-- 编码优化建议抽屉（复用 CodingOptimizationDrawer） -->
    <CodingOptimizationDrawer
      :open="bridge.suggestionDrawerVisible.value"
      :loading="bridge.suggestionsLoading.value"
      :suggestions="bridge.suggestions.value"
      :get-suggestion-title="bridge.getSuggestionTitle"
      @update:open="bridge.suggestionDrawerVisible.value = $event"
      @handle="bridge.handleSuggestion"
    />
  </div>
</template>

<script setup lang="ts">
/**
 * WorkstationView.vue - 病案智能质控工作站
 *
 * 统一工作站，整合首页自动生成、质控分析、ICD编码查询、DRG分组等功能。
 * 三栏布局：左侧病历列表 | 中间文书内容 | 右侧质控/分析面板
 */
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import {
  SearchOutlined,
  UploadOutlined,
  AlertOutlined,
  FileSearchOutlined,
  FileTextOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  SafetyCertificateOutlined,
  ClusterOutlined,
} from '@ant-design/icons-vue'
import { mockRecords, generateMockQCResults, type MedicalRecord, type QCResult } from './mockData'
import { useWorkstationBridge } from './useWorkstationBridge'
import {
  StructuredDataView,
  DRGGroupingTab,
  CodingOptimizationDrawer,
} from '../demo/frontpage/components'

const router = useRouter()

// ==================== 状态 ====================

// 搜索和筛选
const searchText = ref('')
const selectedDept = ref<string | undefined>(undefined)
const selectedStatus = ref<string | undefined>(undefined)

// 科室列表（从 mock 数据提取）
const deptList = computed(() => [...new Set(mockRecords.map((r) => r.deptName))])

// 面板宽度
const leftPanelWidth = ref(300)
const rightPanelWidth = ref(420)

// 当前选中
const selectedRecord = ref<MedicalRecord | null>(null)

// 筛选后的病历列表
const filteredRecords = computed(() => {
  let list = [...mockRecords]
  if (searchText.value) {
    const q = searchText.value.toLowerCase()
    list = list.filter(
      (r) =>
        r.name.toLowerCase().includes(q) ||
        r.inpatNo.toLowerCase().includes(q) ||
        r.visitId.toLowerCase().includes(q) ||
        r.diagnosisMain.toLowerCase().includes(q),
    )
  }
  if (selectedDept.value && selectedDept.value !== 'all') {
    list = list.filter((r) => r.deptName === selectedDept.value)
  }
  if (selectedStatus.value && selectedStatus.value !== 'all') {
    list = list.filter((r) => r.status === selectedStatus.value)
  }
  return list
})

// 文书 Tab
const activeDocTab = ref('admission')
const docTabs = [
  { label: '入院记录', value: 'admission' },
  { label: '出院记录', value: 'discharge' },
  { label: '病程记录', value: 'progress' },
  { label: '手术记录', value: 'surgery' },
]

// 分析 Tab
const activeAnalysisTab = ref('frontpage')
const analysisTabs = [
  { label: '首页', value: 'frontpage' },
  { label: '质控', value: 'qc' },
  { label: 'ICD', value: 'icd' },
  { label: 'DRG', value: 'drg' },
]

// ===== 桥接层：复用 frontpage-demo 的 composables =====
const bridge = useWorkstationBridge(selectedRecord)

// 质控结果
const qcRunning = ref(false)
const qcResults = ref<QCResult[]>([])

// ICD 编码查询
const icdSearchText = ref('')
const icdResults = ref<any[]>([])
const icdLoading = ref(false)
const icdTotal = ref(0)
const icdCodeType = ref('all')
const icdStats = ref<any>(null)

// ==================== 方法 ====================

function getApiBaseUrl(): string {
  return (import.meta as any).env?.VITE_API_BASE_URL || '/api/v1'
}

function noDataHtml(type: string): string {
  return `<div style="text-align:center;padding:60px 20px;color:#999"><p style="font-size:16px">暂无${type}</p><p style="font-size:13px">该患者尚未录入此类文书</p></div>`
}

function onSearch() {
  // 触发 computed 刷新
}

function onSearchChange() {
  // 实时筛选
}

function filterRecords() {
  // 触发 computed 刷新
}

function selectRecord(record: MedicalRecord) {
  selectedRecord.value = record
  activeDocTab.value = 'admission'
  qcResults.value = []
}

async function runQualityControl() {
  if (!selectedRecord.value) return
  qcRunning.value = true
  try {
    await new Promise((resolve) => setTimeout(resolve, 800))
    qcResults.value = generateMockQCResults(selectedRecord.value)
  } finally {
    qcRunning.value = false
  }
}

async function searchICD(value: string) {
  if (!value.trim()) {
    icdResults.value = []
    icdTotal.value = 0
    return
  }
  icdLoading.value = true
  try {
    const params = new URLSearchParams({
      q: value.trim(),
      type: icdCodeType.value,
      limit: '50',
    })
    const res = await fetch(`${getApiBaseUrl()}/icd/search?${params}`)
    const json = await res.json()
    if (json.success && json.data) {
      icdResults.value = json.data.items || []
      icdTotal.value = json.data.total || 0
    } else {
      icdResults.value = []
      icdTotal.value = 0
    }
  } catch (err) {
    console.error('ICD 搜索失败:', err)
    icdResults.value = []
  } finally {
    icdLoading.value = false
  }
}

async function loadIcdStats() {
  try {
    const res = await fetch(`${getApiBaseUrl()}/icd/stats`)
    const json = await res.json()
    if (json.success) {
      icdStats.value = json.data
    }
  } catch {
    // 后端未启动时静默失败
  }
}

// runDRGGrouping 和 generateFrontPage 已由 bridge 处理

// 面板拖拽调整大小
function startResize(side: 'left' | 'right', event: MouseEvent) {
  const startX = event.clientX
  const startWidth = side === 'left' ? leftPanelWidth.value : rightPanelWidth.value

  const onMouseMove = (e: MouseEvent) => {
    const diff = e.clientX - startX
    if (side === 'left') {
      leftPanelWidth.value = Math.max(220, Math.min(500, startWidth + diff))
    } else {
      rightPanelWidth.value = Math.max(320, Math.min(600, startWidth - diff))
    }
  }

  const onMouseUp = () => {
    document.removeEventListener('mousemove', onMouseMove)
    document.removeEventListener('mouseup', onMouseUp)
  }

  document.addEventListener('mousemove', onMouseMove)
  document.addEventListener('mouseup', onMouseUp)
}

onMounted(() => {
  loadIcdStats()
})
</script>

<style scoped>
.workstation-container {
  display: flex;
  flex-direction: column;
  height: calc(100vh - 64px);
  background: #f0f2f5;
}

.workstation-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 16px;
  background: #fff;
  border-bottom: 1px solid #e8e8e8;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.04);
}

.toolbar-left {
  display: flex;
  align-items: center;
}

.workstation-body {
  display: flex;
  flex: 1;
  overflow: hidden;
}

.panel {
  display: flex;
  flex-direction: column;
  background: #fff;
  overflow: hidden;
}

.panel-left {
  min-width: 220px;
  max-width: 500px;
  border-right: 1px solid #e8e8e8;
}

.panel-center {
  flex: 1;
  min-width: 300px;
}

.panel-right {
  min-width: 320px;
  max-width: 600px;
  border-left: 1px solid #e8e8e8;
}

.panel-header {
  padding: 10px 16px;
  border-bottom: 1px solid #f0f0f0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  flex-shrink: 0;
  flex-wrap: wrap;
}

.panel-header-extra {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
}

.header-name {
  color: #666;
  font-size: 12px;
}

.panel-title {
  font-weight: 600;
  font-size: 14px;
  color: #1a1a1a;
}

.divider {
  width: 4px;
  cursor: col-resize;
  background: #f0f0f0;
  transition: background 0.2s;
  flex-shrink: 0;
}

.divider:hover {
  background: #1677ff;
}

/* 病历列表 */
.record-list {
  flex: 1;
  overflow-y: auto;
  padding: 6px;
}

.record-item {
  padding: 10px 12px;
  border-radius: 8px;
  cursor: pointer;
  margin-bottom: 4px;
  transition: all 0.15s;
  border: 1px solid transparent;
}

.record-item:hover {
  background: #f5f5ff;
  border-color: #e8e8ff;
}

.record-item.active {
  background: #e6f4ff;
  border-color: #91caff;
  box-shadow: 0 1px 4px rgba(22, 119, 255, 0.15);
}

.record-item-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 2px;
}

.patient-name {
  font-weight: 600;
  font-size: 14px;
  color: #1a1a1a;
}

.record-item-meta {
  font-size: 11px;
  color: #888;
}

.record-item-diag {
  font-size: 12px;
  color: #444;
  margin-top: 3px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.record-item-date {
  font-size: 11px;
  color: #aaa;
  margin-top: 2px;
}

/* 文书内容 */
.document-content {
  flex: 1;
  overflow-y: auto;
  padding: 20px 24px;
}

.doc-text {
  font-size: 14px;
  line-height: 1.9;
  color: #333;
}

.doc-text :deep(h4) {
  color: #1a1a1a;
  font-size: 16px;
  margin-bottom: 12px;
  padding-bottom: 8px;
  border-bottom: 2px solid #1677ff;
}

.doc-text :deep(b) {
  color: #1a1a1a;
}

/* 分析面板 */
.analysis-content {
  flex: 1;
  overflow-y: auto;
}

.tab-content {
  padding: 16px;
}

.empty-hint {
  text-align: center;
  padding: 40px 20px;
  color: #999;
}

.empty-hint p {
  margin-top: 12px;
  font-size: 13px;
}

.empty-state {
  text-align: center;
  padding: 40px 20px;
  color: #999;
}

.empty-state p {
  margin: 12px 0;
}

.empty-state-full {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: #999;
}

.empty-state-full h3 {
  margin: 16px 0 8px;
  color: #666;
}

.empty-state-full p {
  font-size: 13px;
}

/* 首页生成 */
.fp-field {
  display: flex;
  padding: 8px 0;
  border-bottom: 1px solid #f5f5f5;
  align-items: baseline;
}

.fp-label {
  width: 100px;
  flex-shrink: 0;
  font-size: 13px;
  color: #888;
}

.fp-value {
  flex: 1;
  font-size: 13px;
  color: #1a1a1a;
  display: flex;
  align-items: center;
  gap: 8px;
}

.fp-confidence {
  font-size: 11px;
  padding: 1px 6px;
  border-radius: 10px;
  font-weight: 500;
}

.fp-confidence.high {
  background: #f6ffed;
  color: #52c41a;
}

.fp-confidence.mid {
  background: #fffbe6;
  color: #faad14;
}

.fp-confidence.low {
  background: #fff2f0;
  color: #ff4d4f;
}

/* 质控结果 */
.qc-summary {
  display: flex;
  gap: 12px;
  margin-bottom: 16px;
  padding: 12px;
  background: #fafafa;
  border-radius: 8px;
}

.qc-stat {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 13px;
  font-weight: 500;
}

.qc-stat.pass {
  color: #52c41a;
}
.qc-stat.fail {
  color: #ff4d4f;
}
.qc-stat.score {
  color: #888;
  margin-left: auto;
}

.qc-rule-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  width: 100%;
  padding-right: 8px;
}

.qc-detail {
  font-size: 13px;
  color: #666;
  margin: 0;
}

.qc-meta {
  margin-top: 8px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.qc-deduction {
  font-size: 12px;
  color: #ff4d4f;
  font-weight: 500;
}

/* ICD */
.icd-stats {
  margin-bottom: 12px;
  display: flex;
  gap: 8px;
}

.icd-match-info {
  font-size: 12px;
  color: #999;
  margin-bottom: 8px;
}

.icd-results {
  max-height: calc(100vh - 400px);
  overflow-y: auto;
}

.icd-item {
  display: flex;
  align-items: baseline;
  padding: 6px 0;
  border-bottom: 1px solid #f5f5f5;
  gap: 8px;
}

.icd-code {
  font-family: 'Cascadia Code', 'Consolas', monospace;
  font-weight: 600;
  color: #1677ff;
  white-space: nowrap;
  font-size: 12px;
}

.icd-name {
  font-size: 13px;
  color: #333;
}

/* DRG */
.drg-result {
  margin-top: 8px;
}
</style>
