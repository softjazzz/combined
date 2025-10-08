<template>
  <div class="min-h-screen p-4 md:p-6 bg-gradient-to-br from-blue-50 via-blue-50 to-indigo-100">
    <a-card class="bg-white/90 backdrop-blur-sm rounded-2xl shadow-lg hover:shadow-xl transition-all ring-1 ring-blue-100/70 border md:border-2 border-gray-200 max-w-7xl mx-auto">
      <template #title>
        <div class="flex items-center gap-3">
          <div class="flex items-center justify-center w-10 h-10 rounded-lg bg-blue-100 text-blue-600 ring-1 ring-blue-200">
            <RobotOutlined />
          </div>
          <div>
            <div class="text-xl md:text-2xl font-extrabold text-gray-900 tracking-tight">智能病历导入</div>
            <div class="text-xs md:text-sm text-gray-500 mt-0.5">AI 解析医疗文本与文档，快速生成结构化病历信息</div>
          </div>
        </div>
      </template>

      <template #extra>
        <a-space>
          <a-button @click="showApiConfig = true" type="default" class="hover:shadow-sm">
            <template #icon><SettingOutlined /></template>
            配置
          </a-button>
          <a-button @click="handleCancel" type="default" class="hover:shadow-sm">
            返回
          </a-button>
        </a-space>
      </template>

      <!-- 当前配置显示 -->
      <a-alert
        v-if="currentConfig"
        :message="`当前LLM配置: ${currentConfig.config_name}`"
        :description="`${(currentConfig.provider && currentConfig.provider.provider_name) || ''} - ${(currentConfig.model && currentConfig.model.model_name) || ''}`"
        type="info"
        show-icon
        class="mb-4"
      />

      <!-- Tab页设计 -->
      <a-tabs v-model:activeKey="activeTab" type="card" class="mt-4">
        <!-- Tab 1: 文本输入 -->
        <a-tab-pane key="text" tab="文本输入">
          <div class="rounded-2xl p-2 md:p-3 bg-gradient-to-br from-blue-100/50 via-sky-100/40 to-indigo-100/50">
            <a-card size="small" title="直接输入医疗文本" class="rounded-2xl shadow-md ring-1 ring-slate-200/70">

            <a-textarea
              v-model:value="inputText"
              :rows="8"
              placeholder="请输入医疗记录文本，例如：\n患者姓名，性别，年龄，主诉...\n现病史：...\n既往史：...\n入院诊断：..."
              class="mb-3"
            />
            <div class="flex items-center justify-between">
              <a-space>
                <a-button @click="parseText" :loading="parsing" type="primary" size="large">
                  <template #icon><ThunderboltOutlined /></template>
                  解析文本
                </a-button>
                <a-button @click="clearText" type="default">
                  清空文本
                </a-button>
              </a-space>
              <a-space v-if="parseResult && parseResult.success">
                <a-tag color="success">
                  <CheckCircleOutlined />
                  解析完成
                </a-tag>
                <a-button
                  @click="smartImportTextResult"
                  :loading="importing"
                  type="primary"
                  size="large"
                >
                  <template #icon><DatabaseOutlined /></template>
                  智能导入数据库
                </a-button>
              </a-space>
            </div>
          </a-card>
          </div>
        </a-tab-pane>

        <!-- Tab 2: 文件上传 -->
        <a-tab-pane key="file" tab="文件上传">
          <div class="rounded-2xl p-2 md:p-3 bg-gradient-to-br from-blue-100/50 via-sky-100/40 to-indigo-100/50">
            <a-card size="small" title="上传医疗文档" class="rounded-2xl shadow-md ring-1 ring-slate-200/70">

            <!-- 文件上传区域 -->
            <a-upload-dragger
              :file-list="[]"
              :before-upload="beforeUpload"
              accept=".pdf,.doc,.docx,.txt"
              :multiple="true"
              :show-upload-list="false"
              @change="handleUploadChange"
              class="mb-4 rounded-2xl border-2 border-dashed border-blue-300/70 bg-gradient-to-br from-white via-white to-blue-50/40 shadow-sm hover:shadow-md transition-all"
            >
              <p class="ant-upload-drag-icon">
                <InboxOutlined />
              </p>
              <p class="ant-upload-text">点击或拖拽文件到此区域上传</p>
              <p class="ant-upload-hint">
                支持 PDF、Word、文本文件格式，可批量上传
              </p>
            </a-upload-dragger>

            <!-- 文件管理区域 -->
            <div v-if="uploadedFiles.length > 0" class="mt-4 bg-blue-50/40 rounded-2xl p-4 border md:border-2 border-blue-300">
              <a-divider>已上传文件 ({{ uploadedFiles.length }})</a-divider>

              <!-- 批量操作增强 -->
              <div class="mb-3 text-center p-4 bg-white/95 rounded-xl border md:border-2 border-blue-300 hover:border-blue-400 shadow-md hover:shadow-lg transition-all">
                <a-space size="large">
                  <a-button @click="parseAllFiles" :loading="batchParsing" type="primary" size="default">
                    <template #icon><ThunderboltOutlined /></template>
                    {{ batchParsing ? '解析中...' : '一键解析所有文件' }}
                  </a-button>

                  <a-button
                    v-if="batchParsing"
                    @click="pauseBatchProcessing"
                    :disabled="!canPauseBatch"
                  >
                    <template #icon><PauseCircleOutlined /></template>
                    {{ batchPaused ? '继续' : '暂停' }}
                  </a-button>

                  <a-button
                    v-if="batchParsing"
                    @click="cancelBatchProcessing"
                    danger
                  >
                    <template #icon><StopOutlined /></template>
                    取消
                  </a-button>

                  <a-button @click="clearAllFiles" type="default" size="default" danger>
                    清空所有文件
                  </a-button>

                  <a-button @click="showBatchImportView" type="dashed">
                    <template #icon><AppstoreOutlined /></template>
                    高级批量导入
                  </a-button>
                </a-space>
              </div>

              <!-- 批量处理进度 -->
              <div v-if="batchParsing || batchProgress.total > 0" class="mb-3 p-3 bg-blue-50/60 rounded-xl border border-blue-200">
                <div class="flex justify-between items-center mb-2">
                  <span class="text-sm font-medium text-blue-800">批量处理进度</span>
                  <span class="text-xs text-blue-600">
                    {{ batchProgress.completed }} / {{ batchProgress.total }}
                    {{ batchProgress.currentFile ? `(正在处理: ${batchProgress.currentFile})` : '' }}
                  </span>
                </div>
                <a-progress
                  :percent="batchProgressPercent"
                  :status="batchParsing ? 'active' : (batchProgress.hasErrors ? 'exception' : 'success')"
                  size="small"
                />
              </div>

              <!-- 简洁文件列表 -->
              <div class="bg-white rounded-xl p-3 border md:border-2 border-gray-300 hover:border-gray-400 shadow-sm mb-4">
                <a-list
                  :data-source="uploadedFiles"
                  size="small"
                  :split="false"
                >
                  <template #renderItem="{ item, index }">
                    <a-list-item
                      :class="[
                        'cursor-pointer transition-transform rounded-xl px-3 py-2 mb-2 ui-card ui-card-muted hover:border-blue-400 hover:shadow-md hover:-translate-y-[1px] duration-200 ease-out',
                        currentFileIndex === index ? 'ring-2 ring-blue-300 border-blue-500 bg-blue-50/60 shadow-md' : ''
                      ]"
                      @click="selectFile(index)"
                    >
                      <template #actions>
                        <a-dropdown>
                          <a-button size="small" type="text">
                            <MoreOutlined />
                          </a-button>
                          <template #overlay>
                            <a-menu>
                              <a-menu-item @click="removeFile(index)" danger>
                                <DeleteOutlined />
                                删除文件
                              </a-menu-item>
                            </a-menu>
                          </template>
                        </a-dropdown>
                      </template>

                      <a-list-item-meta>
                        <template #avatar>
                          <FileOutlined class="text-blue-500 text-base" />
                        </template>
                        <template #title>
                          <div class="flex items-center justify-between w-full">
                            <span class="font-medium text-slate-800 max-w-[300px] truncate" :title="item.name">{{ item.name }}</span>
                            <div class="ml-3">
                              <a-tag v-if="item.parsing" color="processing" size="small">
                                <LoadingOutlined />
                                解析中
                              </a-tag>
                              <a-tag v-else-if="item.parsed" color="success" size="small">
                                <CheckCircleOutlined />
                                已解析
                              </a-tag>
                              <a-tag v-else-if="item.error" color="error" size="small">
                                <ExclamationCircleOutlined />
                                解析失败
                              </a-tag>
                              <a-tag v-else color="default" size="small">
                                待解析
                              </a-tag>
                            </div>
                          </div>
                        </template>
                        <template #description>
                          <span class="text-slate-500 text-xs">
                            {{ formatFileSize(item.size) }} • {{ item.uploadTime }}
                          </span>
                        </template>
                      </a-list-item-meta>
                    </a-list-item>
                  </template>
                </a-list>
              </div>
            </div>


          </a-card>
          </div>
        </a-tab-pane>
        </a-tabs>

      <!-- 文件解析内容预览 -->
      <div v-if="currentFile && currentFile.parsed && currentFile.parseResult" class="mt-4 border-t-2 border-blue-100/70 pt-4">
        <div class="rounded-2xl p-2 md:p-3 bg-gradient-to-br from-sky-100/40 via-blue-100/30 to-indigo-100/40">
          <a-card size="small" title="📋 解析内容预览" class="rounded-2xl shadow-md ring-1 ring-slate-200/70">

          <template #extra>
            <a-space>
              <a-tag v-if="currentFile.imported" color="success" class="shadow-sm">
                <CheckCircleOutlined />
                已导入数据库
              </a-tag>
              <a-tag v-else color="geekblue" class="shadow-sm">
                <CheckCircleOutlined />
                解析完成
              </a-tag>
              <a-button
                v-if="!currentFile.imported"
                size="small"
                @click="smartImportToDatabase"
                :loading="importing"
                type="primary"
                class="hover:shadow"
              >
                <template #icon><DatabaseOutlined /></template>
                智能导入数据库
              </a-button>
              <a-button
                v-if="currentFile.imported"
                size="small"
                type="default"
                class="hover:shadow"
                @click="viewImportResult"
              >
                <template #icon><EyeOutlined /></template>
                查看导入结果
              </a-button>
            </a-space>
          </template>

          <!-- 解析统计信息 -->
          <div class="parse-stats mb-3 grid grid-cols-1 sm:grid-cols-2 gap-3">
            <a-row :gutter="0" style="display: contents">

              <a-col :xs="12" :sm="12" :md="12" :lg="12">
                <div class="rounded-xl border border-slate-200 bg-white hover:shadow-sm transition p-3">
                  <div class="flex flex-col gap-1">
                    <div class="text-[13px] text-gray-500 font-medium">内容长度</div>
                    <div class="text-[15px] font-semibold text-gray-900 truncate">
                      {{ ((currentFile.parseResult && currentFile.parseResult.content ? currentFile.parseResult.content.length : 0)).toLocaleString() }} 字符
                    </div>
                  </div>
                </div>
              </a-col>
              <a-col :xs="12" :sm="12" :md="12" :lg="12">
                <div class="rounded-xl border border-slate-200 bg-white hover:shadow-sm transition p-3">
                  <div class="flex flex-col gap-1">
                    <div class="text-[13px] text-gray-500 font-medium">页数</div>
                    <div class="text-[15px] font-semibold text-gray-900 truncate">{{ currentFile.parseResult.pages || 1 }} 页</div>
                  </div>
                </div>
              </a-col>
            </a-row>
          </div>

          <!-- 解析内容 -->
          <div class="parsed-content-display">
            <a-collapse>
              <a-collapse-panel key="content" header="📄 提取的文本内容" class="border border-blue-200 rounded-xl">
                <div class="max-h-96 overflow-y-auto bg-gray-50 border rounded p-4">
                  <pre class="content-text font-sans text-[13px] leading-6 text-gray-800 whitespace-pre-wrap break-words m-0">{{ currentFile.parseResult.content || '无内容' }}</pre>
                </div>
              </a-collapse-panel>

              <!-- PDF原文预览 (仅PDF文件) -->
              <a-collapse-panel v-if="currentFile.type === 'application/pdf' && currentFile.previewUrl" key="pdf" header="📖 PDF原文预览" class="border border-blue-200 rounded-xl">
                <div class="bg-gray-50 p-4 rounded-md border">
                  <div class="mb-2 flex items-center justify-between p-3 rounded-xl border border-slate-200 bg-white shadow-sm">
                    <a-space>
                      <span class="text-sm text-gray-600 font-medium truncate max-w-[200px]">{{ currentFile.name }}</span>
                      <a-divider type="vertical" />
                      <a-button size="small" @click="zoomOut" :disabled="pdfScale <= 0.5">
                        <template #icon><ZoomOutOutlined /></template>
                      </a-button>
                      <span class="text-sm font-medium text-gray-800 min-w-10 text-center">{{ Math.round(pdfScale * 100) }}%</span>
                      <a-button size="small" @click="zoomIn" :disabled="pdfScale >= 2">
                        <template #icon><ZoomInOutlined /></template>
                      </a-button>
                      <a-button size="small" @click="resetZoom">
                        <template #icon><ReloadOutlined /></template>
                        重置
                      </a-button>
                    </a-space>
                  </div>
                  <div class="mt-3 rounded-2xl overflow-hidden bg-gradient-to-br from-sky-100/30 via-blue-100/20 to-indigo-100/30">
                    <iframe
                      :src="currentFile.previewUrl"
                      :style="{ transform: `scale(${pdfScale})`, transformOrigin: 'top left' }"
                      width="100%"
                      height="500px"
                      frameborder="0"
                    ></iframe>
                  </div>
                </div>
              </a-collapse-panel>
            </a-collapse>
          </div>
        </a-card>
        </div>
      </div>

      <!-- 导入结果展示 -->
      <div v-if="importResult" class="mt-4">
        <div class="rounded-2xl p-2 md:p-3 bg-gradient-to-br from-green-100/60 via-emerald-100/50 to-teal-100/60">
          <a-card size="small" title="🎉 智能导入成功" class="rounded-2xl shadow-md ring-1 ring-emerald-200/60">
            <template #extra>
              <a-space>
                <a-tag color="success">
                  <CheckCircleOutlined />
                  已保存到数据库
                </a-tag>
                <a-button size="small" @click="viewInDatabase" type="primary">
                  <template #icon><EyeOutlined /></template>
                  查看记录
                </a-button>
              </a-space>
            </template>

            <a-descriptions bordered size="small" :column="2">
              <a-descriptions-item label="记录ID">
                <a-typography-text copyable>{{ importResult.id }}</a-typography-text>
              </a-descriptions-item>
              <a-descriptions-item label="病历编号">
                <a-typography-text copyable>{{ importResult.record_number }}</a-typography-text>
              </a-descriptions-item>
              <a-descriptions-item label="患者姓名">
                {{ importResult.patient_name }}
              </a-descriptions-item>
              <a-descriptions-item label="患者信息">
                {{ importResult.patient_age }}岁 {{ importResult.patient_gender }}
              </a-descriptions-item>
              <a-descriptions-item label="主要诊断">
                {{ importResult.diagnosis_primary || '未识别' }}
              </a-descriptions-item>
              <a-descriptions-item label="状态">
                <a-tag :color="importResult.status === 'pending' ? 'processing' : 'success'">
                  {{ importResult.status === 'pending' ? '待处理' : '已完成' }}
                </a-tag>
              </a-descriptions-item>
              <a-descriptions-item label="创建时间" :span="2">
                {{ new Date(importResult.created_at).toLocaleString() }}
              </a-descriptions-item>
            </a-descriptions>
          </a-card>
        </div>
      </div>

      <!-- 解析结果简化展示 -->
      <div v-if="parseResult" class="rounded-2xl p-2 md:p-3 bg-gradient-to-br from-emerald-100/60 via-green-100/50 to-teal-100/60">
        <a-card size="small" title="解析结果概览" class="rounded-2xl shadow-md ring-1 ring-emerald-200/60">
          <a-descriptions bordered size="small" :column="2">
            <a-descriptions-item label="患者姓名">
              {{ (parseResult.data && parseResult.data.patientName) || '未识别' }}
            </a-descriptions-item>
            <a-descriptions-item label="科室">
              {{ (parseResult.data && parseResult.data.department) || '未识别' }}
            </a-descriptions-item>
            <a-descriptions-item label="主要诊断">
              {{ (parseResult.data && parseResult.data.primaryDiagnosis) || '未识别' }}
            </a-descriptions-item>
            <a-descriptions-item label="文书数量">
              {{ (parseResult.data && parseResult.data.documents && parseResult.data.documents.length) || 0 }}个
            </a-descriptions-item>
          </a-descriptions>

          <!-- 操作按钮 -->
          <div class="mt-4">
            <a-space>
              <a-button @click="showResultModal = true" type="primary" ghost>
                <EyeOutlined class="mr-1" />
                查看详细解析结果
              </a-button>
              <a-button @click="saveRecord" :loading="saving" type="primary">
                <DatabaseOutlined class="mr-1" />
                保存到数据库
              </a-button>
              <a-button @click="exportResult" type="default">
                导出结果
              </a-button>
            </a-space>
          </div>
        </a-card>
      </div>

      <!-- 操作日志 -->
      <a-card v-if="operationLog" size="small" title="操作日志" class="mb-4 bg-white rounded-2xl shadow-lg border md:border-2 border-gray-300 hover:border-gray-400">
        <div class="bg-gray-50 rounded p-3">
          <pre class="bg-gray-900 text-white p-3 rounded max-h-52 overflow-y-auto font-mono text-xs leading-5 m-0">{{ operationLog }}</pre>
          <div class="text-right mt-2">
            <a-button size="small" @click="clearLog" type="link">
              清空日志
            </a-button>
          </div>
        </div>
      </a-card>
    </a-card>

    <!-- API配置弹窗 -->
    <a-modal
      v-model:open="showApiConfig"
      title="大模型API配置"
      width="1000px"
      :footer="null"
      :destroyOnClose="true"
    >
      <LLMApiConfigStudio @config-updated="handleApiConfigUpdated" />
    </a-modal>

    <!-- 解析结果弹窗 -->
    <MedicalDocumentResultModal
      v-model:visible="showResultModal"
      :data="modalData"
      :original-text="modalOriginalText"
      @confirm="handleModalConfirm"
      @confirm-only="handleModalConfirmOnly"
      @export="handleModalExport"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { message, Modal } from 'ant-design-vue'
