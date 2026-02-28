<template>
  <div class="workstation-container">
    <!-- 顶部工具栏 -->
    <div class="workstation-toolbar">
      <div class="toolbar-left">
        <a-input-search
          v-model:value="searchText"
          placeholder="搜索患者姓名、住院号、病案号..."
          style="width: 320px"
          @search="onSearch"
        >
          <template #prefix>
            <SearchOutlined />
          </template>
        </a-input-search>
        <a-select
          v-model:value="selectedDept"
          placeholder="选择科室"
          style="width: 160px; margin-left: 12px"
          allowClear
        >
          <a-select-option value="all">全部科室</a-select-option>
          <a-select-option value="neike">内科</a-select-option>
          <a-select-option value="waike">外科</a-select-option>
          <a-select-option value="fuke">妇科</a-select-option>
          <a-select-option value="erke">儿科</a-select-option>
        </a-select>
      </div>
      <div class="toolbar-right">
        <a-button @click="showDataImport = true">
          <UploadOutlined />
          导入病历数据
        </a-button>
      </div>
    </div>

    <!-- 三栏布局主体 -->
    <div class="workstation-body">
      <!-- 左侧：病历列表 -->
      <div class="panel panel-left" :style="{ width: leftPanelWidth + 'px' }">
        <div class="panel-header">
          <span class="panel-title">病历列表</span>
          <a-badge :count="recordList.length" :number-style="{ backgroundColor: '#1677ff' }" />
        </div>
        <div class="record-list">
          <div
            v-for="record in recordList"
            :key="record.visitId"
            class="record-item"
            :class="{ active: selectedRecord?.visitId === record.visitId }"
            @click="selectRecord(record)"
          >
            <div class="record-item-header">
              <span class="patient-name">{{ record.name }}</span>
              <a-tag :color="record.status === 'completed' ? 'green' : 'blue'" size="small">
                {{ record.status === 'completed' ? '已质控' : '待质控' }}
              </a-tag>
            </div>
            <div class="record-item-meta">
              <span>{{ record.deptName }} · {{ record.inpatNo }}</span>
            </div>
            <div class="record-item-date">
              入院：{{ record.admissionDate }}
            </div>
          </div>
          <!-- 空状态 -->
          <div v-if="recordList.length === 0" class="empty-state">
            <InboxOutlined style="font-size: 48px; color: #d9d9d9" />
            <p>暂无病历数据</p>
            <a-button type="primary" size="small" @click="showDataImport = true">
              导入数据
            </a-button>
          </div>
        </div>
      </div>

      <!-- 可拖动分隔条 -->
      <div class="divider" @mousedown="startResize('left', $event)"></div>

      <!-- 中间：病历文书内容 -->
      <div class="panel panel-center">
        <template v-if="selectedRecord">
          <div class="panel-header">
            <a-segmented v-model:value="activeDocTab" :options="docTabs" />
          </div>
          <div class="document-content">
            <div v-if="activeDocTab === 'admission'" class="doc-text" v-html="selectedRecord.admissionNote || '<p class=\'placeholder\'>暂无入院记录</p>'" />
            <div v-else-if="activeDocTab === 'discharge'" class="doc-text" v-html="selectedRecord.dischargeNote || '<p class=\'placeholder\'>暂无出院记录</p>'" />
            <div v-else-if="activeDocTab === 'progress'" class="doc-text" v-html="selectedRecord.progressNote || '<p class=\'placeholder\'>暂无病程记录</p>'" />
            <div v-else-if="activeDocTab === 'surgery'" class="doc-text" v-html="selectedRecord.surgeryNote || '<p class=\'placeholder\'>暂无手术记录</p>'" />
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
      <div class="divider" @mousedown="startResize('right', $event)"></div>

      <!-- 右侧：质控/分析面板 -->
      <div class="panel panel-right" :style="{ width: rightPanelWidth + 'px' }">
        <div class="panel-header">
          <a-segmented v-model:value="activeAnalysisTab" :options="analysisTabs" />
        </div>
        <div class="analysis-content">
          <!-- Tab1: 首页生成 -->
          <div v-if="activeAnalysisTab === 'frontpage'" class="tab-content">
            <div v-if="!selectedRecord" class="empty-hint">
              <FileTextOutlined style="font-size: 32px; color: #d9d9d9" />
              <p>选择病历后自动生成首页</p>
            </div>
            <div v-else class="frontpage-panel">
              <a-button type="primary" block :loading="generating" @click="generateFrontPage">
                <ThunderboltOutlined />
                AI 生成病案首页
              </a-button>
              <div v-if="frontPageData" class="frontpage-result">
                <a-descriptions bordered size="small" :column="1" style="margin-top: 16px">
                  <a-descriptions-item label="患者姓名">{{ frontPageData.name || '-' }}</a-descriptions-item>
                  <a-descriptions-item label="性别">{{ frontPageData.sex || '-' }}</a-descriptions-item>
                  <a-descriptions-item label="年龄">{{ frontPageData.age || '-' }}</a-descriptions-item>
                  <a-descriptions-item label="入院日期">{{ frontPageData.admissionDate || '-' }}</a-descriptions-item>
                  <a-descriptions-item label="出院日期">{{ frontPageData.dischargeDate || '-' }}</a-descriptions-item>
                  <a-descriptions-item label="主诊断">{{ frontPageData.mainDiagnosis || '-' }}</a-descriptions-item>
                  <a-descriptions-item label="主手术">{{ frontPageData.mainSurgery || '-' }}</a-descriptions-item>
                </a-descriptions>
              </div>
            </div>
          </div>

          <!-- Tab2: 质控结果 -->
          <div v-if="activeAnalysisTab === 'qc'" class="tab-content">
            <div v-if="!selectedRecord" class="empty-hint">
              <CheckCircleOutlined style="font-size: 32px; color: #d9d9d9" />
              <p>选择病历后运行质控</p>
            </div>
            <div v-else>
              <a-button type="primary" block @click="runQualityControl">
                <SafetyCertificateOutlined />
                运行质控检查
              </a-button>
              <div v-if="qcResults.length > 0" class="qc-results" style="margin-top: 16px">
                <a-collapse>
                  <a-collapse-panel
                    v-for="(result, index) in qcResults"
                    :key="index"
                    :header="result.ruleName"
                  >
                    <template #extra>
                      <a-tag :color="result.passed ? 'green' : 'red'" size="small">
                        {{ result.passed ? '通过' : '不通过' }}
                      </a-tag>
                    </template>
                    <p>{{ result.detail }}</p>
                  </a-collapse-panel>
                </a-collapse>
              </div>
            </div>
          </div>

          <!-- Tab3: ICD编码 -->
          <div v-if="activeAnalysisTab === 'icd'" class="tab-content">
            <div v-if="icdStats" class="icd-stats">
              <a-tag color="blue">ICD-10: {{ icdStats.icd10_count?.toLocaleString() }} 条</a-tag>
              <a-tag color="green">ICD-9-CM-3: {{ icdStats.icd9cm3_count?.toLocaleString() }} 条</a-tag>
            </div>
            <div style="display: flex; gap: 8px; margin-bottom: 12px">
              <a-input-search
                v-model:value="icdSearchText"
                placeholder="搜索疾病名称、编码、拼音首字母..."
                @search="searchICD"
                :loading="icdLoading"
                style="flex: 1"
              />
              <a-select v-model:value="icdCodeType" style="width: 130px" @change="() => icdSearchText && searchICD(icdSearchText)">
                <a-select-option value="all">全部</a-select-option>
                <a-select-option value="icd10">ICD-10</a-select-option>
                <a-select-option value="icd9cm3">ICD-9-CM-3</a-select-option>
              </a-select>
            </div>
            <div v-if="icdTotal > 0" class="icd-match-info">
              找到 {{ icdTotal }} 条匹配（显示前 {{ icdResults.length }} 条）
            </div>
            <a-spin :spinning="icdLoading">
              <div v-if="icdResults.length > 0" class="icd-results">
                <div v-for="item in icdResults" :key="item.code + item.type" class="icd-item">
                  <a-tag :color="item.type === 'icd10' ? 'blue' : 'green'" size="small" style="flex-shrink: 0">
                    {{ item.type === 'icd10' ? '诊断' : '手术' }}
                  </a-tag>
                  <span class="icd-code">{{ item.code }}</span>
                  <span class="icd-name">{{ item.name }}</span>
                </div>
              </div>
              <div v-else-if="icdSearchText && !icdLoading" class="empty-hint">
                <p>未找到匹配的编码</p>
              </div>
            </a-spin>
          </div>

          <!-- Tab4: DRG分组 -->
          <div v-if="activeAnalysisTab === 'drg'" class="tab-content">
            <div v-if="!selectedRecord" class="empty-hint">
              <ClusterOutlined style="font-size: 32px; color: #d9d9d9" />
              <p>选择病历后进行 DRG 入组</p>
            </div>
            <div v-else>
              <a-button type="primary" block @click="runDRGGrouping">
                <ClusterOutlined />
                DRG 预入组
              </a-button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 数据导入弹窗 -->
    <a-modal
      v-model:open="showDataImport"
      title="导入病历数据"
      :footer="null"
      width="600px"
    >
      <a-upload-dragger
        name="file"
        accept=".xlsx,.xls,.csv"
        :before-upload="handleFileUpload"
      >
        <p class="ant-upload-drag-icon">
          <InboxOutlined />
        </p>
        <p class="ant-upload-text">点击或拖拽文件上传</p>
        <p class="ant-upload-hint">支持 Excel (.xlsx/.xls) 和 CSV 格式</p>
      </a-upload-dragger>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
