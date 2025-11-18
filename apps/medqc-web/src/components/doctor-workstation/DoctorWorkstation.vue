<template>
  <div class="min-h-screen bg-gradient-to-br from-blue-50 via-white to-indigo-50">
    <!-- 现代化工作站头部 -->
    <div class="bg-gradient-to-r from-blue-600 to-indigo-600 shadow-lg">
      <div class="max-w-full mx-auto px-6 py-4">
        <div class="flex items-center justify-between">
          <!-- 医生信息 -->
          <div class="flex items-center space-x-4">
            <div class="w-12 h-12 bg-white/20 rounded-full flex items-center justify-center backdrop-blur-sm">
              <i class="fas fa-user-md text-white text-xl"></i>
            </div>
            <div>
              <h2 class="text-xl font-semibold text-white">{{ currentDoctor.name }}</h2>
              <p class="text-blue-100 text-sm">{{ currentDoctor.department }}</p>
            </div>
          </div>

          <!-- 操作按钮 -->
          <div class="flex items-center space-x-3">
            <button
              @click="createNewRecord"
              class="bg-white/20 hover:bg-white/30 text-white px-4 py-2 rounded-lg backdrop-blur-sm transition-all duration-200 flex items-center space-x-2 hover:scale-105"
            >
              <i class="fas fa-plus"></i>
              <span>新建病历</span>
            </button>
            <div class="text-white/80 text-sm">
              当前时间: {{ currentTime }}
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 主要工作区域 - 左右分栏布局 -->
    <div class="flex h-[calc(100vh-80px)]">
      <!-- 左侧患者列表边栏 -->
      <div class="w-80 bg-white shadow-lg border-r border-gray-200 flex flex-col">
        <!-- 患者列表头部 -->
        <div class="p-4 border-b border-gray-200 bg-gradient-to-r from-blue-50 to-indigo-50">
          <div class="flex items-center justify-between mb-3">
            <h3 class="text-lg font-semibold text-gray-800">患者列表</h3>
            <span class="text-sm text-gray-600">{{ filteredPatientList.length }} 位患者</span>
          </div>

          <!-- 搜索框 -->
          <div class="relative">
            <input
              v-model="searchKeyword"
              type="text"
              placeholder="搜索患者姓名、科室..."
              class="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent text-sm"
            >
            <i class="fas fa-search absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400"></i>
          </div>
        </div>

        <!-- 患者列表内容 -->
        <div class="flex-1 overflow-y-auto">
          <div class="p-2 space-y-2">
            <div
              v-for="patient in filteredPatientList"
              :key="patient.id"
              @click="selectPatient(patient)"
              class="p-3 rounded-xl border transition-all duration-200 cursor-pointer hover:shadow-md"
              :class="{
                'border-blue-500 bg-blue-50 shadow-md': currentRecord?.id === patient.id,
                'border-gray-200 bg-white hover:border-blue-300': currentRecord?.id !== patient.id
              }"
            >
              <!-- 患者基本信息 -->
              <div class="flex items-center space-x-3 mb-2">
                <div class="w-10 h-10 bg-gradient-to-br from-blue-500 to-indigo-600 rounded-full flex items-center justify-center flex-shrink-0">
                  <i class="fas fa-user text-white text-sm"></i>
                </div>
                <div class="flex-1 min-w-0">
                  <h4 class="font-semibold text-gray-800 truncate">{{ patient.patient_name }}</h4>
                  <p class="text-xs text-gray-600">{{ patient.patient_age }}岁 · {{ getGenderText(patient.patient_gender) }}</p>
                </div>
                <div class="flex-shrink-0">
                  <span
                    class="px-2 py-1 text-xs font-medium rounded-full"
                    :class="{
                      'bg-yellow-100 text-yellow-800': patient.status === 'pending',
                      'bg-blue-100 text-blue-800': patient.status === 'analyzing',
                      'bg-green-100 text-green-800': patient.status === 'completed',
                      'bg-red-100 text-red-800': patient.status === 'failed'
                    }"
                  >
                    {{ getStatusText(patient.status) }}
                  </span>
                </div>
              </div>

              <!-- 患者详细信息 -->
              <div class="text-xs text-gray-600 space-y-1">
                <div class="flex justify-between">
                  <span class="text-gray-500">科室:</span>
                  <span class="font-medium text-gray-700">{{ patient.department }}</span>
                </div>
                <div class="flex justify-between">
                  <span class="text-gray-500">入院:</span>
                  <span class="font-medium text-gray-700">{{ formatDate(patient.admission_date) }}</span>
                </div>
                <div v-if="patient.qc_score" class="flex justify-between">
                  <span class="text-gray-500">质控:</span>
                  <div class="flex items-center space-x-1">
                    <span class="font-medium text-gray-700">{{ patient.qc_score }}</span>
                    <span
                      class="px-1 py-0.5 text-xs font-medium rounded"
                      :class="{
                        'bg-green-100 text-green-800': patient.qc_score >= 90,
                        'bg-blue-100 text-blue-800': patient.qc_score >= 80 && patient.qc_score < 90,
                        'bg-yellow-100 text-yellow-800': patient.qc_score >= 70 && patient.qc_score < 80,
                        'bg-red-100 text-red-800': patient.qc_score < 70
                      }"
                    >
                      {{ getGrade(patient.qc_score) }}级
                    </span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 右侧主工作区域 -->
      <div class="flex-1 flex flex-col">
        <div class="flex-1 p-6">
          <!-- 病历编辑区 - 现在占据全宽 -->
          <div class="flex flex-col h-full">
            <div class="bg-white rounded-2xl shadow-lg border border-gray-200 overflow-hidden flex-1 flex flex-col">
            <!-- 患者信息头部 -->
            <div v-if="currentRecord" class="bg-gradient-to-r from-blue-50 to-indigo-50 p-6 border-b border-gray-200">
              <div class="flex items-start justify-between">
                <!-- 患者基本信息 -->
                <div class="flex-1">
                  <div class="flex items-center space-x-3 mb-4">
                    <h3 class="text-2xl font-bold text-gray-800">{{ currentRecord.patient_name }}</h3>
                    <span class="px-3 py-1 bg-blue-100 text-blue-800 text-sm font-medium rounded-full">
                      #{{ currentRecord.id.slice(-6) }}
                    </span>
                  </div>

                  <!-- 患者详情 -->
                  <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
                    <div class="flex items-center space-x-2 bg-white/70 px-3 py-2 rounded-lg">
                      <i class="fas fa-birthday-cake text-blue-600"></i>
                      <span class="text-sm font-medium text-gray-700">{{ currentRecord.patient_age }}岁</span>
                    </div>
                    <div class="flex items-center space-x-2 bg-white/70 px-3 py-2 rounded-lg">
                      <i class="fas fa-venus-mars text-blue-600"></i>
                      <span class="text-sm font-medium text-gray-700">{{ getGenderText(currentRecord.patient_gender) }}</span>
                    </div>
                    <div class="flex items-center space-x-2 bg-white/70 px-3 py-2 rounded-lg">
                      <i class="fas fa-hospital text-blue-600"></i>
                      <span class="text-sm font-medium text-gray-700">{{ currentRecord.department }}</span>
                    </div>
                    <div class="flex items-center space-x-2 bg-white/70 px-3 py-2 rounded-lg">
                      <i class="fas fa-calendar text-blue-600"></i>
                      <span class="text-sm font-medium text-gray-700">{{ formatDate(currentRecord.admission_date) }}</span>
                    </div>
                  </div>
                </div>

                <!-- 状态和质控信息 -->
                <div class="flex flex-col items-end space-y-3">
                  <span
                    class="px-4 py-2 text-sm font-medium rounded-full"
                    :class="{
                      'bg-yellow-100 text-yellow-800': currentRecord.status === 'pending',
                      'bg-blue-100 text-blue-800': currentRecord.status === 'analyzing',
                      'bg-green-100 text-green-800': currentRecord.status === 'completed',
                      'bg-red-100 text-red-800': currentRecord.status === 'failed'
                    }"
                  >
                    {{ getStatusText(currentRecord.status) }}
                  </span>

                  <div v-if="currentRecord.qc_score" class="flex items-center space-x-2 bg-white px-4 py-2 rounded-lg shadow-sm">
                    <span class="text-lg font-bold text-blue-600">{{ currentRecord.qc_score }}</span>
                    <span
                      class="px-2 py-1 text-xs font-medium rounded"
                      :class="{
                        'bg-green-100 text-green-800': currentRecord.qc_score >= 90,
                        'bg-blue-100 text-blue-800': currentRecord.qc_score >= 80 && currentRecord.qc_score < 90,
                        'bg-yellow-100 text-yellow-800': currentRecord.qc_score >= 70 && currentRecord.qc_score < 80,
                        'bg-red-100 text-red-800': currentRecord.qc_score < 70
                      }"
                    >
                      {{ getGrade(currentRecord.qc_score) }}级
                    </span>
                  </div>
                </div>
              </div>

              <!-- 操作按钮 -->
              <div class="flex items-center space-x-3 mt-4">
                <button
                  @click="loadTemplate"
                  class="bg-white hover:bg-gray-50 text-gray-700 px-4 py-2 rounded-lg border border-gray-300 transition-colors duration-200 flex items-center space-x-2"
                >
                  <i class="fas fa-file-medical"></i>
                  <span>模板</span>
                </button>
                <button
                  @click="saveRecord"
                  :disabled="!hasChanges"
                  class="bg-green-600 hover:bg-green-700 disabled:bg-gray-400 text-white px-4 py-2 rounded-lg transition-colors duration-200 flex items-center space-x-2"
                >
                  <i class="fas fa-save"></i>
                  <span>{{ hasChanges ? '保存' : '已保存' }}</span>
                </button>
                <button
                  @click="analyzeRecord"
                  :disabled="!currentRecord?.content || isAnalyzing"
                  class="bg-blue-600 hover:bg-blue-700 disabled:bg-gray-400 text-white px-4 py-2 rounded-lg transition-colors duration-200 flex items-center space-x-2"
                >
                  <i class="fas" :class="isAnalyzing ? 'fa-spinner fa-spin' : 'fa-shield-alt'"></i>
                  <span>{{ isAnalyzing ? '分析中...' : '质控分析' }}</span>
                </button>
                <button
                  @click="toggleQCPanel"
                  class="bg-purple-600 hover:bg-purple-700 text-white px-4 py-2 rounded-lg transition-colors duration-200 flex items-center space-x-2"
                >
                  <i class="fas" :class="showQCPanel ? 'fa-eye-slash' : 'fa-eye'"></i>
                  <span>{{ showQCPanel ? '隐藏质控' : '显示质控' }}</span>
                </button>
              </div>
            </div>

            <!-- 编辑器容器 -->
            <div class="flex-1 p-6">
                <!-- 欢迎页面 -->
                <div v-if="!currentRecord" class="flex-1 flex items-center justify-center">
                  <div class="text-center max-w-2xl mx-auto">
                    <div class="w-24 h-24 bg-gradient-to-br from-blue-500 to-indigo-600 rounded-full flex items-center justify-center mx-auto mb-8">
                      <i class="fas fa-stethoscope text-white text-4xl"></i>
                    </div>
                    <h2 class="text-3xl font-bold text-gray-800 mb-4">欢迎使用医生工作站</h2>
                    <p class="text-gray-600 text-lg mb-8 leading-relaxed">
                      请从左侧患者列表中选择一个患者开始工作，或创建新的病历记录。
                    </p>

                    <!-- 快速操作 -->
                    <div class="flex items-center justify-center space-x-4 mb-12">
                      <button
                        @click="createNewRecord"
                        class="bg-blue-600 hover:bg-blue-700 text-white px-6 py-3 rounded-xl transition-all duration-200 flex items-center space-x-2 hover:scale-105 shadow-lg"
                      >
                        <i class="fas fa-plus"></i>
                        <span>新建病历</span>
                      </button>
                    </div>

                  <!-- 功能特色 -->
                  <div class="grid grid-cols-2 md:grid-cols-4 gap-6">
                    <div class="bg-white p-6 rounded-xl shadow-sm border border-gray-200 hover:shadow-md transition-shadow duration-200">
                      <div class="w-12 h-12 bg-blue-100 rounded-lg flex items-center justify-center mb-4 mx-auto">
                        <i class="fas fa-edit text-blue-600 text-xl"></i>
                      </div>
                      <h3 class="font-semibold text-gray-800 mb-2">智能编辑</h3>
                      <p class="text-sm text-gray-600">智能病历编辑器</p>
                    </div>
                    <div class="bg-white p-6 rounded-xl shadow-sm border border-gray-200 hover:shadow-md transition-shadow duration-200">
                      <div class="w-12 h-12 bg-green-100 rounded-lg flex items-center justify-center mb-4 mx-auto">
                        <i class="fas fa-shield-alt text-green-600 text-xl"></i>
                      </div>
                      <h3 class="font-semibold text-gray-800 mb-2">质控分析</h3>
                      <p class="text-sm text-gray-600">实时质控分析</p>
                    </div>
                    <div class="bg-white p-6 rounded-xl shadow-sm border border-gray-200 hover:shadow-md transition-shadow duration-200">
                      <div class="w-12 h-12 bg-yellow-100 rounded-lg flex items-center justify-center mb-4 mx-auto">
                        <i class="fas fa-chart-line text-yellow-600 text-xl"></i>
                      </div>
                      <h3 class="font-semibold text-gray-800 mb-2">质量评分</h3>
                      <p class="text-sm text-gray-600">智能质量评分</p>
                    </div>
                    <div class="bg-white p-6 rounded-xl shadow-sm border border-gray-200 hover:shadow-md transition-shadow duration-200">
                      <div class="w-12 h-12 bg-purple-100 rounded-lg flex items-center justify-center mb-4 mx-auto">
                        <i class="fas fa-lightbulb text-purple-600 text-xl"></i>
                      </div>
                      <h3 class="font-semibold text-gray-800 mb-2">改进建议</h3>
                      <p class="text-sm text-gray-600">智能改进建议</p>
                    </div>
                  </div>
                  </div>
                </div>

              <!-- 病历编辑器 -->
              <div v-else class="flex-1 flex flex-col overflow-hidden">
                <div class="flex-1 overflow-y-auto">
                  <MedicalRecordEditor
                    v-model="editorContent"
                    :placeholder="'请输入病历内容...'"
                    @input="onContentChange"
                    @save="saveRecord"
                    class="h-full min-h-[600px]"
                  />
                </div>
              </div>
            </div>

            <!-- 状态栏 -->
            <div class="bg-gradient-to-r from-gray-50 to-blue-50 px-6 py-3 border-t border-gray-200 flex items-center justify-between">
              <div class="flex items-center space-x-4">
                <div v-if="isDraftSaving" class="flex items-center space-x-2 text-blue-600">
                  <i class="fas fa-spinner fa-spin"></i>
                  <span class="text-sm font-medium">自动保存中...</span>
                </div>
                <div v-else-if="lastSaved" class="flex items-center space-x-2 text-green-600">
                  <i class="fas fa-check"></i>
                  <span class="text-sm font-medium">已保存于 {{ formatTime(lastSaved) }}</span>
                </div>
              </div>

              <div class="text-sm font-medium text-gray-600">
                字数：{{ wordCount }}
              </div>
            </div>
            </div>
          </div>
        </div>
      </div>
    </div>
    <!-- 模板选择对话框 -->
    <TemplateSelector
      v-if="showTemplateSelector"
      :templates="templates"
      @select="applyTemplate"
      @close="showTemplateSelector = false"
    />

    <!-- 新建病历对话框 -->
    <NewRecordDialog
      v-if="showNewRecordDialog"
      @create="createRecord"
      @close="showNewRecordDialog = false"
    />

    <!-- 质控分析悬浮窗 -->
    <div
      v-if="showQCPanel && (qcAnalysisResult || isAnalyzing)"
      ref="qcFloatingPanel"
      class="fixed bg-white rounded-2xl shadow-2xl border border-gray-200 z-50 resize overflow-hidden"
      :style="{
        left: qcPanelPosition.x + 'px',
        top: qcPanelPosition.y + 'px',
        width: qcPanelSize.width + 'px',
        height: qcPanelSize.height + 'px',
        minWidth: '400px',
        minHeight: '300px',
        maxWidth: '800px',
        maxHeight: '80vh'
      }"
    >
      <!-- 悬浮窗标题栏 -->
      <div
        ref="qcPanelHeader"
        class="bg-gradient-to-r from-purple-500 to-indigo-600 text-white px-4 py-3 cursor-move select-none flex items-center justify-between"
        @mousedown="startDrag"
      >
        <div class="flex items-center space-x-2">
          <i class="fas fa-shield-alt"></i>
          <span class="font-semibold">质控分析</span>
        </div>
        <div class="flex items-center space-x-2">
          <button
            @click="toggleMinimize"
            class="w-6 h-6 rounded-full bg-white/20 hover:bg-white/30 flex items-center justify-center transition-colors duration-200"
          >
            <i class="fas" :class="isMinimized ? 'fa-window-maximize' : 'fa-window-minimize'" style="font-size: 10px;"></i>
          </button>
          <button
            @click="closeQCPanel"
            class="w-6 h-6 rounded-full bg-white/20 hover:bg-red-500 flex items-center justify-center transition-colors duration-200"
          >
            <i class="fas fa-times" style="font-size: 10px;"></i>
          </button>
        </div>
      </div>

      <!-- 悬浮窗内容 -->
      <div v-if="!isMinimized" class="flex-1 overflow-hidden">
        <QCAnalysisPanel
          :analysis-result="qcAnalysisResult"
          :is-analyzing="isAnalyzing"
          @refresh="analyzeRecord"
          @apply-suggestion="applySuggestion"
          class="h-full"
        />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { debounce } from 'lodash-es'
