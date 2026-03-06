<template>
  <div class="h-full flex bg-white dark:bg-slate-900 overflow-hidden">
    <!-- ====== 列表模式 ====== -->
    <template v-if="viewMode === 'list'">
      <!-- 左侧科室导航 -->
      <aside class="w-56 flex-shrink-0 border-r border-slate-200 dark:border-slate-800 flex flex-col bg-slate-50 dark:bg-slate-900">
        <div class="h-14 flex items-center gap-2 px-5 border-b border-slate-200 dark:border-slate-800 flex-shrink-0">
          <MedicineBoxOutlined class="text-blue-500 text-lg" />
          <span class="font-bold text-slate-800 dark:text-slate-100 text-base tracking-tight">病案工作台</span>
        </div>
        <div class="flex-1 overflow-y-auto py-2 custom-scrollbar">
          <div
            v-for="dept in departments"
            :key="dept.name"
            @click="selectDept(dept.name)"
            :class="[
              'mx-2 mb-0.5 flex items-center justify-between px-3 py-2.5 rounded-lg cursor-pointer text-sm transition-all duration-150',
              activeDept === dept.name
                ? 'bg-blue-50 text-blue-700 font-semibold dark:bg-blue-900/30 dark:text-blue-300 shadow-sm'
                : 'text-slate-600 hover:bg-slate-100 dark:text-slate-400 dark:hover:bg-slate-800'
            ]"
          >
            <span class="truncate">{{ dept.name }}</span>
            <div class="flex items-center gap-1.5">
              <span
                v-if="dept.warningCount > 0"
                class="min-w-[18px] h-[18px] flex items-center justify-center rounded-full bg-red-100 text-red-600 text-[10px] font-bold px-1 dark:bg-red-900/30 dark:text-red-400"
              >{{ dept.warningCount }}</span>
              <span
                class="min-w-[18px] h-[18px] flex items-center justify-center rounded-full bg-slate-200 text-slate-500 text-[10px] font-bold px-1 dark:bg-slate-700 dark:text-slate-400"
              >{{ dept.total }}</span>
            </div>
          </div>
        </div>
        <div class="border-t border-slate-200 dark:border-slate-800 px-5 py-3 flex-shrink-0">
          <div class="text-[11px] text-slate-400 mb-1">本周出院总计</div>
          <div class="text-2xl font-black text-slate-800 dark:text-white">{{ totalCount }}</div>
        </div>
      </aside>

      <!-- 右侧主内容 -->
      <main class="flex-1 flex flex-col min-w-0">
        <header class="h-14 flex items-center justify-between px-6 border-b border-slate-200 dark:border-slate-800 flex-shrink-0 bg-white dark:bg-slate-900">
          <div class="flex items-center gap-4">
            <h2 class="text-lg font-bold text-slate-800 dark:text-white">{{ activeDept }}</h2>
            <span class="text-xs text-slate-400 bg-slate-100 dark:bg-slate-800 px-2 py-0.5 rounded-full">
              {{ filteredRecords.length }} 例
            </span>
          </div>
          <div class="flex items-center gap-3">
            <a-input-search
              v-model:value="searchText"
              placeholder="搜索姓名/病案号"
              style="width: 200px"
              size="small"
              allow-clear
            />
            <a-select
              v-model:value="statusFilter"
              style="width: 110px"
              size="small"
              :options="statusOptions"
            />
            <a-button size="small" @click="refreshData" :loading="loading">
              <template #icon><SyncOutlined /></template>
            </a-button>
          </div>
        </header>

        <!-- 状态统计条 -->
        <div class="h-10 flex items-center gap-6 px-6 border-b border-slate-100 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-900/50 flex-shrink-0">
          <div class="flex items-center gap-1.5 text-xs">
            <span class="w-2 h-2 rounded-full bg-emerald-500"></span>
            <span class="text-slate-500">已完成</span>
            <span class="font-bold text-slate-700 dark:text-slate-300">{{ statusCounts.completed }}</span>
          </div>
          <div class="flex items-center gap-1.5 text-xs">
            <span class="w-2 h-2 rounded-full bg-amber-500"></span>
            <span class="text-slate-500">有缺陷</span>
            <span class="font-bold text-slate-700 dark:text-slate-300">{{ statusCounts.warning }}</span>
          </div>
          <div class="flex items-center gap-1.5 text-xs">
            <span class="w-2 h-2 rounded-full bg-blue-500"></span>
            <span class="text-slate-500">处理中</span>
            <span class="font-bold text-slate-700 dark:text-slate-300">{{ statusCounts.processing }}</span>
          </div>
          <div class="flex items-center gap-1.5 text-xs">
            <span class="w-2 h-2 rounded-full bg-slate-300"></span>
            <span class="text-slate-500">待处理</span>
            <span class="font-bold text-slate-700 dark:text-slate-300">{{ statusCounts.pending }}</span>
          </div>
          <div class="ml-auto text-[11px] text-slate-400">
            完成率
            <span class="ml-1 font-bold text-emerald-600 dark:text-emerald-400">{{ completionRate }}%</span>
          </div>
        </div>

        <!-- 病历卡片网格 -->
        <div class="flex-1 overflow-y-auto p-5 custom-scrollbar">
          <div v-if="filteredRecords.length === 0" class="flex flex-col items-center justify-center h-full text-slate-400">
            <InboxOutlined class="text-4xl mb-3" />
            <div class="text-sm">暂无病历记录</div>
          </div>
          <div v-else class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 2xl:grid-cols-5 gap-3">
            <div
              v-for="record in filteredRecords"
              :key="record.id"
              @click="openRecord(record)"
              class="bg-white dark:bg-slate-800 rounded-xl shadow-[0_1px_8px_rgba(0,0,0,0.05)] hover:shadow-[0_6px_20px_rgba(0,0,0,0.1)] cursor-pointer transition-all duration-200 border border-slate-200 dark:border-slate-700/80 group overflow-hidden"
            >
              <div class="p-3.5 flex flex-col h-full">
                <div class="flex items-start justify-between mb-2">
                  <div class="flex items-baseline gap-2">
                    <span class="font-black text-slate-800 dark:text-slate-100 text-xl tracking-tighter leading-none">
                      {{ record.bedNo }}<span class="text-xs font-bold text-slate-500 ml-0.5">床</span>
                    </span>
                    <span class="font-extrabold text-slate-800 dark:text-slate-200 text-base tracking-wide ml-1 leading-none">
                      {{ record.name }}
                    </span>
                  </div>
                </div>
                <div class="flex items-center gap-2 mb-2.5 text-[11px] font-medium text-slate-500 dark:text-slate-400">
                  <span>{{ record.sex }}/{{ record.age }}岁</span>
                  <span class="bg-slate-50 dark:bg-slate-700/50 text-slate-400 dark:text-slate-500 px-1.5 py-[1px] rounded border border-slate-100 dark:border-slate-600/50">
                    {{ record.insurance }}
                  </span>
                </div>
                <div class="bg-slate-50/80 dark:bg-slate-800/40 rounded p-2 mb-1.5 flex flex-col justify-center border border-slate-50 dark:border-slate-700/30">
                  <div class="flex justify-between items-center text-[10px] text-slate-400 dark:text-slate-500 mb-1">
                    <span>入院: <span class="text-slate-600 dark:text-slate-300 font-mono ml-1">{{ record.admissionDate }}</span></span>
                    <div :class="[
                      'font-bold text-[11px]',
                      record.days > 14 ? 'text-red-500' : record.days > 7 ? 'text-amber-500' : 'text-slate-700 dark:text-slate-200'
                    ]">{{ record.days }} 天</div>
                  </div>
                  <div class="flex items-center text-[10px] text-slate-400 dark:text-slate-500">
                    <span>出院: <span class="text-slate-600 dark:text-slate-300 font-mono ml-1">{{ record.dischargeDate }}</span></span>
                  </div>
                </div>
                <div class="bg-slate-50/80 dark:bg-slate-800/40 rounded p-2 text-[10px] text-slate-500 dark:text-slate-400 flex items-center h-[26px] overflow-hidden mb-3.5 border border-slate-50 dark:border-slate-700/30">
                  <span class="shrink-0 mr-1.5 font-medium text-slate-400">诊断:</span>
                  <span class="truncate font-medium text-slate-600 dark:text-slate-300" :title="record.diagnosis">{{ record.diagnosis }}</span>
                </div>
                <div class="mt-auto flex items-center">
                  <span
                    v-if="record.status === 'completed'"
                    class="inline-flex items-center gap-1.5 text-[#10b981] bg-[#ecfdf5] border border-[#d1fae5] dark:bg-[#10b981]/10 dark:border-[#10b981]/20 px-2 py-0.5 rounded text-[10px] font-bold"
                  >
                    <CheckCircleOutlined /> 提取完成
                  </span>
                  <span
                    v-else-if="record.status === 'warning'"
                    class="inline-flex items-center gap-1.5 text-[#f59e0b] bg-[#fffbeb] border border-[#fef3c7] dark:bg-[#f59e0b]/10 dark:border-[#f59e0b]/20 px-2 py-0.5 rounded text-[10px] font-bold"
                  >
                    <WarningOutlined /> 存在缺陷
                  </span>
                  <span
                    v-else-if="record.status === 'processing'"
                    class="inline-flex items-center gap-1.5 text-[#3b82f6] bg-[#eff6ff] border border-[#dbeafe] dark:bg-[#3b82f6]/10 dark:border-[#3b82f6]/20 px-2 py-0.5 rounded text-[10px] font-bold"
                  >
                    <SyncOutlined spin /> AI 提取中
                  </span>
                  <span
                    v-else
                    class="inline-flex items-center gap-1.5 text-slate-400 bg-slate-50 border border-slate-100 dark:bg-slate-800 dark:border-slate-700/80 px-2 py-0.5 rounded text-[10px] font-bold group-hover:bg-white transition-colors"
                  >
                    <InboxOutlined /> 待发提取
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </main>
    </template>

    <!-- ====== 详情模式（全屏） ====== -->
    <template v-else>
      <div class="flex-1 flex flex-col min-w-0 h-full">
        <!-- 详情顶部栏 -->
        <header class="h-14 flex items-center justify-between px-6 border-b border-slate-200 dark:border-slate-800 flex-shrink-0 bg-white dark:bg-slate-900">
          <div class="flex items-center gap-4">
            <button
              @click="goBackToList"
              class="flex items-center gap-2 text-slate-500 hover:text-blue-600 transition-colors text-sm font-medium"
            >
              <LeftOutlined />
              <span>返回列表</span>
            </button>
            <div class="w-px h-6 bg-slate-200 dark:bg-slate-700"></div>
            <div v-if="selectedRecord" class="flex items-center gap-3">
              <div class="w-9 h-9 rounded-full bg-blue-500 flex items-center justify-center text-white font-bold text-base">
                {{ selectedRecord.name.charAt(0) }}
              </div>
              <div>
                <div class="font-bold text-slate-800 dark:text-white text-base leading-tight">{{ selectedRecord.name }}</div>
                <div class="text-[11px] text-slate-400 font-mono">{{ selectedRecord.id }}</div>
              </div>
              <span class="text-xs text-slate-400 bg-slate-100 dark:bg-slate-800 px-2 py-0.5 rounded-full ml-2">
                {{ selectedRecord.department }}
              </span>
            </div>
          </div>
          <div class="flex items-center gap-3">
            <a-button
              type="primary"
              :loading="frontpageGenerating"
              @click="generateFrontpage"
              class="!rounded-lg"
            >
              <template #icon><ThunderboltOutlined /></template>
              {{ frontpageDraft ? '重新生成' : 'AI 生成首页' }}
            </a-button>
          </div>
        </header>

        <!-- 详情主体：左右分栏 -->
        <div class="flex-1 flex overflow-hidden">
          <!-- 左侧：患者信息 (35%) -->
          <aside class="w-[35%] min-w-[320px] max-w-[480px] border-r border-slate-200 dark:border-slate-800 overflow-y-auto custom-scrollbar bg-slate-50/30 dark:bg-slate-900/50">
            <div v-if="selectedRecord" class="p-6">
              <!-- 基本信息卡片 -->
              <h4 class="text-xs font-bold text-slate-400 uppercase tracking-wider mb-3 flex items-center gap-2">
                <UserOutlined class="text-blue-500" />
                患者信息
              </h4>
              <div class="grid grid-cols-2 gap-3 mb-6">
                <div v-for="item in detailItems" :key="item.label" class="bg-white dark:bg-slate-800 rounded-lg p-3 border border-slate-100 dark:border-slate-700/50">
                  <div class="text-[10px] text-slate-400 uppercase tracking-wider mb-1">{{ item.label }}</div>
                  <div class="text-sm font-semibold text-slate-700 dark:text-slate-200">{{ item.value }}</div>
                </div>
              </div>

              <!-- 诊断信息 -->
              <h4 class="text-xs font-bold text-slate-400 uppercase tracking-wider mb-3 flex items-center gap-2">
                <FileTextOutlined class="text-blue-500" />
                诊断信息
              </h4>
              <div class="bg-white dark:bg-slate-800 rounded-lg p-4 border border-slate-100 dark:border-slate-700/50 mb-6">
                <div class="flex items-center gap-2 mb-2">
                  <span class="text-[10px] text-blue-600 bg-blue-100 px-1.5 py-0.5 rounded font-bold">主诊断</span>
                  <span class="text-sm text-slate-800 dark:text-slate-200 font-medium">{{ selectedRecord.diagnosis }}</span>
                </div>
                <div v-if="selectedRecord.diagnosisCode" class="text-xs text-slate-400 font-mono">
                  ICD-10: {{ selectedRecord.diagnosisCode }}
                </div>
              </div>

              <!-- 病历文书预览 -->
              <h4 class="text-xs font-bold text-slate-400 uppercase tracking-wider mb-3 flex items-center gap-2">
                <FileSearchOutlined class="text-blue-500" />
                病历文书
                <span v-if="documentsLoading" class="ml-auto"><SyncOutlined spin class="text-blue-400 text-xs" /></span>
              </h4>
              <div class="space-y-2">
                <div
                  v-for="doc in documentsList"
                  :key="doc.type + doc.label"
                  class="bg-white dark:bg-slate-800 rounded-lg px-4 py-3 border text-sm flex items-center justify-between transition-all duration-150"
                  :class="doc.has_content
                    ? 'border-slate-100 dark:border-slate-700/50 text-slate-600 dark:text-slate-300 cursor-pointer hover:border-blue-300 hover:bg-blue-50/30 dark:hover:bg-blue-950/20'
                    : 'border-slate-50 dark:border-slate-800 text-slate-300 dark:text-slate-600'"
                  @click="doc.has_content && openDocPreview(doc)"
                >
                  <span class="flex items-center gap-2">
                    <FileTextOutlined :class="doc.has_content ? 'text-blue-400' : 'text-slate-200'" />
                    {{ doc.label }}
                  </span>
                  <span v-if="doc.has_content" class="flex items-center gap-1.5">
                    <span class="text-[10px] text-green-500">{{ doc.length }}字</span>
                    <EyeOutlined class="text-blue-400 text-xs" />
                  </span>
                  <span v-else class="text-[10px] text-slate-300">—</span>
                </div>
                <div v-if="!documentsLoading && documentsList.length === 0" class="text-xs text-slate-400 text-center py-3">
                  暂无病历文书
                </div>
              </div>

              <!-- 文书预览抽屉 -->
              <a-drawer
                v-model:open="docDrawerVisible"
                :title="docDrawerTitle"
                placement="right"
                :width="600"
                :headerStyle="{ borderBottom: '1px solid #e2e8f0' }"
                :bodyStyle="{ padding: '20px', backgroundColor: '#fafbfc' }"
              >
                <div class="bg-white rounded-lg border border-slate-200 p-5 shadow-sm">
                  <pre class="whitespace-pre-wrap font-sans text-sm text-slate-700 leading-7 m-0">{{ docDrawerContent }}</pre>
                </div>
              </a-drawer>
            </div>
          </aside>

          <!-- 右侧：AI 首页生成 (65%) -->
          <main class="flex-1 overflow-y-auto custom-scrollbar bg-white dark:bg-slate-900">
            <div class="p-6">
              <!-- 生成中进度 -->
              <div v-if="frontpageGenerating" class="flex flex-col items-center justify-center py-20">
                <a-spin size="large" />
                <div class="text-sm text-slate-400 mt-4">正在从病历中提取首页信息...</div>
                <div v-if="frontpageModule" class="text-xs text-blue-500 mt-2">当前模块: {{ frontpageModule }}</div>
              </div>

              <!-- 生成结果 Tabs -->
              <div v-else-if="frontpageDraft">
                <a-tabs v-model:activeKey="frontpageTab" size="small">
                  <a-tab-pane key="fields" tab="提取结果">
                    <FrontPagePanel
                      :fields="frontpageFields"
                      :generating="frontpageGenerating"
                      @generate="generateFrontpage"
                    />
                  </a-tab-pane>
                  <a-tab-pane key="preview" tab="首页预览/打印">
                    <HmFrontpagePreview :draft="frontpageDraft" />
                  </a-tab-pane>
                </a-tabs>
              </div>

              <!-- 未生成状态 -->
              <div v-else class="flex flex-col items-center justify-center py-20 text-slate-300">
                <div class="w-20 h-20 rounded-full bg-slate-50 dark:bg-slate-800 flex items-center justify-center mb-4 border-2 border-dashed border-slate-200 dark:border-slate-700">
                  <FileTextOutlined class="text-3xl" />
                </div>
                <div class="text-sm font-medium mb-1">尚未生成病案首页</div>
                <div class="text-xs text-slate-400">点击右上角「AI 生成首页」按钮开始</div>
              </div>
            </div>
          </main>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import axios from 'axios'