/**
 * WorkstationView.vue - 病案智能质控工作站
 *
 * 统一工作站，整合首页自动生成、质控分析、ICD编码查询、DRG分组等功能。
 * 三栏布局：左侧病历列表 | 中间文书内容 | 右侧质控/分析面板
 */
import { ref, reactive } from 'vue'
import {
  SearchOutlined,
  UploadOutlined,
  InboxOutlined,
  FileSearchOutlined,
  FileTextOutlined,
  ThunderboltOutlined,
  CheckCircleOutlined,
  SafetyCertificateOutlined,
  ClusterOutlined,
} from '@ant-design/icons-vue'

// ==================== 状态 ====================

// 搜索和筛选
const searchText = ref('')
const selectedDept = ref<string | undefined>(undefined)

// 面板宽度
const leftPanelWidth = ref(280)
const rightPanelWidth = ref(400)

// 当前选中
const selectedRecord = ref<any>(null)

// 文书 Tab
const activeDocTab = ref('admission')
const docTabs = ['admission', 'discharge', 'progress', 'surgery'].map(key => ({
  label: { admission: '入院记录', discharge: '出院记录', progress: '病程记录', surgery: '手术记录' }[key],
  value: key,
}))

// 分析 Tab
const activeAnalysisTab = ref('frontpage')
const analysisTabs = ['frontpage', 'qc', 'icd', 'drg'].map(key => ({
  label: { frontpage: '首页', qc: '质控', icd: 'ICD', drg: 'DRG' }[key],
  value: key,
}))