import MedicalRecordEditor from './MedicalRecordEditor.vue'
import QCAnalysisPanel from './QCAnalysisPanel.vue'
import TemplateSelector from './TemplateSelector.vue'
import NewRecordDialog from './NewRecordDialog.vue'
import {
  getDemoMedicalRecords,
  getDoctorWorkstationTemplates,
  saveMedicalRecordDraft,
  submitRecordForQCAnalysis,
  updateMedicalRecord,
  createMedicalRecord,
  getMedicalRecords
} from '@/api/medical-records'
import type {
  MedicalRecord,
  MedicalRecordTemplate,
  QCAnalysisResult
} from '@/api/medical-records'

// 响应式数据
const currentDoctor = ref({
  name: '张医生',
  department: '内科',
  id: 'doctor-001'
})

const selectedScenario = ref<'complete' | 'incomplete' | 'inconsistent' | 'irrational' | ''>('')
const currentRecord = ref<MedicalRecord | null>(null)
const editorContent = ref('')
const originalContent = ref('')
const templates = ref<MedicalRecordTemplate[]>([])
const qcAnalysisResult = ref<QCAnalysisResult | null>(null)
const currentTime = ref('')

// 界面状态
const patientList = ref<MedicalRecord[]>([])
const searchKeyword = ref('')