import {
  InboxOutlined,
  SettingOutlined,
  ZoomInOutlined,
  ZoomOutOutlined,
  ThunderboltOutlined,
  FileOutlined,
  RobotOutlined,
  LoadingOutlined,
  MoreOutlined,
  DeleteOutlined,
  CheckCircleOutlined,
  ExclamationCircleOutlined,
  ReloadOutlined,
  ClockCircleOutlined,
  DatabaseOutlined,
  CloudUploadOutlined,
  EyeOutlined,
  PauseCircleOutlined,
  StopOutlined,
  AppstoreOutlined
} from '@ant-design/icons-vue'
import { Empty } from 'ant-design-vue'
import MedicalDocumentResultModal from '@/components/MedicalDocumentResultModal.vue'
// import { type UserLLMConfig } from '@/services/llmConfigService'
// import LLMApiConfigStudio from '@/components/LLMApiConfigStudio.vue'
// import { supabase } from '@/lib/supabase'

// 临时类型定义
interface UserLLMConfig {
  config_name: string
  [key: string]: unknown
}

interface SavedRecord {
  id: string
  [key: string]: unknown
}

const router = useRouter()

// 后端 API 配置（开发环境走同源代理，避免跨域与端口错配）
const API_BASE_URL = ''

// 响应式数据
const activeTab = ref('text')
const fileList = ref([])
const inputText = ref('')
const parsing = ref(false)
const saving = ref(false)
const importing = ref(false)
const parseResult = ref<unknown>(null)
const operationLog = ref('')
const importResult = ref<unknown>(null)
const realtimeSubscription = ref<unknown>(null)
const showApiConfig = ref(false)
const currentConfig = ref<UserLLMConfig | null>(null)
// 后端可用性标记，用于避免跨域健康检查造成的报错
const backendAvailable = ref(false)