import { message } from 'ant-design-vue'
import {
  MedicineBoxOutlined,
  SyncOutlined,
  CheckCircleOutlined,
  WarningOutlined,
  InboxOutlined,
  CloseOutlined,
  FileTextOutlined,
  ThunderboltOutlined,
  LeftOutlined,
  UserOutlined,
  FileSearchOutlined,
  EyeOutlined,
} from '@ant-design/icons-vue'
import FrontPagePanel from '@/views/workstation/FrontPagePanel.vue'
import HmFrontpagePreview from '@/components/frontpage/HmFrontpagePreview.vue'

// ========== 类型 ==========
interface PatientRecord {
  id: string
  bedNo: string
  name: string
  sex: string
  age: number
  insurance: string
  department: string
  admissionDate: string
  dischargeDate: string
  days: number
  diagnosis: string
  diagnosisCode: string
  doctor: string
  status: 'pending' | 'processing' | 'completed' | 'warning'
}

interface DeptInfo {
  name: string
  total: number
  warningCount: number
}

// ========== 视图模式 ==========
const viewMode = ref<'list' | 'detail'>('list')

// ========== 数据（从 API 加载） ==========
const allRecords = ref<PatientRecord[]>([])
const departments = ref<DeptInfo[]>([])
const totalCount = computed(() => allRecords.value.length)