// 状态管理
const isAnalyzing = ref(false)
const isDraftSaving = ref(false)
const lastSaved = ref<Date | null>(null)
const hasChanges = computed(() => editorContent.value !== originalContent.value)
const wordCount = computed(() => editorContent.value.length)

// 过滤患者列表
const filteredPatientList = computed(() => {
  if (!searchKeyword.value.trim()) {
    return patientList.value
  }

  const keyword = searchKeyword.value.toLowerCase().trim()
  return patientList.value.filter(patient =>
    patient.patient_name.toLowerCase().includes(keyword) ||
    patient.department.toLowerCase().includes(keyword) ||
    patient.patient_age.toString().includes(keyword)
  )
})

// 对话框状态
const showTemplateSelector = ref(false)
const showNewRecordDialog = ref(false)

// 悬浮窗状态
const showQCPanel = ref(false)
const isMinimized = ref(false)
const qcFloatingPanel = ref<HTMLElement | null>(null)
const qcPanelHeader = ref<HTMLElement | null>(null)

// 悬浮窗位置和大小
const qcPanelPosition = ref({ x: window.innerWidth - 450, y: 100 })
const qcPanelSize = ref({ width: 400, height: 600 })

// 拖拽状态
const isDragging = ref(false)
const dragOffset = ref({ x: 0, y: 0 })