// Modal相关状态
const showResultModal = ref(false)
const modalData = ref<unknown>(null)
const modalOriginalText = ref('')

function isCrossOrigin(url: string): boolean {
  try {
    const u = new URL(url)
    const currentOrigin = typeof window !== 'undefined' ? window.location.origin : 'http://localhost:3000'
    return u.origin !== currentOrigin
  } catch {
    return true
  }
}

// 文件对象类型定义
interface UploadedFile {
  name: string
  size: number
  type: string
  file: File
  uploadTime: string
  parsed: boolean
  parsing: boolean
  parseResult: Record<string, unknown>
  error: string | null
  previewUrl: string | null
  imported: boolean
  importResult: Record<string, unknown>
}

// 批量文件管理
const uploadedFiles = ref<UploadedFile[]>([])
const currentFileIndex = ref(0)
const pdfScale = ref(1)
const batchParsing = ref(false)
const batchPaused = ref(false)
const canPauseBatch = ref(true)
const batchProgress = ref({
  total: 0,
  completed: 0,
  currentFile: '',
  hasErrors: false
})
const parsingFileIndex = ref(-1)
const llmAnalyzing = ref(false)

// 计算属性
const currentFile = computed(() => {
  return uploadedFiles.value[currentFileIndex.value] || null
})

const batchProgressPercent = computed(() => {
  if (batchProgress.value.total === 0) return 0
  return Math.round((batchProgress.value.completed / batchProgress.value.total) * 100)
})

// 示例医疗文本
// 文本输入占位说明由 placeholder 提供，不再预填示例文本
const sampleText = ''

// 方法
const beforeUpload = (file: File) => {
  console.log('beforeUpload 被调用:', file.name, file.type, file.size)

  // 检查文件数量限制
  if (uploadedFiles.value.length >= 20) {
    message.error('最多只能上传20个文件')
    return false
  }

  // 检查文件类型
  const validTypes = [
    'application/pdf',
    'application/msword',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'text/plain'
  ]

  // 也检查文件扩展名，以防MIME类型不准确
  const fileName = file.name.toLowerCase()
  const validExtensions = ['.pdf', '.doc', '.docx', '.txt']
  const hasValidExtension = validExtensions.some(ext => fileName.endsWith(ext))

  const isValidType = validTypes.includes(file.type) || hasValidExtension
  if (!isValidType) {
    message.error(`文件 ${file.name} 格式不支持，只支持 PDF、Word、文本文件格式`)
    return false
  }

  // 检查文件大小
  const isLt50M = file.size / 1024 / 1024 < 50
  if (!isLt50M) {
    message.error(`文件 ${file.name} 大小超过限制，单文件不能超过 50MB`)
    return false
  }

  console.log('文件验证通过，允许上传:', file.name)
  return false // 返回false，阻止默认上传，使用custom-request处理
}

// 处理文件上传变化事件
const handleUploadChange = (info: unknown) => {
  console.log('handleUploadChange 被调用', info)

  const { fileList } = info
  console.log('文件列表:', fileList)

  // 处理新添加的文件
  fileList.forEach((fileItem: unknown) => {
    const file = fileItem.originFileObj || fileItem

    // 检查是否已经添加过这个文件
    const exists = uploadedFiles.value.some(existingFile =>
      existingFile.name === file.name && existingFile.size === file.size
    )

    if (!exists && file) {
      console.log('添加新文件:', file.name)
      addFileToList(file)
    }
  })
}

// 添加文件到列表
const addFileToList = (file: File) => {
  try {
    console.log('处理文件:', file.name, file.type, file.size)

    // 创建文件对象
    const fileObj: UploadedFile = {
      name: file.name,
      size: file.size,
      type: file.type,
      file: file,
      uploadTime: new Date().toLocaleString(),
      parsed: false,
      parsing: false,
      parseResult: null,
      error: null,
      previewUrl: null, // 用于PDF预览
      imported: false,
      importResult: null
    }

    // 为PDF文件创建预览URL
    if (file.type === 'application/pdf') {
      fileObj.previewUrl = URL.createObjectURL(file)
      console.log('创建PDF预览URL:', fileObj.previewUrl)
    }

    // 添加到文件列表
    uploadedFiles.value.push(fileObj)
    console.log('文件已添加到列表，当前文件数量:', uploadedFiles.value.length)

    // 自动选择新上传的文件
    currentFileIndex.value = uploadedFiles.value.length - 1

    operationLog.value += `\n文件上传成功: ${file.name} (${(file.size / 1024 / 1024).toFixed(2)}MB)`
    message.success(`文件 ${file.name} 上传成功`, 2)

  } catch (error: unknown) {
    console.error('文件处理失败:', error)
    operationLog.value += `\n文件处理失败: ${error}`
    message.error('文件处理失败')
  }
}

// 保留原有的handleFileUpload方法作为备用
const handleFileUpload = async (options: unknown) => {
  console.log('handleFileUpload 被调用', options)
  const { file } = options
  addFileToList(file)
}