// ========== 筛选状态 ==========
const activeDept = ref('全部科室')
const searchText = ref('')
const statusFilter = ref('all')
const loading = ref(false)
const selectedId = ref<string | null>(null)

// ========== 首页生成状态 ==========
const frontpageGenerating = ref(false)
const frontpageDraft = ref<any>(null)
const frontpageModule = ref('')
const frontpageTab = ref('fields')

// ========== 病历文书预览 ==========
interface DocItem {
  type: string
  label: string
  has_content: boolean
  content: string | null
  length: number
}
const documentsList = ref<DocItem[]>([])
const documentsLoading = ref(false)
const docDrawerVisible = ref(false)
const docDrawerTitle = ref('')
const docDrawerContent = ref('')

async function loadDocuments(visitId: string) {
  documentsLoading.value = true
  documentsList.value = []
  try {
    const { data } = await axios.get(`/api/medical-records/documents/${visitId}`)
    // 只显示有内容的 + 前 3 个核心文书类型（即使没内容也展示）
    const coreTypes = ['admission_record', 'discharge_record', 'surgery_record']
    const docs: DocItem[] = data.documents || []
    documentsList.value = docs.filter(
      (d: DocItem) => d.has_content || coreTypes.includes(d.type)
    )
  } catch (err) {
    console.error('加载病历文书失败:', err)
  } finally {
    documentsLoading.value = false
  }
}