// 计算属性和方法
const getGenderText = (gender: 'M' | 'F' | 'U') => {
  const genderMap = { M: '男', F: '女', U: '未知' }
  return genderMap[gender] || '未知'
}

const formatTime = (date: Date) => {
  return date.toLocaleTimeString('zh-CN', {
    hour: '2-digit',
    minute: '2-digit'
  })
}

const getStatusText = (status: string) => {
  const statusMap: Record<string, string> = {
    pending: '待处理',
    analyzing: '分析中',
    completed: '已完成',
    failed: '失败'
  }
  return statusMap[status] || status
}

const getGrade = (score: number): string => {
  if (score >= 90) return 'A'
  if (score >= 80) return 'B'
  if (score >= 70) return 'C'
  return 'D'
}

// 格式化日期显示
const formatDate = (dateString: string) => {
  const date = new Date(dateString)
  const now = new Date()
  const diffTime = Math.abs(now.getTime() - date.getTime())
  const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24))

  if (diffDays === 1) return '今天'
  if (diffDays === 2) return '昨天'
  if (diffDays <= 7) return `${diffDays}天前`

  return date.toLocaleDateString('zh-CN', {
    month: '2-digit',
    day: '2-digit'
  })
}

// 更新当前时间
const updateCurrentTime = () => {
  currentTime.value = new Date().toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit'
  })
}