// 文件管理方法
const selectFile = (index: number) => {
  currentFileIndex.value = index
  resetZoom()
  console.log('选择文件:', index, (uploadedFiles.value[index] && uploadedFiles.value[index].name))
}

const removeFile = (index: number) => {
  const file = uploadedFiles.value[index]

  // 清理预览URL
  if (file.previewUrl) {
    URL.revokeObjectURL(file.previewUrl)
  }

  uploadedFiles.value.splice(index, 1)

  // 调整当前选中的文件索引
  if (currentFileIndex.value >= uploadedFiles.value.length) {
    currentFileIndex.value = Math.max(0, uploadedFiles.value.length - 1)
  }

  operationLog.value += `\n删除文件: ${file.name}`
  message.success(`删除文件: ${file.name}`)
}

const clearAllFiles = () => {
  // 清理所有预览URL
  uploadedFiles.value.forEach(file => {
    if (file.previewUrl) {
      URL.revokeObjectURL(file.previewUrl)
    }
  })

  uploadedFiles.value = []
  currentFileIndex.value = 0
  operationLog.value += '\n清空所有文件'
  message.success('已清空所有文件')
}

// 解析方法
const parseFile = async (index: number) => {
  const file = uploadedFiles.value[index]
  if (!file) {
    message.warning('文件不存在')
    return
  }

  // 设置解析状态
  file.parsing = true
  file.error = null
  file.parsed = false
  file.imported = false
  operationLog.value += `\n开始解析文件: ${file.name}`

  try {
    // 调用后端PDF解析API
    const formData = new FormData()
    formData.append('file', file.file)
    formData.append('options', '{}')

    const response = await fetch(`${API_BASE_URL}/api/parse-medical-file-public`, {
      method: 'POST',
      body: formData
    })

    if (!response.ok) {
      const errorText = await response.text()
      throw new Error(`HTTP ${response.status}: ${errorText}`)
    }

    const result = await response.json() as any

    if (result.success) {
      // 更新文件状态
      file.parsed = true
      file.parseResult = result.data

      operationLog.value += `\n解析完成: 成功`
      operationLog.value += `\n解析方法: ${result.data.method}`
      operationLog.value += `\n内容长度: ${(result.data && result.data.content ? result.data.content.length : 0) || 0} 字符`

      message.success(`文件解析成功: ${file.name}`)
    } else {
      throw new Error(result.error || '解析失败')
    }
  } catch (error: unknown) {
    file.error = error.message || '解析失败'
    operationLog.value += `\n解析失败: ${error.message}`
    message.error(`文件解析失败: ${file.name} - ${error.message}`)
  } finally {
    file.parsing = false
  }
}

const parseCurrentFile = async () => {
  if (!currentFile.value) {
    message.warning('请先选择文件')
    return
  }

  parsing.value = true
  parsingFileIndex.value = currentFileIndex.value
  operationLog.value += `\n开始解析文件: ${currentFile.value.name}`

  try {
    // 调用后端PDF解析API
    const formData = new FormData()
    formData.append('file', currentFile.value.file)
    formData.append('options', '{}')

    const response = await fetch(`${API_BASE_URL}/api/parse-medical-file-public`, {
      method: 'POST',
      body: formData
    })

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`)
    }

    const result = await response.json()

    if (result.success) {
      // 更新文件状态
      currentFile.value.parsed = true
      currentFile.value.parseResult = result.data

      operationLog.value += `\n解析完成: 成功`
      operationLog.value += `\n解析方法: ${result.data.method}`
      operationLog.value += `\n内容长度: ${(result.data && result.data.content ? result.data.content.length : 0) || 0} 字符`
      operationLog.value += `\n页数: ${result.data.pages || 1} 页`

      message.success('文件解析成功')
    } else {
      throw new Error(result.error || '解析失败')
    }
  } catch (error: unknown) {
    currentFile.value.error = error.message || '解析失败'
    operationLog.value += `\n解析失败: ${error.message}`
    message.error(`文件解析失败: ${error.message}`)
  } finally {
    parsing.value = false
    parsingFileIndex.value = -1
  }
}

// 批量解析方法（增强版）
const parseAllFiles = async () => {
  if (uploadedFiles.value.length === 0) {
    message.warning('请先上传文件')
    return
  }

  batchParsing.value = true
  batchPaused.value = false
  batchProgress.value = {
    total: uploadedFiles.value.length,
    completed: 0,
    currentFile: '',
    hasErrors: false
  }

  operationLog.value += `\n开始批量解析 ${uploadedFiles.value.length} 个文件...`

  let successCount = 0
  let failCount = 0

  for (let i = 0; i < uploadedFiles.value.length; i++) {
    // 检查是否被取消
    if (!batchParsing.value) {
      operationLog.value += '\n批量解析已取消'
      break
    }

    // 检查是否暂停
    while (batchPaused.value && batchParsing.value) {
      await new Promise(resolve => setTimeout(resolve, 100))
    }

    const file = uploadedFiles.value[i]

    // 跳过已解析的文件
    if (file.parsed) {
      operationLog.value += `\n跳过已解析文件: ${file.name}`
      batchProgress.value.completed++
      continue
    }

    batchProgress.value.currentFile = file.name
    operationLog.value += `\n正在解析: ${file.name} (${i + 1}/${uploadedFiles.value.length})`

    try {
      await parseFile(i)
      if (file.parsed) {
        successCount++
      } else {
        failCount++
        batchProgress.value.hasErrors = true
      }
    } catch (error: unknown) {
      failCount++
      batchProgress.value.hasErrors = true
      operationLog.value += `\n解析失败: ${file.name} - ${error.message}`
    }

    batchProgress.value.completed++

    // 添加延迟避免请求过快
    if (i < uploadedFiles.value.length - 1 && batchParsing.value) {
      await new Promise(resolve => setTimeout(resolve, 500))
    }
  }

  batchParsing.value = false
  batchPaused.value = false
  batchProgress.value.currentFile = ''

  if (batchParsing.value !== false) {
    operationLog.value += `\n批量解析完成: 成功 ${successCount} 个，失败 ${failCount} 个`

    if (successCount > 0) {
      message.success(`批量解析完成: 成功 ${successCount} 个，失败 ${failCount} 个`)
  } else {
    message.error('批量解析失败，请检查文件格式和网络连接')
  }
}

// 智能导入到数据库
const smartImportToDatabase = async () => {
  if (!currentFile.value || !currentFile.value.parseResult) {
    message.warning('请先解析文件')
    return
  }

  importing.value = true
  operationLog.value += '\n开始智能导入到数据库...'

  try {
    const parseResult = currentFile.value.parseResult
    const medicalInfo = parseResult.medical_info || {}

    // 提取患者姓名（优先从医疗信息中获取，否则使用默认值）
    const patientName = medicalInfo.patient_name ||
                       extractPatientNameFromContent(parseResult.content) ||
                       '未知患者'

    const importData = {
      patient_name: patientName,
      content: parseResult.content,
      file_info: {
        filename: currentFile.value.name,
        size: currentFile.value.size,
        type: currentFile.value.type,
        pages: parseResult.pages
      },
      parse_result: {
        method: parseResult.method,
        medical_info: medicalInfo
      }
    }

    const response = await fetch(`${API_BASE_URL}/api/smart-import`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(importData)
    })

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`)
    }

    const result = await response.json()

    // 保存导入结果
    importResult.value = result
    currentFile.value.imported = true
    currentFile.value.importResult = result

    operationLog.value += `\n导入成功！`
    operationLog.value += `\n记录ID: ${result.id}`
    operationLog.value += `\n病历编号: ${result.record_number}`
    operationLog.value += `\n创建时间: ${new Date(result.created_at).toLocaleString()}`

    message.success('智能导入成功！数据已保存到数据库')
  } catch (error: unknown) {
    operationLog.value += `\n导入失败: ${error.message}`
    message.error(`智能导入失败: ${error.message}`)
  } finally {
    importing.value = false
  }
}

// 从内容中提取患者姓名的辅助函数
const extractPatientNameFromContent = (content: string): string | null => {
  if (!content) return null

  // 简单的正则匹配患者姓名
  const patterns = [
    /患者[：:]\s*([^\s，,。.]{2,4})/,
    /姓名[：:]\s*([^\s，,。.]{2,4})/,
    /病人[：:]\s*([^\s，,。.]{2,4})/
  ]

  for (const pattern of patterns) {
    const match = content.match(pattern)
    if (match && match[1]) {
      return match[1].trim()
    }
  }

  return null
}