// 数据导入
const showDataImport = ref(false)

// 首页生成
const generating = ref(false)
const frontPageData = ref<any>(null)

// 质控结果
const qcResults = ref<any[]>([])

// ICD 编码查询
const icdSearchText = ref('')
const icdResults = ref<any[]>([])
const icdLoading = ref(false)
const icdTotal = ref(0)
const icdCodeType = ref('all')
const icdStats = ref<any>(null)

// 病历列表（后续由 API 填充）
const recordList = ref<any[]>([])

// ==================== 方法 ====================

// 获取 API 基础 URL
function getApiBaseUrl(): string {
  // 开发环境直接连后端
  return import.meta.env.VITE_API_BASE_URL || '/api/v1'
}

function onSearch(value: string) {
  console.log('搜索:', value)
  // TODO: 调用后端搜索 API
}

function selectRecord(record: any) {
  selectedRecord.value = record
  frontPageData.value = null
  qcResults.value = []
}

async function generateFrontPage() {
  generating.value = true
  try {
    // TODO: 调用 frontpage_extraction API
    await new Promise(resolve => setTimeout(resolve, 1000))
    frontPageData.value = {
      name: selectedRecord.value?.name || '',
      sex: selectedRecord.value?.sex || '',
      age: selectedRecord.value?.age || '',
      admissionDate: selectedRecord.value?.admissionDate || '',
      dischargeDate: selectedRecord.value?.dischargeDate || '',
      mainDiagnosis: '待 AI 提取',
      mainSurgery: '待 AI 提取',
    }
  } finally {
    generating.value = false
  }
}