// 加载患者列表
const loadPatientList = async () => {
  console.log('🔄 开始加载患者列表...')
  try {
    // 首先尝试从数据库加载真实的患者数据
    console.log('📡 调用 getMedicalRecords API...')
    const response = await getMedicalRecords({
      limit: 50, // 加载更多患者
      offset: 0
    })

    console.log('📊 API响应:', {
      success: response.success,
      dataLength: response.data?.length || 0,
      error: response.error
    })

    if (response.success && response.data && response.data.length > 0) {
      // 如果数据库中有数据，使用真实数据
      patientList.value = response.data
      console.log(`✅ 从数据库加载了 ${response.data.length} 个患者`)
      console.log('👥 患者列表:', response.data.map(p => `${p.patient_name} (${p.department})`))
    } else {
      // 如果数据库中没有数据，回退到演示数据
      console.log('⚠️ 数据库中没有患者数据，使用演示数据')
      const scenarios = ['complete', 'incomplete', 'inconsistent', 'irrational'] as const
      const allPatients: MedicalRecord[] = []

      for (const scenario of scenarios) {
        const demoResponse = await getDemoMedicalRecords(scenario)
        if (demoResponse.data) {
          allPatients.push(...demoResponse.data)
        }
      }

      patientList.value = allPatients
      console.log(`📋 加载了 ${allPatients.length} 个演示患者`)
    }
  } catch (error) {
    console.error('❌ 加载患者列表失败:', error)
    // 发生错误时也尝试加载演示数据
    try {
      console.log('🔄 尝试加载演示数据作为备选...')
      const scenarios = ['complete', 'incomplete', 'inconsistent', 'irrational'] as const
      const allPatients: MedicalRecord[] = []

      for (const scenario of scenarios) {
        const demoResponse = await getDemoMedicalRecords(scenario)
        if (demoResponse.data) {
          allPatients.push(...demoResponse.data)
        }
      }

      patientList.value = allPatients
      console.log(`📋 备选方案：加载了 ${allPatients.length} 个演示患者`)
    } catch (fallbackError) {
      console.error('❌ 加载演示数据也失败:', fallbackError)
    }
  }
}