// LLM精确解析
const showLLMAnalysis = async () => {
  if (!(currentFile.value && currentFile.value.parseResult && currentFile.value.parseResult.content)) {
    message.warning('请先解析文件获取文本内容')
    return
  }

  llmAnalyzing.value = true
  operationLog.value += `\n开始LLM精确解析: ${currentFile.value.name}`

  try {
    const { llmService } = await import('@/services/llmService')

    // 检查LLM配置
    if (!currentConfig.value) {
      message.warning('请先配置LLM API')
      showApiConfig.value = true
      return
    }

    // 使用当前配置初始化LLM服务
    await llmService.initialize(currentConfig.value)

    const result = await llmService.extractMedicalData(currentFile.value.parseResult.content, {
      extractDocuments: true,
      extractPatientInfo: true,
      extractDiagnosis: true
    })
    parseResult.value = result

    operationLog.value += `\n LLM解析完成: ${result.success ? '成功' : '失败'}`

    if (result.success) {
      // 显示解析结果Modal
      modalData.value = result.data
      modalOriginalText.value = result.data?.content || currentFile.value.parseResult?.content || ''
      showResultModal.value = true

      message.success('LLM精确解析成功')
    } else {
      message.error(`LLM解析失败: ${result.error}`)
    }
  } catch (error: unknown) {
    console.error('LLM解析失败:', error)
    operationLog.value += `\n LLM解析失败: ${error}`
    message.error('LLM解析失败，请检查API配置')
  } finally {
    llmAnalyzing.value = false
  }
}

// 文本解析方法
const parseText = async () => {
  if (!inputText.value.trim()) {
    message.warning('请输入文本内容')
    return
  }

  parsing.value = true
  operationLog.value += '\n开始解析文本...'

  try {
    // 创建一个临时文本文件进行解析
    const textBlob = new Blob([inputText.value], { type: 'text/plain' })
    const textFile = new File([textBlob], 'input_text.txt', { type: 'text/plain' })

    const formData = new FormData()
    formData.append('file', textFile)
    formData.append('options', '{}')

    const response = await fetch(`${API_BASE_URL}/api/parse-medical-file-public`, {
      method: 'POST',
      body: formData
    })

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`)
    }

    const result = await response.json()

    if (result.success) {
      parseResult.value = {
        success: true,
        data: result.data,
        content: result.data.content,
        method: result.data.method,
        medical_info: result.data.medical_info
      }

      operationLog.value += `\n解析完成: 成功`
      operationLog.value += `\n解析方法: ${result.data.method}`
      operationLog.value += `\n内容长度: ${(result.data && result.data.content ? result.data.content.length : 0) || 0} 字符`

      // 显示解析结果Modal
      modalData.value = result.data
      modalOriginalText.value = result.data.content || inputText.value
      showResultModal.value = true

      message.success('文本解析成功')
    } else {
      throw new Error(result.error || '解析失败')
    }
  } catch (error: unknown) {
    console.error('文本解析失败:', error)
    operationLog.value += `\n解析失败: ${error.message}`
    message.error(`文本解析失败: ${error.message}`)
  } finally {
    parsing.value = false
  }
}

// 智能导入文本解析结果
const smartImportTextResult = async () => {
  if (!(parseResult.value && parseResult.value.success)) {
    message.warning('请先解析文本')
    return
  }

  importing.value = true
  operationLog.value += '\n开始智能导入文本解析结果到数据库...'

  try {
    const data = parseResult.value.data
    const medicalInfo = data.medical_info || {}

    // 提取患者姓名
    const patientName = medicalInfo.patient_name ||
                       extractPatientNameFromContent(data.content) ||
                       '文本导入患者'

    const importData = {
      patient_name: patientName,
      content: data.content,
      file_info: {
        filename: 'text_input.txt',
        size: (data.content ? data.content.length : 0),
        type: 'text/plain',
        pages: 1
      },
      parse_result: {
        method: data.method,
        medical_info: medicalInfo
      }
    }

    const response = await fetch(`${API_BASE_URL}/api/smart-import`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(importData)
    })

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`)
    }

    const result = await response.json()

    // 保存导入结果
    importResult.value = result

    operationLog.value += `\n导入成功！`
    operationLog.value += `\n记录ID: ${result.id}`
    operationLog.value += `\n病历编号: ${result.record_number}`
    operationLog.value += `\n创建时间: ${new Date(result.created_at).toLocaleString()}`

    message.success('智能导入成功！数据已保存到数据库')
  } catch (error: unknown) {
    operationLog.value += `\n导入失败: ${error.message}`
    message.error(`智能导入失败: ${error.message}`)
  } finally {
    importing.value = false
  }
}

const clearText = () => {
  inputText.value = ''
  parseResult.value = null
  message.success('文本已清空')
}

// 测试函数
const testAddFile = () => {
  console.log('测试添加文件')
  const testFile = {
    name: 'test.pdf',
    size: 1024,
    type: 'application/pdf',
    file: null,
    uploadTime: new Date().toLocaleString(),
    parsed: false,
    parsing: false,
    parseResult: null,
    error: null,
    previewUrl: null,
    imported: false,
    importResult: null
  }
  uploadedFiles.value.push(testFile)
  console.log('测试文件已添加，当前数量:', uploadedFiles.value.length)
  message.success('测试文件已添加')
}

// 其他辅助方法
const exportResult = () => {
  if (!(parseResult.value && parseResult.value.success)) {
    message.warning('没有可导出的解析结果')
    return
  }

  try {
    const dataStr = JSON.stringify(parseResult.value, null, 2)
    const dataBlob = new Blob([dataStr], { type: 'application/json' })
    const url = URL.createObjectURL(dataBlob)

    const link = document.createElement('a')
    link.href = url
    link.download = `medical_analysis_${new Date().getTime()}.json`
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)

    URL.revokeObjectURL(url)
    message.success('解析结果已导出')
    operationLog.value += '\n解析结果已导出为JSON文件'
  } catch (error: unknown) {
    message.error('导出失败')
    operationLog.value += `\n导出失败: ${error}`
  }
}

const clearLog = () => {
  operationLog.value = ''
  message.success('日志已清空')
}

const saveRecord = async () => {
  if (!(parseResult.value && parseResult.value.success)) {
    message.warning('没有可保存的解析结果')
    return
  }

  saving.value = true
  operationLog.value += '\n开始保存记录到数据库...'

  try {
    // 导入数据库服务
    const { supabaseMedicalRecordService } = await import('@/services/supabaseMedicalRecordService')

    // 准备保存的数据
    const recordData = Object.assign({}, parseResult.value.data, {
      source: 'smart_import',
      importedAt: new Date().toISOString(),
      originalText: (currentFile.value && currentFile.value.parseResult && currentFile.value.parseResult.content) ? currentFile.value.parseResult.content : inputText.value
    })

    // 保存到数据库
    const savedRecord = await supabaseMedicalRecordService.createRecord(recordData)

    message.success('记录保存成功')
    operationLog.value += `\n记录已保存到数据库，ID: ${savedRecord.id}`

    // 可选：跳转到记录详情页
    // router.push(`/medical-records/${savedRecord.id}`)

  } catch (error: unknown) {
    console.error('保存失败:', error)
    message.error(`保存失败: ${error.message || error}`)
    operationLog.value += `\n保存失败: ${error.message || error}`
  } finally {
    saving.value = false
  }
}

const handleApiConfigUpdated = async (config: UserLLMConfig) => {
  try {
    const { llmService } = await import('@/services/llmService')

    const success = await llmService.loadConfigFromDatabase(config.config_name)
    if (success) {
      currentConfig.value = llmService.getCurrentConfig()
      message.success(`已切换到配置: ${config.config_name}`)
      showApiConfig.value = false
      operationLog.value += `\n配置已更新: ${config.config_name}`
    }
  } catch (error: unknown) {
    message.error('应用配置失败')
    operationLog.value += `\n配置更新失败: ${error}`
  }
}

const handleCancel = () => {
  router.back()
}

// PDF缩放控制
const zoomIn = () => {
  if (pdfScale.value < 2) {
    pdfScale.value += 0.1
  }
}

const zoomOut = () => {
  if (pdfScale.value > 0.5) {
    pdfScale.value -= 0.1
  }
}

const resetZoom = () => {
  pdfScale.value = 1
}

// 查看导入结果
const viewImportResult = () => {
  if (currentFile.value && currentFile.value.importResult) {
    importResult.value = currentFile.value.importResult
    message.success('已显示导入结果')
  }
}