function openDocPreview(doc: DocItem) {
  docDrawerTitle.value = doc.label
  docDrawerContent.value = doc.content || '暂无内容'
  docDrawerVisible.value = true
}

const statusOptions = [
  { value: 'all', label: '全部状态' },
  { value: 'pending', label: '待处理' },
  { value: 'processing', label: '处理中' },
  { value: 'completed', label: '已完成' },
  { value: 'warning', label: '有缺陷' },
]

// ========== API 加载 ==========
async function fetchData() {
  loading.value = true
  try {
    const { data } = await axios.get('/api/medical-records/workstation')
    allRecords.value = data.records || []
    departments.value = data.departments || []
  } catch (err) {
    console.error('加载工作台数据失败:', err)
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  fetchData()
})

// 切换病历时清除上次生成结果 + 加载文书列表
watch(selectedId, (newId) => {
  frontpageDraft.value = null
  frontpageModule.value = ''
  frontpageTab.value = 'fields'
  frontpageGenerating.value = false
  // 加载文书列表
  docDrawerVisible.value = false
  if (newId) {
    loadDocuments(newId)
  } else {
    documentsList.value = []
  }
})

// ========== 首页生成 ==========
async function generateFrontpage() {
  if (!selectedRecord.value) return

  frontpageGenerating.value = true
  frontpageDraft.value = null
  frontpageModule.value = ''

  try {
    const response = await fetch('/api/v1/frontpage/auto-generate-draft-stream', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        visit_id: selectedId.value,
        medical_text: ''
      }),
    })

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`)
    }

    const reader = response.body?.getReader()
    const decoder = new TextDecoder()

    if (!reader) throw new Error('无法读取响应流')

    let buffer = ''
    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          try {
            const payload = JSON.parse(line.slice(6))
            if (payload.frontpage) {
              frontpageDraft.value = payload.frontpage
            }
            if (payload.module) {
              frontpageModule.value = payload.module
            }
          } catch (e) {
            // 忽略解析错误
          }
        }
      }
    }

    if (frontpageDraft.value) {
      message.success('首页生成完成')
    } else {
      message.warning('未能生成首页数据')
    }
  } catch (err: any) {
    console.error('首页生成失败:', err)
    message.error('首页生成失败: ' + (err.message || '未知错误'))
  } finally {
    frontpageGenerating.value = false
    frontpageModule.value = ''
  }
}

// 将 draft 转换为 FrontPagePanel 需要的 fields 格式
const frontpageFields = computed(() => {
  const draft = frontpageDraft.value
  if (!draft) return []

  const fields: any[] = []
  const addField = (category: string, label: string, value: any, confidence = 0.8) => {
    fields.push({ category, label, value: value ?? '', confidence })
  }

  const bi = draft.basic_info || {}
  addField('basic', '患者姓名', bi.patient_name)
  addField('basic', '性别', bi.gender_text)
  addField('basic', '年龄', bi.age_years ? `${bi.age_years}岁` : '')
  addField('basic', '出生日期', bi.birth_date)
  addField('basic', '民族', bi.ethnicity)
  addField('basic', '婚姻状况', bi.marital_status_text)
  addField('basic', '身份证号', bi.id_number)
  addField('basic', '职业', bi.occupation)
  addField('basic', '住院号', draft.hospitalization?.medical_record_no || '')

  const hosp = draft.hospitalization || {}
  addField('basic', '医疗机构名称', hosp.hospital_name)
  addField('admission', '入院日期', hosp.admission_datetime?.split(' ')[0] || '')
  addField('admission', '出院日期', hosp.discharge_datetime?.split(' ')[0] || '')
  addField('admission', '住院天数', hosp.actual_hospital_days ? String(hosp.actual_hospital_days) : '')
  addField('admission', '入院科室', hosp.admission_dept)
  addField('admission', '出院科室', hosp.discharge_dept)
  addField('admission', '床号', selectedRecord.value?.bedNo ? `${selectedRecord.value.bedNo}床` : '')

  const diag = draft.diagnoses || {}
  addField('basic', '主要诊断', diag.discharge_main_diagnosis_text)
  addField('basic', '主要诊断编码', diag.discharge_main_icd)
  addField('basic', '主要手术', draft.procedures?.main_procedure_text)
  addField('basic', '主要手术编码', draft.procedures?.main_procedure_code)

  return fields
})

// ========== 计算 ==========
const filteredRecords = computed(() => {
  let list = allRecords.value
  if (activeDept.value !== '全部科室') {
    list = list.filter(r => r.department === activeDept.value)
  }
  if (statusFilter.value !== 'all') {
    list = list.filter(r => r.status === statusFilter.value)
  }
  if (searchText.value.trim()) {
    const keyword = searchText.value.trim().toLowerCase()
    list = list.filter(r =>
      r.name.toLowerCase().includes(keyword) ||
      r.id.toLowerCase().includes(keyword)
    )
  }
  return list
})

const statusCounts = computed(() => {
  const all = activeDept.value === '全部科室'
    ? allRecords.value
    : allRecords.value.filter(r => r.department === activeDept.value)
  return {
    completed: all.filter(r => r.status === 'completed').length,
    warning: all.filter(r => r.status === 'warning').length,
    processing: all.filter(r => r.status === 'processing').length,
    pending: all.filter(r => r.status === 'pending').length,
  }
})

const completionRate = computed(() => {
  const all = activeDept.value === '全部科室'
    ? allRecords.value
    : allRecords.value.filter(r => r.department === activeDept.value)
  if (all.length === 0) return 0
  return Math.round((all.filter(r => r.status === 'completed').length / all.length) * 100)
})

const selectedRecord = computed(() =>
  allRecords.value.find(r => r.id === selectedId.value)
)

const detailItems = computed(() => {
  const r = selectedRecord.value
  if (!r) return []
  return [
    { label: '科室', value: r.department },
    { label: '床号', value: r.bedNo + '床' },
    { label: '性别/年龄', value: `${r.sex} / ${r.age}岁` },
    { label: '医保类型', value: r.insurance },
    { label: '入院日期', value: r.admissionDate },
    { label: '住院天数', value: r.days + '天' },
    { label: '主管医生', value: r.doctor },
    { label: '出院日期', value: r.dischargeDate },
    { label: '病案号', value: r.id },
  ]
})

// ========== 方法 ==========
function selectDept(name: string) {
  activeDept.value = name
}

function openRecord(record: PatientRecord) {
  selectedId.value = record.id
  viewMode.value = 'detail'
}

function goBackToList() {
  viewMode.value = 'list'
  // 不清空 selectedId，方便返回后还能看到高亮
}

function refreshData() {
  fetchData()
}
</script>

<style scoped>
.custom-scrollbar::-webkit-scrollbar { width: 5px; height: 5px; }
.custom-scrollbar::-webkit-scrollbar-track { background: transparent; }
.custom-scrollbar::-webkit-scrollbar-thumb { background-color: rgba(203, 213, 225, 0.4); border-radius: 4px; }
.custom-scrollbar::-webkit-scrollbar-thumb:hover { background-color: rgba(148, 163, 184, 0.6); }
</style>