// 选择患者
const selectPatient = (patient: MedicalRecord) => {
  currentRecord.value = patient
  editorContent.value = patient.content
  originalContent.value = patient.content
  selectedScenario.value = ''

  // 自动进行质控分析
  if (patient.content) {
    analyzeRecord()
  }
}

// 加载模板
const loadTemplate = async () => {
  if (templates.value.length === 0) {
    const response = await getDoctorWorkstationTemplates()
    if (response.data) {
      templates.value = response.data
    }
  }
  showTemplateSelector.value = true
}

// 应用模板
const applyTemplate = (template: MedicalRecordTemplate) => {
  editorContent.value = template.template_content
  showTemplateSelector.value = false
}

// 内容变化处理
const onContentChange = () => {
  debouncedSaveDraft()
}

// 防抖保存草稿
const debouncedSaveDraft = debounce(async () => {
  if (!currentRecord.value || !hasChanges.value) return

  isDraftSaving.value = true
  try {
    await saveMedicalRecordDraft(currentRecord.value.id, {
      content: editorContent.value
    })
    lastSaved.value = new Date()
  } catch (error) {
    console.error('保存草稿失败:', error)
  } finally {
    isDraftSaving.value = false
  }
}, 2000)

// 保存病历
const saveRecord = async () => {
  if (!currentRecord.value) return

  try {
    const response = await updateMedicalRecord(currentRecord.value.id, {
      content: editorContent.value
    })

    if (response.data) {
      originalContent.value = editorContent.value
      lastSaved.value = new Date()
      console.log('病历保存成功')
    }
  } catch (error) {
    console.error('保存病历失败:', error)
  }
}