// 在数据库中查看记录
const viewInDatabase = () => {
  if (importResult.value && importResult.value.id) {
    // 跳转到医疗记录详情页面
    router.push(`/dashboard/medical-records/${importResult.value.id}`)
  }
}

// 工具函数
const formatFileSize = (bytes: number) => {
  if (bytes === 0) return '0 Bytes'
  const k = 1024
  const sizes = ['Bytes', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
}

// 获取置信度颜色
const getConfidenceColor = (confidence: number) => {
  if (confidence >= 0.8) return '#52c41a' // 绿色
  if (confidence >= 0.6) return '#faad14' // 橙色
  return '#ff4d4f' // 红色
}

// 获取文档类型颜色
const getDocumentTypeColor = (type: string) => {
  const colorMap: Record<string, string> = {
    'admission_record': 'blue',
    'progress_note': 'green',
    'operation_record': 'red',
    'discharge_record': 'purple',
    'auxiliary_examination': 'orange',
    'informed_consent': 'cyan'
  }
  return colorMap[type] || 'default'
}

// 获取文档类型名称
const getDocumentTypeName = (type: string) => {
  const nameMap: Record<string, string> = {
    'admission_record': '入院记录',
    'progress_note': '病程记录',
    'operation_record': '手术记录',
    'discharge_record': '出院记录',
    'auxiliary_examination': '辅助检查',
    'informed_consent': '知情同意书'
  }
  return nameMap[type] || type
}

// Supabase Realtime 监听
const setupRealtimeSubscription = () => {
  if (realtimeSubscription.value) {
    realtimeSubscription.value.unsubscribe()
  }

  realtimeSubscription.value = supabase
    .channel('medical_records_changes')
    .on('postgres_changes',
      { event: 'INSERT', schema: 'public', table: 'medical_records' },
      (payload) => {
        console.log('新的医疗记录创建:', payload.new)
        operationLog.value += `\n实时更新: 新记录已创建 (ID: ${payload.new.id})`
        message.info('检测到新的医疗记录创建')
      }
    )
    .on('postgres_changes',
      { event: 'UPDATE', schema: 'public', table: 'medical_records' },
      (payload) => {
        console.log('医疗记录更新:', payload.new)
        operationLog.value += `\n实时更新: 记录已更新 (ID: ${payload.new.id})`
      }
    )
    .subscribe()
}

// 检查后端服务连接（跨域或不可达时静默降级）
const checkBackendConnection = async () => {
  try {
    // 如果 API_BASE_URL 跨域，直接跳过健康检查，避免 CORS 错误
    if (isCrossOrigin(API_BASE_URL)) {
      operationLog.value += `\n检测到跨域后端(${API_BASE_URL})，跳过健康检查，启用前端直连模式`
      backendAvailable.value = false
      return true
    }

    const response = await fetch(`${API_BASE_URL}/api/health`)
    if (response.ok) {
      const result: unknown = await response.json()
      operationLog.value += `\n后端服务连接正常: ${result.message || 'OK'}`
      backendAvailable.value = true
      return true
    } else {
      throw new Error(`HTTP ${response.status}`)
    }
  } catch (error: unknown) {
    operationLog.value += `\n后端服务连接失败，已降级为直连模式: ${(error && (error as any).message) || error}`
    backendAvailable.value = false
    // 不提示 warning，避免打扰用户
    return true
  }
}

// 生命周期
onMounted(async () => {
  console.log('SmartImportMedicalRecordNew 组件已挂载')
  operationLog.value = '系统初始化中...'

  // 设置示例文本
  inputText.value = sampleText

  // 检查后端连接
  await checkBackendConnection()

  // 尝试加载默认配置
  try {
    const { llmService } = await import('@/services/llmService')
    const success = await llmService.loadConfigFromDatabase('default')
    if (success) {
      currentConfig.value = llmService.getCurrentConfig()
      operationLog.value += '\n已加载默认LLM配置'
    }
  } catch (error: unknown) {
    operationLog.value += `\n加载配置失败: ${error}`
  }

  // 设置实时监听
  setupRealtimeSubscription()

  operationLog.value += '\n系统初始化完成'
})

// 组件卸载时清理资源
onUnmounted(() => {
  console.log('SmartImportMedicalRecordNew 组件即将卸载')

  // 清理所有预览URL
  uploadedFiles.value.forEach(file => {
    if (file.previewUrl) {
      URL.revokeObjectURL(file.previewUrl)
    }
  })

  // 清理实时订阅
  if (realtimeSubscription.value) {
    realtimeSubscription.value.unsubscribe()
    realtimeSubscription.value = null
  }
})

// Modal处理方法
const handleModalConfirm = async (data: unknown) => {
  // 用户点击"保存并跳转"按钮，直接保存并跳转
  operationLog.value += '\n用户选择保存并跳转到详情页面'
  await autoSaveAndRedirect(data)
}

const handleModalConfirmOnly = (data: unknown) => {
  // 用户点击"确认结果"按钮，只确认不跳转
  parseResult.value = {
    success: true,
    data: data,
    content: data.content,
    method: data.method || 'LLM解析',
    medical_info: data.medical_info || {}
  }

  // 切换到结果标签页，显示简化的结果信息
  activeTab.value = 'result'

  operationLog.value += '\n用户确认了解析结果'
  message.success('解析结果已确认，可以进行后续操作')
}

const handleModalExport = (data: unknown) => {
  try {
    const dataStr = JSON.stringify(data, null, 2)
    const blob = new Blob([dataStr], { type: 'application/json' })
    const url = URL.createObjectURL(blob)

    const link = document.createElement('a')
    link.href = url
    link.download = `medical_parse_result_${new Date().getTime()}.json`
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)

    URL.revokeObjectURL(url)
    message.success('解析结果已导出')
    operationLog.value += '\n解析结果已导出为JSON文件'
  } catch (error: unknown) {
    message.error('导出失败')
    operationLog.value += `\n导出失败: ${error}`
  }
}

// 自动保存并跳转方法
const autoSaveAndRedirect = async (data: unknown) => {
  try {
    saving.value = true
    operationLog.value += '\n开始自动保存解析结果...'

    // 构建保存数据
    const saveData = {
      record_number: data.recordNumber || `AUTO_${Date.now()}`,
      patient_name: data.patientName || '未识别',
      patient_age: data.patientAge || null,
      patient_gender: data.patientGender || null,
      department: data.department || '未识别',
      primary_diagnosis: data.primaryDiagnosis || '未识别',
      secondary_diagnosis: data.secondaryDiagnosis || [],
      major_surgery: data.majorSurgery || '无',
      documents: data.documents || [],
      confidence: data.confidence || 0,
      content: data.content || '',
      method: data.method || 'LLM解析',
      created_at: new Date().toISOString()
    }

    const response = await fetch(`${API_BASE_URL}/api/medical-records`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(saveData)
    })

    if (!response.ok) {
      throw new Error(`保存失败: ${response.status}`)
    }

    const savedRecord = await response.json() as SavedRecord
    operationLog.value += `\n保存成功，记录ID: ${savedRecord.id}`

    message.success('解析结果已保存，正在跳转到详情页面...')

    // 延迟跳转，让用户看到成功消息
    setTimeout(() => {
      router.push(`/dashboard/medical-records/${savedRecord.id}`)
    }, 1500)

  } catch (error: unknown) {
    console.error('自动保存失败:', error)
    message.error(`自动保存失败: ${error.message}`)
    operationLog.value += `\n自动保存失败: ${error.message}`

    // 保存失败时，切换到结果标签页让用户手动操作
    activeTab.value = 'result'
  } finally {
    saving.value = false
  }
}

// 暂停/继续批量处理
const pauseBatchProcessing = () => {
  batchPaused.value = !batchPaused.value
  if (batchPaused.value) {
    operationLog.value += '\n批量解析已暂停'
  } else {
    operationLog.value += '\n批量解析已继续'
  }
}

// 取消批量处理
const cancelBatchProcessing = () => {
  batchParsing.value = false
  batchPaused.value = false
  operationLog.value += '\n批量解析已取消'
  message.info('批量解析已取消')
}

// 跳转到高级批量导入页面
const showBatchImportView = () => {
  router.push('/dashboard/medical-records/batch-import')
}

// 这些方法已在前面定义，删除重复定义
</script>

<style>
/*
  Tailwind migration: legacy scoped styles are disabled.
  This block is intentionally commented out to prioritize Tailwind utility classes.
*/