async function runQualityControl() {
  // TODO: 调用质控引擎 API
  qcResults.value = [
    { ruleName: '示例：首页必填项检查', passed: true, detail: '所有必填项已填写完整' },
    { ruleName: '示例：入院日期逻辑校验', passed: true, detail: '入院日期早于出院日期，逻辑正确' },
  ]
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

// 加载 ICD 编码库统计
async function loadIcdStats() {
  try {
    const res = await fetch(`${getApiBaseUrl()}/icd/stats`)
    const json = await res.json()
    if (json.success) {
      icdStats.value = json.data
    }
  } catch (err) {
    console.error('加载 ICD 统计失败:', err)
  }
}

// 页面加载时获取统计信息
loadIcdStats()

async function runDRGGrouping() {
  // TODO: 调用 DRG 分组 API
}

// 面板拖拽调整大小
function startResize(side: 'left' | 'right', event: MouseEvent) {
  const startX = event.clientX
  const startWidth = side === 'left' ? leftPanelWidth.value : rightPanelWidth.value

  const onMouseMove = (e: MouseEvent) => {
    const diff = e.clientX - startX
    if (side === 'left') {
      leftPanelWidth.value = Math.max(200, Math.min(500, startWidth + diff))
    } else {
      rightPanelWidth.value = Math.max(300, Math.min(600, startWidth - diff))
    }
  }

  const onMouseUp = () => {
    document.removeEventListener('mousemove', onMouseMove)
    document.removeEventListener('mouseup', onMouseUp)
  }

  document.addEventListener('mousemove', onMouseMove)
  document.addEventListener('mouseup', onMouseUp)
}

function handleFileUpload(file: File) {
  console.log('上传文件:', file.name)
  // TODO: 调用后端数据导入 API
  return false // 阻止自动上传
}
</script>

<style scoped>
.workstation-container {
  display: flex;
  flex-direction: column;
  height: calc(100vh - 64px); /* 减去顶部导航栏高度 */
  background: #f5f5f5;
}

.workstation-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  background: #fff;
  border-bottom: 1px solid #e8e8e8;
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
  min-width: 200px;
  max-width: 500px;
  border-right: 1px solid #e8e8e8;
}

.panel-center {
  flex: 1;
  min-width: 300px;
}

.panel-right {
  min-width: 300px;
  max-width: 600px;
  border-left: 1px solid #e8e8e8;
}

.panel-header {
  padding: 12px 16px;
  border-bottom: 1px solid #f0f0f0;
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
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
}

.divider:hover {
  background: #1677ff;
}

/* 病历列表 */
.record-list {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
}

.record-item {
  padding: 10px 12px;
  border-radius: 8px;
  cursor: pointer;
  margin-bottom: 4px;
  transition: all 0.2s;
  border: 1px solid transparent;
}

.record-item:hover {
  background: #f5f5ff;
  border-color: #e8e8ff;
}

.record-item.active {
  background: #e6f4ff;
  border-color: #91caff;
}

.record-item-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 4px;
}

.patient-name {
  font-weight: 600;
  font-size: 14px;
  color: #1a1a1a;
}

.record-item-meta {
  font-size: 12px;
  color: #666;
}

.record-item-date {
  font-size: 12px;
  color: #999;
  margin-top: 2px;
}

/* 文书内容 */
.document-content {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
}

.doc-text {
  font-size: 14px;
  line-height: 1.8;
  color: #333;
}

.doc-text :deep(.placeholder) {
  color: #999;
  text-align: center;
  padding: 40px;
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

/* 空状态 */
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

/* ICD 搜索结果 */
.icd-results {
  max-height: 400px;
  overflow-y: auto;
}

.icd-item {
  display: flex;
  align-items: baseline;
  padding: 8px 0;
  border-bottom: 1px solid #f5f5f5;
  gap: 12px;
}

.icd-code {
  font-family: monospace;
  font-weight: 600;
  color: #1677ff;
  white-space: nowrap;
}

.icd-name {
  font-size: 13px;
  color: #333;
}

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

/* 首页结果 */
.frontpage-result {
  margin-top: 16px;
}
</style>