// 质控分析
const analyzeRecord = async () => {
  if (!currentRecord.value || !editorContent.value) return

  isAnalyzing.value = true
  // 显示悬浮窗
  showQCPanel.value = true

  try {
    const response = await submitRecordForQCAnalysis(
      currentRecord.value.id,
      editorContent.value
    )

    if (response.data) {
      qcAnalysisResult.value = response.data
    }
  } catch (error) {
    console.error('质控分析失败:', error)
  } finally {
    isAnalyzing.value = false
  }
}

// 应用建议
const applySuggestion = (suggestion: string) => {
  // 这里可以实现智能应用建议的逻辑
  console.log('应用建议:', suggestion)
}

// 创建新病历
const createNewRecord = () => {
  showNewRecordDialog.value = true
}

const createRecord = async (recordData: Partial<MedicalRecord>) => {
  try {
    const response = await createMedicalRecord(recordData)
    if (response.data) {
      currentRecord.value = response.data
      editorContent.value = response.data.content || ''
      originalContent.value = editorContent.value
      showNewRecordDialog.value = false
    }
  } catch (error) {
    console.error('创建病历失败:', error)
  }
}

// 悬浮窗相关方法
const toggleQCPanel = () => {
  showQCPanel.value = !showQCPanel.value
  if (showQCPanel.value && !qcAnalysisResult.value && currentRecord.value?.content) {
    analyzeRecord()
  }
}