.smart-import-page {
  /* Design tokens for this page */
  --color-primary: #2563eb;        /* indigo-600 */
  --color-primary-hover: #1d4ed8;  /* indigo-700 */
  --color-primary-weak: #e8f1ff;   /* light bg */
  --color-border: #e6eaf2;
  --color-surface: #ffffff;
  --color-surface-muted: #f7f9fc;
  --color-text: #0f172a;           /* slate-900 */
  --color-text-muted: #6b7280;     /* slate-500 */
  --radius-sm: 8px;
  --radius-md: 12px;
  --radius-lg: 14px;
  --shadow-1: 0 1px 3px rgba(16, 24, 40, .06);
  --shadow-2: 0 4px 12px rgba(16, 24, 40, .08);
  padding: 20px;
  background: linear-gradient(180deg, #f8fbff 0%, #fbfdff 100%);
}

/* Card visuals */
.smart-import-page :deep(.ant-card) {
  border-radius: var(--radius-lg);
  border-color: var(--color-border);
  box-shadow: var(--shadow-1);
}

.smart-import-page :deep(.ant-card-hoverable:hover) {
  box-shadow: var(--shadow-2);
}

/* Buttons */
.smart-import-page :deep(.ant-btn-primary) {
  background: var(--color-primary);
  border-color: var(--color-primary);
}
.smart-import-page :deep(.ant-btn-primary:hover),
.smart-import-page :deep(.ant-btn-primary:focus) {
  background: var(--color-primary-hover);
  border-color: var(--color-primary-hover);
}
.smart-import-page :deep(.ant-btn),
.smart-import-page :deep(.ant-input),
.smart-import-page :deep(.ant-input-affix-wrapper),
.smart-import-page :deep(.ant-select-selector),
.smart-import-page :deep(textarea.ant-input) {
  border-radius: var(--radius-sm);
}

/* Tabs */
.smart-import-page :deep(.ant-tabs-nav::before) { border: none; }
.smart-import-page :deep(.ant-tabs-tab) { border-radius: var(--radius-sm); }
.smart-import-page :deep(.ant-tabs-tab-active) {
  background: var(--color-surface-muted);
}

/* Upload */
.smart-import-page :deep(.ant-upload-drag) {
  background: linear-gradient(135deg, rgba(237,248,255,.6), rgba(238,242,255,.6));
  border-radius: var(--radius-lg);
}

/* Placeholder & typography */
.smart-import-page :deep(.ant-input::placeholder),
.smart-import-page :deep(textarea.ant-input::placeholder) {
  color: #9aa3b2;
}

.smart-import-page .main-card {
  max-width: 1320px;
}


.main-card {
  max-width: 1400px;
  margin: 0 auto;
}

.mb-4 {
  margin-bottom: 16px;
}

.mb-3 {
  margin-bottom: 12px;
}

.mt-2 {
  margin-top: 8px;
}

.mt-4 {
  margin-top: 16px;
}

/* Tab页样式 */
.import-tabs {
  margin-top: 16px;
}

.import-tabs :deep(.ant-tabs-content-holder) {
  padding: 0;
}

.tab-card {
  border: none;
  box-shadow: none;
}

.tab-card :deep(.ant-card-body) {
  padding: 24px;
}

/* 文本输入区域 */
.text-actions {
  display: flex;
  justify-content: flex-start;
  align-items: center;
}

/* 文件上传区域 */
.upload-area {
  margin-bottom: 16px;
}

/* 批量文件管理 */
.file-management {
  background: #fafafa;
  border-radius: 8px;
  padding: 16px;
}

.file-list {
  max-height: 300px;
  overflow-y: auto;
}

.file-card {
  cursor: pointer;
  transition: all 0.3s ease;
  border: 2px solid transparent;
}

.file-card:hover {
  border-color: #1890ff;
  box-shadow: 0 2px 8px rgba(24, 144, 255, 0.2);
}

.file-card.active {
  border-color: #1890ff;
  background: #ffffff;
}

.file-title {
  display: flex;
  align-items: center;
  gap: 8px;
}

.file-name {
  font-size: 12px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.file-info p {
  margin: 4px 0;
  font-size: 12px;
  color: #666;
}

.batch-actions {
  text-align: center;
  padding: 16px;
  background: white;
  border-radius: 6px;
  border: 1px solid #d9d9d9;
}

/* 文件预览样式 */
.file-preview {
  border: 1px solid #d9d9d9;
  border-radius: 6px;
  padding: 16px;
  background: white;
  margin-top: 16px;
}

.pdf-original-preview {
  background: #fafafa;
  border-radius: 6px;
  padding: 12px;
}

.pdf-preview-section {
  background: white;
  border-radius: 4px;
  padding: 12px;
}

.pdf-preview {
  text-align: center;
}

.pdf-toolbar, .text-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 14px;
  background: #f5f5f5;
  border-radius: 4px;
}

.file-info-text {
  font-weight: 500;
  color: #333;
}

.pdf-container {
  border: 1px solid #d9d9d9;
  border-radius: 4px;
  overflow: auto;
  max-height: 500px;
  background: white;
}

.pdf-iframe {
  width: 100%;
  height: 500px;
  border: none;
}

.text-preview {
  max-height: 400px;
  overflow-y: auto;
}

.text-content {
  background: white;
  border: 1px solid #d9d9d9;
  border-radius: 4px;
  padding: 12px;
  margin: 0;
  max-height: 300px;
  overflow-y: auto;
  font-family: 'Courier New', monospace;
  font-size: 13px;
  line-height: 1.4;
}

.file-info-preview {
  background: white;
  padding: 16px;
  border-radius: 4px;
}

.file-actions {
  text-align: center;
  padding: 16px;
  background: #f9f9f9;
  border-radius: 4px;
}

/* 解析结果样式 */
.parse-result {
  background: #f6ffed;
  border: 1px solid #b7eb8f;
  border-radius: 6px;
  padding: 16px;
}

.result-content {
  background: white;
  border: 1px solid #d9d9d9;
  border-radius: 4px;
  padding: 12px;
  margin: 0;
  max-height: 200px;
  overflow-y: auto;
  font-family: 'Courier New', monospace;
  font-size: 12px;
  line-height: 1.4;
}

/* 日志样式 */
.log-container {
  background: var(--color-surface-muted);
  border-radius: var(--radius-sm);
  padding: 12px;
  border: 1px solid var(--color-border);
}

.log-content {
  background: #0f172a;
  color: #e2e8f0;
  padding: 12px;
  border-radius: var(--radius-sm);
  margin: 0;
  max-height: 220px;
  overflow-y: auto;
  font-family: 'Monaco', 'Menlo', 'Courier New', monospace;
  font-size: 12px;
  line-height: 1.5;
  box-shadow: inset 0 1px 3px rgba(0,0,0,.25);
}

.log-actions {
  text-align: right;
}

/* 通用样式 */
pre {
  white-space: pre-wrap;
  word-wrap: break-word;
}

/* 响应式设计优化 */
@media (max-width: 1200px) {
  .file-card .file-name {
    max-width: 120px;
  }
}

@media (max-width: 992px) {
  .batch-actions {
    text-align: left;
  }

  .file-card {
    min-height: 100px;
  }

  .pdf-toolbar {
    flex-direction: column;
    gap: 8px;
  }
}

@media (max-width: 768px) {
  .smart-import-page {
    padding: 8px;
  }

  .main-card {
    max-width: 100%;
    margin: 0;
  }

  .file-management {
    margin-top: 12px;
    padding-top: 12px;
  }

  .file-preview {
    margin-top: 16px;
    padding-top: 12px;
  }

  .pdf-container {
    max-height: 250px;
  }

  .pdf-viewer iframe {
    height: 250px !important;
  }

  .content-text {
    max-height: 300px;
    padding: 12px;
  }

  .file-card {
    min-height: 80px;
  }

  .file-card .file-name {
    max-width: 100px;
    font-size: 12px;
  }

  .batch-actions .ant-space {
    flex-direction: column;
    width: 100%;
  }

  .batch-actions .ant-btn {
    width: 100%;
  }
}

@media (max-width: 576px) {
  .smart-import-page {
    padding: 4px;
  }

  .file-card {
    min-height: 70px;
  }

  .file-meta p {
    font-size: 11px;
  }

  .content-preview-text {
    font-size: 12px;
  }

  .pdf-toolbar {
    padding: 8px;
  }

  .llm-analysis-section {
    padding: 16px 8px;
  }
}

/* 文件管理样式优化 */
.file-management {
  border-top: 1px solid #f0f0f0;
  padding-top: 16px;
  margin-top: 16px;
}

.batch-actions {
  text-align: center;
  margin-bottom: 16px;
}

.file-list {
  margin-bottom: 16px;
}

.file-card {
  cursor: pointer;
  transition: all 0.3s ease;
  border: 2px solid transparent;
  height: 100%;
  min-height: 120px;
}

.file-card:hover {
  border-color: #1890ff;
  box-shadow: 0 4px 12px rgba(24, 144, 255, 0.15);
  transform: translateY(-2px);
}

.file-card.active {
  border-color: #1890ff;
  background-color: #ffffff;
  box-shadow: 0 4px 12px rgba(24, 144, 255, 0.2);
}

.file-title {
  display: flex;
  align-items: center;
  font-size: 13px;
  font-weight: 500;
  color: #333;
}

.file-name {
  margin-left: 6px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 150px;
}

.file-info {
  padding: 8px 0;
}

.file-meta {
  margin-bottom: 8px;
}

.file-meta p {
  margin: 2px 0;
  font-size: 12px;
  color: #666;
}

.file-status {
  text-align: center;
  margin-top: 8px;
}

.file-actions {
  margin-top: 12px;
}

.file-actions .ant-btn {
  font-weight: 500;
}

/* 简洁文件列表样式 */
.file-list-simple {
  background: #fafafa;
  border-radius: 8px;
  padding: 8px;
  border: 1px solid #e8e8e8;
}

.file-item {
  cursor: pointer;
  transition: all 0.2s ease;
  border-radius: var(--radius-sm);
  padding: 10px 12px !important;
  margin-bottom: 6px;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
}

.file-item:hover {
  border-color: var(--color-primary);
  box-shadow: 0 2px 8px rgba(37, 99, 235, 0.12);
}

.file-item.active {
  border-color: var(--color-primary);
  background-color: #eef4ff;
  box-shadow: 0 2px 10px rgba(37, 99, 235, 0.18);
}

.file-info-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  width: 100%;
}

.file-name {
  font-weight: 500;
  color: #333;
  max-width: 300px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.file-status-inline {
  margin-left: 12px;
}

.file-meta-inline {
  color: #666;
  font-size: 12px;
}

.file-icon {
  color: #1890ff;
  font-size: 16px;
}

/* 文件预览样式优化 */
.file-preview {
  margin-top: 24px;
  border-top: 2px solid #f0f0f0;
  padding-top: 16px;
}

.preview-card {
  border: 1px solid #e8e8e8;
  border-radius: 8px;
  overflow: hidden;
}

.preview-placeholder {
  text-align: center;
  padding: 60px 20px;
  background: #fafafa;
  border-radius: 6px;
}

.parsing-status {
  text-align: center;
  padding: 60px 20px;
  background: #f6ffed;
  border-radius: 6px;
}

.parsing-text p {
  margin: 8px 0;
  color: #666;
}

.error-status {
  padding: 20px;
  background: #fff2f0;
  border-radius: 6px;
}

.parsed-content {
  padding: 16px 0;
}

.pdf-preview-section {
  background: #f8f9fa;
  padding: 16px;
  border-radius: 8px;
  border: 1px solid #e8e8e8;
}

.pdf-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: white;
  padding: 12px 16px;
  border-radius: 6px;
  border: 1px solid #d9d9d9;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
}

.file-info-text {
  font-size: 13px;
  color: #666;
  font-weight: 500;
  max-width: 200px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.pdf-viewer {
  margin-top: 12px;
  border: 2px solid #d9d9d9;
  border-radius: 6px;
  overflow: hidden;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.content-preview {
  margin-top: 20px;
}

.content-info {
  margin-bottom: 16px;
  padding: 12px;
  background: #f0f2f5;
  border-radius: 6px;
}

.content-text {
  background: #fafafa;
  border: 1px solid #e8e8e8;
  border-radius: 8px;
  padding: 20px;
  max-height: 400px;
  overflow-y: auto;
  box-shadow: inset 0 1px 3px rgba(0, 0, 0, 0.1);
}

.content-preview-text {
  font-family: 'Courier New', 'Monaco', 'Menlo', monospace;
  font-size: 13px;
  line-height: 1.6;
  margin: 0;
  white-space: pre-wrap;
  word-break: break-word;
  color: #333;
}

.llm-analysis-section {
  text-align: center;
  padding: 24px 0;
  background: #f6ffed;
  border-radius: 8px;
  margin-top: 16px;
}

/* 解析内容预览样式 */
.parse-content-preview {
  border-top: 2px solid #e8f4fd;
  padding-top: 16px;
}

.preview-content-card {
  border: 1px solid #d6e4ff;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(24, 144, 255, 0.1);
}

.parse-stats {
  background: linear-gradient(135deg, rgba(239,246,255,0.6), rgba(238,242,255,0.4));
  padding: 16px;
  border-radius: 14px;
  border: 1px solid #e9ecef;
}

/* 使用深度选择器覆盖 AntD 统计组件的默认字号 */
.parse-stats :deep(.ant-statistic) {
  text-align: center;
  writing-mode: horizontal-tb !important;
}

.parse-stats :deep(.ant-statistic-title) {
  font-size: 12px !important;
  color: #666 !important;
  margin-bottom: 4px !important;
  white-space: nowrap !important;
  overflow: hidden !important;
  text-overflow: ellipsis !important;
  word-break: keep-all !important; /* 防止中文逐字换行 */
  writing-mode: horizontal-tb !important;
  text-orientation: mixed !important;
  letter-spacing: normal !important;
  display: inline-block !important;
}

.parse-stats :deep(.ant-statistic-content) {
  font-size: 14px !important;
  font-weight: 500 !important;
  color: #333 !important;
  line-height: 1.4 !important;
  white-space: nowrap !important;
  overflow: hidden !important;
  text-overflow: ellipsis !important;
  word-break: keep-all !important; /* 防止中文逐字换行 */
  writing-mode: horizontal-tb !important;
  text-orientation: mixed !important;
}

.parse-stats :deep(.ant-statistic-content-value),
.parse-stats :deep(.ant-statistic-content-suffix),
.parse-stats :deep(.ant-statistic-content-prefix) {
  font-size: 14px !important;
  white-space: nowrap !important;
  word-break: keep-all !important;
  writing-mode: horizontal-tb !important;
  display: inline-block !important;
}

.parsed-content-display .ant-collapse {
  border: 1px solid #e8e8e8;
  border-radius: 6px;
}

/* 使用深度选择器强制覆盖Ant Design样式 */
.parsed-content-display :deep(.ant-collapse-header) {
  font-size: 14px !important;
  padding: 12px 16px !important;
  line-height: 1.4 !important;
}

.parsed-content-display :deep(.ant-collapse-content-box) {
  padding: 16px !important;
  font-size: 13px !important;
}

.parsed-content-display :deep(.content-text) {
  font-size: 13px !important;
  line-height: 1.6 !important;
  color: #333 !important;
  font-family: inherit !important;
  white-space: pre-wrap !important; /* 兼容长行换行 */
}

.content-text-container {
  max-height: 400px;
  overflow-y: auto;
  background: #fafafa;
  border: 1px solid #e8e8e8;
  border-radius: 4px;
  padding: 16px;
}

.content-text {
  font-family: 'Courier New', 'Monaco', 'Menlo', monospace;
  font-size: 13px;
  line-height: 1.6;
  margin: 0;
  white-space: pre-wrap;
  word-break: break-word;
  color: #333;
}

.pdf-preview-container {
  background: linear-gradient(135deg, rgba(255,255,255,0.8), rgba(239,246,255,0.6));
  padding: 16px;
  border-radius: 14px;
  border: 1px solid #e8e8e8;
}

.pdf-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: white;
  padding: 12px 16px;
  border-radius: 6px;
  border: 1px solid #d9d9d9;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
}

.pdf-info {
  font-size: 13px;
  color: #666;
  font-weight: 500;
  max-width: 200px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.zoom-level {
  font-size: 13px;
  font-weight: 500;
  color: #333;
  min-width: 40px;
  text-align: center;
}

.pdf-viewer-container {
  margin-top: 12px;
  border: 2px solid #d9d9d9;
  border-radius: 6px;
  overflow: hidden;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.text-center {
  text-align: center;
}

.ml-1 {
  margin-left: 4px;
}

.ml-2 {
  margin-left: 8px;
}

.mt-2 {
  margin-top: 8px;
}

.mt-4 {
  margin-top: 16px;
}

.mb-2 {
  margin-bottom: 8px;
}

.mb-3 {
  margin-bottom: 12px;
}

.mb-4 {
  margin-bottom: 16px;
}

</stylex>