const closeQCPanel = () => {
  showQCPanel.value = false
  isMinimized.value = false
}

const toggleMinimize = () => {
  isMinimized.value = !isMinimized.value
}

// 拖拽功能
const startDrag = (event: MouseEvent) => {
  if (!qcFloatingPanel.value) return

  isDragging.value = true
  const rect = qcFloatingPanel.value.getBoundingClientRect()
  dragOffset.value = {
    x: event.clientX - rect.left,
    y: event.clientY - rect.top
  }

  document.addEventListener('mousemove', onDrag)
  document.addEventListener('mouseup', stopDrag)
  event.preventDefault()
}

const onDrag = (event: MouseEvent) => {
  if (!isDragging.value) return

  const newX = event.clientX - dragOffset.value.x
  const newY = event.clientY - dragOffset.value.y

  // 限制在窗口范围内
  const maxX = window.innerWidth - qcPanelSize.value.width
  const maxY = window.innerHeight - qcPanelSize.value.height

  qcPanelPosition.value = {
    x: Math.max(0, Math.min(newX, maxX)),
    y: Math.max(0, Math.min(newY, maxY))
  }
}

const stopDrag = () => {
  isDragging.value = false
  document.removeEventListener('mousemove', onDrag)
  document.removeEventListener('mouseup', stopDrag)

  // 保存位置到本地存储
  localStorage.setItem('qcPanelPosition', JSON.stringify(qcPanelPosition.value))
}

// 组件挂载时初始化
onMounted(async () => {
  // 更新时间并设置定时器
  updateCurrentTime()
  setInterval(updateCurrentTime, 1000)

  // 加载患者列表
  await loadPatientList()

  // 初始化悬浮窗位置
  const savedPosition = localStorage.getItem('qcPanelPosition')
  if (savedPosition) {
    try {
      qcPanelPosition.value = JSON.parse(savedPosition)
    } catch (error) {
      console.error('解析保存的悬浮窗位置失败:', error)
    }
  }

  // 监听窗口大小变化，调整悬浮窗位置
  const handleResize = () => {
    const maxX = window.innerWidth - qcPanelSize.value.width
    const maxY = window.innerHeight - qcPanelSize.value.height

    qcPanelPosition.value = {
      x: Math.max(0, Math.min(qcPanelPosition.value.x, maxX)),
      y: Math.max(0, Math.min(qcPanelPosition.value.y, maxY))
    }
  }

  window.addEventListener('resize', handleResize)

  // 不默认加载患者，显示欢迎页面
  // 让医生主动选择患者或创建新病历
})

// 监听场景变化
watch(selectedScenario, () => {
  qcAnalysisResult.value = null
})
</script>

<style scoped>
/* 使用 Tailwind CSS 进行样式设计 */

/* 自定义滚动条样式 */
.overflow-y-auto::-webkit-scrollbar {
  width: 8px;
}

.overflow-y-auto::-webkit-scrollbar-track {
  background: #f1f5f9;
  border-radius: 4px;
}

.overflow-y-auto::-webkit-scrollbar-thumb {
  background: #cbd5e1;
  border-radius: 4px;
}

.overflow-y-auto::-webkit-scrollbar-thumb:hover {
  background: #94a3b8;
}

/* 悬浮窗阴影效果 */
.shadow-2xl {
  box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.25);
}

/* 拖拽时的样式 */
.cursor-move:active {
  cursor: grabbing;
}

/* 悬浮窗动画 */
.fixed {
  transition: all 0.3s ease;
}

/* 调整大小手柄样式 */
.resize {
  resize: both;
}

.resize::-webkit-resizer {
  background: linear-gradient(-45deg, transparent 0%, transparent 35%, #cbd5e1 35%, #cbd5e1 65%, transparent 65%);
  border-radius: 0 0 4px 0;
}
</style>
