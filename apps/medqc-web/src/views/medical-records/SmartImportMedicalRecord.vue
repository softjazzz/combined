<template>
  <div class="page-container">
    <!-- 面包屑导航 -->
    <a-breadcrumb class="breadcrumb">
      <a-breadcrumb-item>
        <router-link to="/dashboard/medical-records">
          测试病历管理
        </router-link>
      </a-breadcrumb-item>
      <a-breadcrumb-item>智能导入病历</a-breadcrumb-item>
    </a-breadcrumb>

    <!-- 页面标题 -->
    <div class="page-header">
      <div class="header-content">
        <div class="header-text">
          <h1 class="page-title">
            智能病历导入
          </h1>
          <div class="page-description">
            使用AI技术自动解析病历文本，快速生成结构化病历数据
          </div>
        </div>
        <div class="header-actions">
          <a-button
            type="text"
            @click="showApiConfig = true"
          >
            <template #icon>
              <SettingOutlined />
            </template>
            API配置
          </a-button>
        </div>
      </div>
    </div>

    <!-- 导入步骤指示器 -->
    <a-card class="steps-card">
      <a-steps
        :current="currentStep"
        size="small"
      >
        <a-step
          title="输入病历文本"
          description="粘贴或上传病历内容"
        />
        <a-step
          title="AI智能解析"
          description="自动抽取结构化信息"
        />
        <a-step
          title="确认和修正"
          description="检查并修正解析结果"
        />
        <a-step
          title="完成导入"
          description="保存到病历系统"
        />
      </a-steps>
    </a-card>

    <!-- 步骤1: 输入病历文本 -->
    <a-card
      v-if="currentStep === 0"
      title="步骤1: 输入病历文本"
      class="step-card"
    >
      <a-tabs
        v-model:active-key="inputMethod"
        @change="handleInputMethodChange"
      >
        <!-- 文本粘贴 -->
        <a-tab-pane
          key="paste"
          tab="文本粘贴"
        >
          <div class="input-section">
            <div class="textarea-container">
              <a-textarea
                v-model:value="inputText"
                placeholder="请粘贴完整的病历文本内容，包括入院记录、病程记录、出院小结等..."
                :rows="8"
                :max-length="50000"
                show-count
                class="enhanced-text-input"
                :auto-size="{ minRows: 8, maxRows: 20 }"
              />
            </div>
            <div class="input-tips">
              <a-alert
                message="输入提示"
                description="请粘贴包含患者基本信息、入院记录、病程记录、出院记录等完整病历内容的文本。AI将自动识别和分类不同的文书类型。"
                type="info"
                show-icon
              />
            </div>
          </div>
        </a-tab-pane>

        <!-- 文件上传 -->
        <a-tab-pane
          key="upload"
          tab="文件上传"
        >
          <div class="upload-section">
            <a-upload-dragger
              v-model:file-list="uploadFileList"
              :before-upload="beforeUpload"
              accept=".txt,.doc,.docx,.pdf"
              :multiple="false"
              :show-upload-list="false"
              @change="handleFileUpload"
            >
              <p class="ant-upload-drag-icon">
                <InboxOutlined />
              </p>
              <p class="ant-upload-text">
                点击或拖拽文件到此区域上传
              </p>
              <p class="ant-upload-hint">
                支持 .txt, .doc, .docx, .pdf 格式的病历文档
              </p>
            </a-upload-dragger>

            <!-- 备用PDF解析工具 -->
            <div class="alternative-upload-section mt-4">
              <a-divider>
                <span class="text-sm text-gray-500">
                  <FileTextOutlined class="mr-1" />
                  备用上传方式
                </span>
              </a-divider>
              <div class="alternative-upload-content">
                <div class="mb-3">
                  <a-alert
                    message="如果上方的拖拽上传遇到问题，可以使用下面的备用方式"
                    type="info"
                    show-icon
                    :closable="false"
                    class="text-sm"
                  />
                </div>
                <a-space
                  direction="vertical"
                  class="w-full"
                >
                  <a-space>
                    <input
                      ref="debugFileInput"
                      type="file"
                      accept=".pdf,.txt,.doc,.docx"
                      style="display: none"
                      @change="handleDebugFileSelect"
                    >
                    <a-button
                      type="default"
                      :loading="isParsingFile"
                      :disabled="isParsingFile"
                      @click="triggerDebugFileSelect"
                    >
                      <template #icon>
                        <FileTextOutlined />
                      </template>
                      选择文件
                    </a-button>
                    <a-button
                      v-if="debugSelectedFile"
                      type="primary"
                      :loading="isParsingFile"
                      :disabled="isParsingFile"
                      @click="handleDebugParsePDF"
                    >
                      <template #icon>
                        <RobotOutlined />
                      </template>
                      解析文件
                    </a-button>
                  </a-space>
                  <div
                    v-if="debugSelectedFile"
                    class="selected-file-info"
                  >
                    <a-descriptions
                      size="small"
                      :column="1"
                      bordered
                    >
                      <a-descriptions-item label="文件名">
                        {{ debugSelectedFile.name }}
                      </a-descriptions-item>
                      <a-descriptions-item label="文件大小">
                        {{ formatFileSize(debugSelectedFile.size) }}
                      </a-descriptions-item>
                      <a-descriptions-item label="文件类型">
                        {{ getFileTypeDescription(debugSelectedFile) }}
                      </a-descriptions-item>
                    </a-descriptions>
                  </div>
                </a-space>
              </div>
            </div>

            <div
              v-if="uploadedContent || isParsingFile"
              class="uploaded-preview"
            >
              <h4>文件内容预览：</h4>
              <div class="content-preview-enhanced">
                <div
                  v-if="isParsingFile"
                  class="parsing-status"
                >
                  <a-spin size="large" />
                  <span>正在解析文件内容，请稍候...</span>
                  <div class="text-sm text-gray-500 mt-2">
                    系统正在提取文档中的文本和医疗信息
                  </div>
                </div>
                <div
                  v-else
                  class="parsed-content"
                >
                  <pre class="whitespace-pre-wrap">{{ uploadedContent }}</pre>
                </div>
              </div>
            </div>
          </div>
        </a-tab-pane>

        <!-- 批量导入 -->
        <a-tab-pane
          key="batch"
          tab="批量导入"
        >
          <div class="batch-section">
            <a-upload-dragger
              v-model:file-list="batchFileList"
              :before-upload="beforeBatchUpload"
              accept=".zip,.rar"
              :multiple="false"
              @change="handleBatchUpload"
            >
              <p class="ant-upload-drag-icon">
                <FolderOpenOutlined />
              </p>
              <p class="ant-upload-text">
                上传包含多个病历文件的压缩包
              </p>
              <p class="ant-upload-hint">
                支持 .zip, .rar 格式，包内可包含多个病历文档
              </p>
            </a-upload-dragger>

            <div
              v-if="batchFiles.length > 0"
              class="batch-preview"
            >
              <h4>检测到 {{ batchFiles.length }} 个病历文件：</h4>
              <a-list
                size="small"
                :data-source="batchFiles"
              >
                <template #renderItem="{ item }">
                  <a-list-item>
                    <a-list-item-meta>
                      <template #title>
                        {{ item.name }}
                      </template>
                      <template #description>
                        大小: {{ formatFileSize(item.size) }} | 类型: {{ item.type }}
                      </template>
                    </a-list-item-meta>
                  </a-list-item>
                </template>
              </a-list>
            </div>
          </div>
        </a-tab-pane>
      </a-tabs>

      <div class="step-actions">
        <a-space>
          <a-button @click="handleCancel">
            取消
          </a-button>
          <a-button
            type="primary"
            :disabled="!canProceedToNext"
            :loading="processing"
            @click="handleStartParsing"
          >
            <template #icon>
              <RobotOutlined />
            </template>
            开始AI解析
          </a-button>
        </a-space>
      </div>
    </a-card>

    <!-- 步骤2: AI智能解析 -->
    <a-card
      v-if="currentStep === 1"
      title="步骤2: AI智能解析"
      class="step-card"
    >
      <div class="parsing-section">
        <div class="parsing-progress">
          <a-spin
            size="large"
            :spinning="parsing"
          >
            <div class="parsing-content">
              <div class="parsing-icon">
                <RobotOutlined />
              </div>
              <h3>AI正在解析病历内容...</h3>
              <p>正在使用大语言模型分析和抽取病历信息，请稍候</p>

              <a-progress
                :percent="parsingProgress"
                :status="parsing ? 'active' : 'success'"
                :show-info="true"
              />

              <div class="parsing-steps">
                <div
                  class="parsing-step"
                  :class="{ active: parsingStep >= 1, completed: parsingStep > 1 }"
                >
                  <CheckCircleOutlined v-if="parsingStep > 1" />
                  <LoadingOutlined v-else-if="parsingStep === 1" />
                  <span>文本预处理和清洗</span>
                </div>
                <div
                  class="parsing-step"
                  :class="{ active: parsingStep >= 2, completed: parsingStep > 2 }"
                >
                  <CheckCircleOutlined v-if="parsingStep > 2" />
                  <LoadingOutlined v-else-if="parsingStep === 2" />
                  <span>识别文书类型和结构</span>
                </div>
                <div
                  class="parsing-step"
                  :class="{ active: parsingStep >= 3, completed: parsingStep > 3 }"
                >
                  <CheckCircleOutlined v-if="parsingStep > 3" />
                  <LoadingOutlined v-else-if="parsingStep === 3" />
                  <span>抽取关键信息字段</span>
                </div>
                <div
                  class="parsing-step"
                  :class="{ active: parsingStep >= 4, completed: parsingStep > 4 }"
                >
                  <CheckCircleOutlined v-if="parsingStep > 4" />
                  <LoadingOutlined v-else-if="parsingStep === 4" />
                  <span>生成结构化数据</span>
                </div>
              </div>
            </div>
          </a-spin>
        </div>
      </div>
    </a-card>

    <!-- 步骤3: 确认和修正 -->
    <a-card
      v-if="currentStep === 2"
      title="步骤3: 确认和修正解析结果"
      class="step-card"
    >
      <div class="review-section">
        <a-alert
          message="AI解析完成"
          :description="`成功解析出 ${extractedData && extractedData.documents ? extractedData.documents.length : 0} 个文书，请仔细检查并修正以下信息`"
          type="success"
          show-icon
          class="review-alert"
        />

        <a-tabs v-model:active-key="reviewTab">
          <!-- 基本信息 -->
          <a-tab-pane
            key="basic"
            tab="基本信息"
          >
            <div class="review-form">
              <a-row :gutter="16">
                <a-col :span="12">
                  <a-form-item label="病历编号">
                    <a-input
                      v-model:value="extractedData.recordNumber"
                      placeholder="自动生成"
                      disabled
                    />
                  </a-form-item>
                </a-col>
                <a-col :span="12">
                  <a-form-item label="患者姓名">
                    <a-input
                      v-model:value="extractedData.patientName"
                      :class="{ 'ai-extracted': extractedData.patientName }"
                    />
                    <div
                      v-if="extractedData.patientName"
                      class="ai-confidence"
                    >
                      <RobotOutlined /> AI识别 (置信度: 95%)
                    </div>
                  </a-form-item>
                </a-col>
              </a-row>

              <a-row :gutter="16">
                <a-col :span="12">
                  <a-form-item label="出院科室">
                    <a-select
                      v-model:value="extractedData.department"
                      :class="{ 'ai-extracted': extractedData.department }"
                    >
                      <a-select-option value="内科">
                        内科
                      </a-select-option>
                      <a-select-option value="外科">
                        外科
                      </a-select-option>
                      <a-select-option value="妇产科">
                        妇产科
                      </a-select-option>
                      <a-select-option value="儿科">
                        儿科
                      </a-select-option>
                      <a-select-option value="急诊科">
                        急诊科
                      </a-select-option>
                    </a-select>
                    <div
                      v-if="extractedData.department"
                      class="ai-confidence"
                    >
                      <RobotOutlined /> AI识别 (置信度: 88%)
                    </div>
                  </a-form-item>
                </a-col>
                <a-col :span="12">
                  <a-form-item label="主诊断">
                    <a-input
                      v-model:value="extractedData.primaryDiagnosis"
                      :class="{ 'ai-extracted': extractedData.primaryDiagnosis }"
                    />
                    <div
                      v-if="extractedData.primaryDiagnosis"
                      class="ai-confidence"
                    >
                      <RobotOutlined /> AI识别 (置信度: 92%)
                    </div>
                  </a-form-item>
                </a-col>
              </a-row>

              <a-form-item label="主要手术及操作">
                <a-textarea
                  v-model:value="extractedData.majorSurgery"
                  :rows="3"
                  :class="{ 'ai-extracted': extractedData.majorSurgery }"
                />
                <div
                  v-if="extractedData.majorSurgery"
                  class="ai-confidence"
                >
                  <RobotOutlined /> AI识别 (置信度: 85%)
                </div>
              </a-form-item>
            </div>
          </a-tab-pane>

          <!-- 文书目录视图 -->
          <a-tab-pane
            key="documents"
            tab="文书目录"
          >
            <MedicalDocumentTree
              :documents="treeDocuments"
              :original-text="originalFullText"
            />
          </a-tab-pane>

          <!-- 解析统计 -->
          <a-tab-pane
            key="stats"
            tab="解析统计"
          >
            <div class="parsing-stats">
              <a-row :gutter="16">
                <a-col :span="8">
                  <a-statistic
                    title="识别文书数量"
                    :value="extractedData.documents ? extractedData.documents.length : 0"
                    :value-style="{ color: '#1890ff' }"
                  >
                    <template #prefix>
                      <FileTextOutlined />
                    </template>
                  </a-statistic>
                </a-col>
                <a-col :span="8">
                  <a-statistic
                    title="抽取字段数量"
                    :value="extractedFieldsCount"
                    :value-style="{ color: '#52c41a' }"
                  >
                    <template #prefix>
                      <DatabaseOutlined />
                    </template>
                  </a-statistic>
                </a-col>
                <a-col :span="8">
                  <a-statistic
                    title="平均置信度"
                    :value="averageConfidence"
                    suffix="%"
                    :value-style="{ color: '#722ed1' }"
                  >
                    <template #prefix>
                      <TrophyOutlined />
                    </template>
                  </a-statistic>
                </a-col>
              </a-row>

              <a-divider />

              <div class="confidence-breakdown">
                <h4>字段置信度详情：</h4>
                <div class="confidence-items">
                  <div class="confidence-item">
                    <span>患者姓名</span>
                    <a-progress
                      :percent="95"
                      size="small"
                    />
                  </div>
                  <div class="confidence-item">
                    <span>主诊断</span>
                    <a-progress
                      :percent="92"
                      size="small"
                    />
                  </div>
                  <div class="confidence-item">
                    <span>出院科室</span>
                    <a-progress
                      :percent="88"
                      size="small"
                    />
                  </div>
                  <div class="confidence-item">
                    <span>手术信息</span>
                    <a-progress
                      :percent="85"
                      size="small"
                    />
                  </div>
                </div>
              </div>
            </div>
          </a-tab-pane>
        </a-tabs>
      </div>

      <div class="step-actions">
        <a-space>
          <a-button @click="handleBackToInput">
            返回修改
          </a-button>
          <a-button
            :loading="parsing"
            @click="handleReparse"
          >
            <template #icon>
              <ReloadOutlined />
            </template>
            重新解析
          </a-button>
          <a-button
            type="primary"
            :loading="importing"
            @click="handleConfirmImport"
          >
            <template #icon>
              <CheckOutlined />
            </template>
            确认导入
          </a-button>
        </a-space>
      </div>
    </a-card>

    <!-- 步骤4: 完成导入 -->
    <a-card
      v-if="currentStep === 3"
      title="导入完成"
      class="step-card"
    >
      <div class="success-section">
        <a-result
          status="success"
          title="病历导入成功！"
          :sub-title="`成功导入 ${importedCount} 条病历记录，包含 ${importedDocumentsCount} 个文书`"
        >
          <template #extra>
            <a-space>
              <a-button
                type="primary"
                @click="handleViewImported"
              >
                查看导入的病历
              </a-button>
              <a-button @click="handleImportAnother">
                继续导入其他病历
              </a-button>
              <a-button @click="handleBackToList">
                返回病历列表
              </a-button>
            </a-space>
          </template>
        </a-result>
      </div>
    </a-card>

    <!-- API配置弹窗 -->
    <a-modal
      v-model:open="showApiConfig"
      title="大模型API配置"
      width="1000px"
      :footer="null"
      :destroy-on-close="true"
    >
      <LLMApiConfigDatabase
        @config-updated="handleApiConfigUpdated"
        @close-modal="handleCloseApiConfig"
      />
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, onUnmounted, defineAsyncComponent } from 'vue'
import { useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import type { UploadFile } from 'ant-design-vue'
import {
  InboxOutlined,
  FolderOpenOutlined,
  RobotOutlined,
  CheckCircleOutlined,
  LoadingOutlined,
  FileTextOutlined,
  DatabaseOutlined,
  TrophyOutlined,
  ReloadOutlined,
  CheckOutlined,
  SettingOutlined,
} from '@ant-design/icons-vue'
import type { UserLLMConfig } from '@/services/llmConfigService'
import type { ExtractedDocument as TreeExtractedDocument } from '@/services/llmService'
import type {
  ExtractedMedicalData as PersistedExtractedMedicalData,
  ExtractedDocument as PersistedExtractedDocument,
  DocumentType as PersistedDocumentType,
} from '@/types/medical'
import {
  getGroupedDocumentTypeOptions,
  getDocumentTypeLabel,
  getDocumentTypeColor,
  inferDocumentType,
} from '@/utils/documentTypeUtils'

const router = useRouter()
const LLMApiConfigDatabase = defineAsyncComponent(
  () => import('@/components/LLMApiConfigDatabase.vue'),
)
const MedicalDocumentTree = defineAsyncComponent(
  () => import('@/components/MedicalDocumentTree.vue'),
)

let llmServicePromise: Promise<typeof import('@/services/llmServiceNew')> | null = null
let supabaseMedicalRecordServicePromise: Promise<
  typeof import('@/services/supabaseMedicalRecordService')
> | null = null
let documentParserPromise: Promise<typeof import('@/utils/documentParser')> | null = null

const getLLMService = async () => {
  const module = await (llmServicePromise ??= import('@/services/llmServiceNew'))
  return module.llmService
}

const getSupabaseMedicalRecordService = async () => {
  const module = await (supabaseMedicalRecordServicePromise ??= import(
    '@/services/supabaseMedicalRecordService'
  ))
  return module.supabaseMedicalRecordService
}

const getDocumentParser = async () => {
  const module = await (documentParserPromise ??= import('@/utils/documentParser'))
  return module.DocumentParser
}

interface ExtractedDocumentPosition {
  startMarker?: string
  endMarker?: string
  startIndex?: number
  endIndex?: number
  fullContent?: string
}

interface ExtractedDocumentItem {
  id: string
  type: PersistedDocumentType | string
  title: string
  content: string
  confidence?: number
  extractedAt?: Date
  position?: ExtractedDocumentPosition
}

interface ExtractedMedicalData {
  recordNumber: string
  patientName: string
  patientAge?: number
  patientGender?: string
  department: string
  primaryDiagnosis: string
  secondaryDiagnosis?: string[]
  majorSurgery: string
  documents: ExtractedDocumentItem[]
  confidence?: number
}

interface BatchFileItem {
  name: string
  size: number
  type: string
}

interface UploadInfoLike {
  fileList: UploadFile[]
}

// 响应式数据
const currentStep = ref(0)
const inputMethod = ref('paste')
const inputText = ref('')
const uploadFileList = ref<UploadFile[]>([])
const batchFileList = ref<UploadFile[]>([])
const uploadedContent = ref('')
const uploadedFile = ref<File | null>(null)
const isParsingFile = ref(false)
const batchFiles = ref<BatchFileItem[]>([])
const processing = ref(false)
const parsing = ref(false)
const importing = ref(false)
const parsingProgress = ref(0)
const parsingStep = ref(0)
const reviewTab = ref('basic')
const importedCount = ref(0)
const importedDocumentsCount = ref(0)
const showApiConfig = ref(false)
// 用于目录展开时显示原文
const originalFullText = ref('')

// 调试用的数据
const debugSelectedFile = ref<File | null>(null)
const debugFileInput = ref<HTMLInputElement | null>(null)

// 抽取的数据
const extractedData = reactive<ExtractedMedicalData>({
  recordNumber: '',
  patientName: '',
  patientAge: undefined,
  patientGender: '',
  department: '',
  primaryDiagnosis: '',
  secondaryDiagnosis: [],
  majorSurgery: '',
  documents: [],
})

// 计算属性
const canProceedToNext = computed(() => {
  if (inputMethod.value === 'paste') {
    return inputText.value.trim().length > 100
  } else if (inputMethod.value === 'upload') {
    return uploadedContent.value.length > 0
  } else if (inputMethod.value === 'batch') {
    return batchFiles.value.length > 0
  }
  return false
})

const extractedFieldsCount = computed(() => {
  let count = 0
  if (extractedData.patientName) count++
  if (extractedData.department) count++
  if (extractedData.primaryDiagnosis) count++
  if (extractedData.majorSurgery) count++
  count += extractedData.documents ? extractedData.documents.length : 0
  return count
})

const averageConfidence = computed(() => {
  // 模拟计算平均置信度
  return 89
})
const treeDocuments = computed<TreeExtractedDocument[]>(
  () => extractedData.documents as unknown as TreeExtractedDocument[],
)

// 获取分组的文书类型选项
const documentTypeOptions = computed(() => {
  return getGroupedDocumentTypeOptions()
})

// 生命周期
onMounted(async () => {
  generateRecordNumber()

  // 尝试从数据库加载默认配置
  try {
    const llmService = await getLLMService()
    const success = await llmService.loadConfigFromDatabase('default')
    if (success) {
      console.log('已加载默认LLM配置')
    } else {
      console.log('未找到默认配置，使用内置配置')
      loadAndApplyApiConfig() // 回退到原有的配置加载方式
    }
  } catch (error) {
    console.error('加载数据库配置失败，使用内置配置:', error)
    loadAndApplyApiConfig()
  }

  // 监听全局配置更新事件
  window.addEventListener('llm-config-updated', handleGlobalConfigUpdate)
})

onUnmounted(() => {
  // 清理事件监听器
  window.removeEventListener('llm-config-updated', handleGlobalConfigUpdate)
})

// 方法定义
const generateRecordNumber = () => {
  const now = new Date()
  const year = now.getFullYear()
  const month = String(now.getMonth() + 1).padStart(2, '0')
  const day = String(now.getDate()).padStart(2, '0')
  const random = Math.floor(Math.random() * 1000)
    .toString()
    .padStart(3, '0')
  extractedData.recordNumber = `MR${year}${month}${day}${random}`
}

const handleInputMethodChange = (key: string) => {
  inputMethod.value = key
  // 清空其他输入方式的数据
  if (key !== 'paste') inputText.value = ''
  if (key !== 'upload') {
    uploadFileList.value = []
    uploadedContent.value = ''
  }
  if (key !== 'batch') {
    batchFileList.value = []
    batchFiles.value = []
  }
}

const beforeUpload = (file: File) => {
  console.log('beforeUpload 被调用:', file.name, file.type, file.size)

  // 验证文件类型
  const isValidType = [
    'application/pdf',
    'application/msword',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'text/plain',
  ].includes(file.type)
  if (!isValidType) {
    message.error('只支持 PDF、Word、文本文件格式')
    return false
  }

  // 验证文件大小
  const isLt10M = file.size / 1024 / 1024 < 10
  if (!isLt10M) {
    message.error('文件大小不能超过 10MB')
    return false
  }

  console.log('文件验证通过')
  return false // 阻止自动上传，使用 @change 事件处理
}

const beforeBatchUpload = () => {
  return false // 阻止自动上传
}

const handleFileUpload = async (info: UploadInfoLike) => {
  console.log('🔥 handleFileUpload 被调用了！', info)
  const file = info.fileList[0] && info.fileList[0].originFileObj
  console.log('📁 提取的文件对象:', file)
  if (file) {
    // 防止重复处理
    if (isParsingFile.value) {
      console.log('正在解析中，忽略重复请求')
      return
    }

    // 保存文件对象供后续处理
    uploadedFile.value = file

    // 检查文件类型是否支持
    const allowedTypes = [
      'text/plain',
      'application/pdf',
      'application/msword',
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    ]
    const allowedExtensions = ['.txt', '.pdf', '.doc', '.docx']

    const isValidType =
      allowedTypes.includes(file.type) ||
      allowedExtensions.some((ext) => file.name.toLowerCase().endsWith(ext))

    if (!isValidType) {
      message.error(`不支持的文件格式: ${file.name}`)
      uploadedContent.value = `不支持的文件类型: ${file.name}

请上传以下格式的文件：
- .txt (纯文本文件)
- .pdf (PDF文档)
- .doc/.docx (Word文档)`
      return
    }

    // 检查文件大小 (10MB限制)
    if (file.size > 10 * 1024 * 1024) {
      message.error('文件大小不能超过10MB')
      return
    }

    const fileTypeDesc = getFileTypeDescription(file)

    // 开始解析
    isParsingFile.value = true
    uploadedContent.value = `📄 正在解析文件: ${file.name}
文件大小: ${formatFileSize(file.size)}
文件类型: ${fileTypeDesc}

⏳ 正在处理中，请稍候...`

    try {
      console.log('开始处理文件:', file.name, '类型:', file.type, '大小:', file.size)

      if (file.type === 'application/pdf' || file.name.toLowerCase().endsWith('.pdf')) {
        // PDF文件通过后端API解析
        console.log('调用PDF解析函数')
        await parsePDFFile(file)
      } else if (file.type === 'text/plain' || file.name.toLowerCase().endsWith('.txt')) {
        // 文本文件直接读取
        await parseTextFile(file)
      } else {
        // 其他文件类型使用原有的DocumentParser
        const DocumentParser = await getDocumentParser()
        const parseResult = await DocumentParser.parseDocument(file)

        if (parseResult.success) {
          uploadedContent.value = parseResult.content

          const metadata = parseResult.metadata
          let successMsg = `${fileTypeDesc}解析成功！`
          if (metadata && metadata.pages) {
            successMsg += ` 共${metadata.pages}页`
          }
          if (metadata && metadata.wordCount) {
            successMsg += ` ${metadata.wordCount}字`
          }

          message.success(successMsg)
        } else {
          throw new Error(parseResult.error)
        }
      }
    } catch (error) {
      console.error('文档解析异常:', error)
      let errorMessage = error instanceof Error ? error.message : '未知错误'

      // 特殊处理网络错误
      if (error instanceof TypeError && error.message.includes('NetworkError')) {
        errorMessage = '网络连接失败，请检查网络连接'
      } else if (error instanceof DOMException && error.name === 'AbortError') {
        errorMessage = '请求超时，请重试'
      } else if (error instanceof TypeError && error.message.includes('fetch')) {
        errorMessage = '无法连接到服务器，请检查服务是否正常运行'
      }

      uploadedContent.value = `【解析失败】

【文件信息】
- 文件名: ${file.name}
- 文件大小: ${formatFileSize(file.size)}
- 文件类型: ${getFileTypeDescription(file)}

【错误详情】
${errorMessage}

【解决建议】
${getErrorSuggestions(errorMessage)}

【请尝试】
1. 重新上传文件
2. 检查文件是否损坏
3. 尝试其他格式的文件
4. 联系技术支持`

      message.error(`文档解析失败: ${errorMessage}`)
    } finally {
      isParsingFile.value = false
    }
  }
}

const handleBatchUpload = (info: unknown) => {
  void info
  // 模拟批量文件处理
  batchFiles.value = [
    { name: '患者张三病历.txt', size: 15420, type: 'text/plain' },
    { name: '患者李四病历.doc', size: 23680, type: 'application/msword' },
    { name: '患者王五病历.txt', size: 18950, type: 'text/plain' },
  ]
}

// 备用文件选择处理
const handleDebugFileSelect = (event: Event) => {
  const target = event.target as HTMLInputElement
  const file = target.files && target.files[0]
  if (file) {
    console.log('📁 备用上传：选择了文件', file.name, file.type, file.size)

    // 检查文件类型
    const allowedTypes = [
      'text/plain',
      'application/pdf',
      'application/msword',
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    ]
    const allowedExtensions = ['.txt', '.pdf', '.doc', '.docx']
    const isValidType =
      allowedTypes.includes(file.type) ||
      allowedExtensions.some((ext) => file.name.toLowerCase().endsWith(ext))

    if (!isValidType) {
      message.error(`不支持的文件格式: ${file.name}`)
      return
    }

    // 检查文件大小 (10MB限制)
    if (file.size > 10 * 1024 * 1024) {
      message.error('文件大小不能超过10MB')
      return
    }

    debugSelectedFile.value = file
    uploadedFile.value = file // 同步到主要的文件变量
    message.success(`已选择文件: ${file.name}`)
  }
}

const triggerDebugFileSelect = () => {
  debugFileInput.value?.click()
}

// 备用文件解析
const handleDebugParsePDF = async () => {
  if (!debugSelectedFile.value) {
    message.error('请先选择一个文件')
    return
  }

  console.log('📁 备用上传：开始解析文件', debugSelectedFile.value.name)

  try {
    isParsingFile.value = true
    const fileTypeDesc = getFileTypeDescription(debugSelectedFile.value)

    uploadedContent.value = `📁 备用上传：正在解析文件

📄 文件信息:
- 文件名: ${debugSelectedFile.value.name}
- 文件大小: ${formatFileSize(debugSelectedFile.value.size)}
- 文件类型: ${fileTypeDesc}

⏳ 正在处理中，请稍候...`

    // 根据文件类型选择解析方法
    if (
      debugSelectedFile.value.type === 'application/pdf' ||
      debugSelectedFile.value.name.toLowerCase().endsWith('.pdf')
    ) {
      await parsePDFFile(debugSelectedFile.value)
    } else if (
      debugSelectedFile.value.type === 'text/plain' ||
      debugSelectedFile.value.name.toLowerCase().endsWith('.txt')
    ) {
      await parseTextFile(debugSelectedFile.value)
    } else {
      // 其他文件类型使用DocumentParser
      const DocumentParser = await getDocumentParser()
      const parseResult = await DocumentParser.parseDocument(debugSelectedFile.value)
      if (parseResult.success) {
        uploadedContent.value = parseResult.content
        message.success(`${fileTypeDesc}解析成功！`)
      } else {
        throw new Error(parseResult.error)
      }
    }

    message.success('文件解析完成！')
  } catch (error) {
    console.error('备用上传解析失败:', error)
    let errorMessage = error instanceof Error ? error.message : '未知错误'

    uploadedContent.value = `❌ 文件解析失败

📄 文件信息:
- 文件名: ${debugSelectedFile.value.name}
- 文件大小: ${formatFileSize(debugSelectedFile.value.size)}
- 文件类型: ${getFileTypeDescription(debugSelectedFile.value)}

🔍 错误详情:
${errorMessage}

💡 解决建议:
${getErrorSuggestions(errorMessage)}

🔄 您可以尝试:
1. 重新选择文件
2. 检查文件是否损坏
3. 尝试其他格式的文件`

    message.error(`文件解析失败: ${errorMessage}`)
  } finally {
    isParsingFile.value = false
  }
}

const formatFileSize = (bytes: number) => {
  if (bytes === 0) return '0 Bytes'
  const k = 1024
  const sizes = ['Bytes', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
}

// 获取文件类型描述
const getFileTypeDescription = (file: File) => {
  if (file.type === 'application/pdf' || file.name.toLowerCase().endsWith('.pdf')) {
    return 'PDF文档'
  } else if (file.type === 'text/plain' || file.name.toLowerCase().endsWith('.txt')) {
    return '文本文件'
  } else if (
    file.type.includes('msword') ||
    file.name.toLowerCase().endsWith('.doc') ||
    file.name.toLowerCase().endsWith('.docx')
  ) {
    return 'Word文档'
  }
  return '文档'
}

// 获取错误建议
const getErrorSuggestions = (errorMessage: string) => {
  if (errorMessage.includes('用户未登录')) {
    return '请刷新页面重新登录后再试'
  } else if (
    errorMessage.includes('Not authenticated') ||
    errorMessage.includes('401') ||
    errorMessage.includes('403')
  ) {
    return '认证失败，请检查登录状态或刷新页面重新登录'
  } else if (errorMessage.includes('网络连接失败') || errorMessage.includes('NetworkError')) {
    return '网络连接问题，请检查网络连接状态，确保前后端服务都在运行'
  } else if (
    errorMessage.includes('请求超时') ||
    errorMessage.includes('timeout') ||
    errorMessage.includes('AbortError')
  ) {
    return '请求处理时间过长，可能是文件过大或服务器繁忙，请稍后重试'
  } else if (errorMessage.includes('无法连接到服务器') || errorMessage.includes('fetch')) {
    return '服务器连接失败，请确认后端服务正在运行，或联系技术支持'
  } else if (errorMessage.includes('网络') || errorMessage.includes('Network')) {
    return '网络连接问题，请检查网络连接后重试'
  } else if (errorMessage.includes('文件格式') || errorMessage.includes('format')) {
    return '文件格式不支持，请确保上传的是有效的PDF、Word或文本文件'
  } else if (errorMessage.includes('文件大小') || errorMessage.includes('size')) {
    return '文件过大，请上传小于10MB的文件'
  } else if (errorMessage.includes('解析失败') || errorMessage.includes('parse')) {
    return '文件内容解析失败，可能是文件损坏或格式异常'
  } else {
    return '遇到未知错误，建议重试或联系技术支持'
  }
}

// 解析PDF文件
const parsePDFFile = async (file: File) => {
  console.log('PDF解析函数开始，文件:', file.name, '大小:', file.size)
  try {
    // 使用ApiService来处理请求，确保token管理一致性
    const formData = new FormData()
    formData.append('file', file)
    formData.append('options', JSON.stringify({}))

    console.log('FormData创建完成，文件已添加')

    // PDF解析不需要API token，只需要用户已登录即可

    // 创建AbortController来处理请求取消
    const controller = new AbortController()
    const timeoutId = setTimeout(() => controller.abort(), 60000) // 60秒超时

    // 尝试直接调用后端，如果代理有问题的话
    const apiUrl =
      window.location.hostname === 'localhost'
        ? 'http://localhost:8001/api/parse-medical-file'
        : '/api/parse-medical-file'

    console.log('调用API:', apiUrl)
    console.log('发送请求...')
    const response = await fetch(apiUrl, {
      method: 'POST',
      body: formData,
      signal: controller.signal,
    })

    clearTimeout(timeoutId)
    console.log('收到响应:', response.status, response.statusText)

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}))
      throw new Error(errorData.detail || `HTTP ${response.status}: ${response.statusText}`)
    }

    const result = await response.json()

    if (result.success && result.data) {
      const data = result.data
      const content = data.content || ''
      const method = data.method || '未知方法'
      const pages = data.pages || 0
      const medicalInfo = data.medical_info || {}

      // 构建显示内容
      let displayContent = `✅ PDF文档解析成功！

📄 文件信息:
- 文件名: ${file.name}
- 文件大小: ${formatFileSize(file.size)}
- 页数: ${pages}页
- 解析方法: ${method}
- 内容长度: ${content.length}字符

`

      // 如果提取到医疗信息，显示它们
      if (Object.keys(medicalInfo).some((key) => medicalInfo[key])) {
        displayContent += `🏥 自动提取的医疗信息:
`
        Object.entries(medicalInfo).forEach(([key, value]) => {
          if (value) {
            const keyMap: Record<string, string> = {
              patient_name: '患者姓名',
              patient_age: '年龄',
              patient_gender: '性别',
              department: '科室',
              diagnosis: '诊断',
              vital_signs: '生命体征',
            }
            displayContent += `- ${keyMap[key] || key}: ${Array.isArray(value) ? value.join(', ') : value}
`
          }
        })
        displayContent += `
`
      } else {
        displayContent += `ℹ️ 未检测到结构化医疗信息，请在下方查看完整文档内容

`
      }

      displayContent += `📝 文档内容预览:
${content.length > 2000 ? content.substring(0, 2000) + '\n\n...(内容已截断，完整内容将在AI解析时使用)' : content}

💡 提示: 您现在可以点击"开始AI解析"按钮，让系统智能提取病历信息！`

      uploadedContent.value = displayContent
      message.success(`PDF文件解析成功！共${pages}页，内容长度${content.length}字符`)
    } else {
      throw new Error(result.error || 'PDF解析失败')
    }
  } catch (error) {
    console.error('PDF解析失败:', error)
    throw error
  }
}

// 解析文本文件
const parseTextFile = async (file: File) => {
  return new Promise<string>((resolve, reject) => {
    const reader = new FileReader()

    reader.onload = (e) => {
      try {
        const content = (e.target && (e.target as any).result) as string
        uploadedContent.value = content
        message.success(`文本文件读取成功！内容长度${content.length}字符`)
        resolve(content)
      } catch (error) {
        reject(error)
      }
    }

    reader.onerror = () => {
      reject(new Error('文件读取失败'))
    }

    reader.readAsText(file, 'UTF-8')
  })
}

const handleStartParsing = async () => {
  processing.value = true
  parsing.value = true
  currentStep.value = 1
  parsingProgress.value = 0
  parsingStep.value = 0

  try {
    // 获取输入内容
    let textToParse = ''
    let fileToProcess: File | null = null
    let inputMethodUsed: 'paste' | 'upload' | 'batch' = 'paste'

    if (inputMethod.value === 'paste') {
      textToParse = inputText.value
      inputMethodUsed = 'paste'
    } else if (inputMethod.value === 'upload') {
      inputMethodUsed = 'upload'

      // 检查是否为PDF文件，需要通过后端处理
      if (uploadedFile.value && (await getDocumentParser()).isPDFFile(uploadedFile.value)) {
        fileToProcess = uploadedFile.value
        console.log('准备通过后端处理PDF文件:', fileToProcess.name)
      } else {
        // 其他文件类型直接使用已解析的内容
        textToParse = uploadedContent.value
      }
    } else if (inputMethod.value === 'batch') {
      // 批量处理暂时使用第一个文件的内容作为示例
      textToParse = '患者张三，男，65岁，因"头晕、头痛3天"入院...'
      inputMethodUsed = 'batch'
    }

    // 验证输入
    if (!textToParse.trim() && !fileToProcess) {
      throw new Error('没有可解析的文本内容或文件')
    }

    // 显示解析进度
    await simulateAIParsing()

    // 确保在使用前加载默认配置（用户级优先，回退全局）
    const llmService = await getLLMService()
    await llmService.loadConfigFromDatabase('default')

    // 调用LLM服务进行解析
    let parseResult
    if (fileToProcess) {
      // 处理PDF文件 - 通过后端API
      console.log('通过后端API解析PDF文件:', fileToProcess.name)
      parseResult = await llmService.parseMedicalFileViaBackend(fileToProcess, {
        extractPatientInfo: true,
        extractDiagnosis: true,
        extractSurgeryInfo: true,
        classifyDocuments: true,
        confidenceThreshold: 0.7,
      })
    } else {
      // 处理文本内容
      console.log('开始AI解析文本内容，长度:', textToParse.length)
      parseResult = await llmService.parseMedicalText(textToParse, {
        extractPatientInfo: true,
        extractDiagnosis: true,
        extractSurgeryInfo: true,
        classifyDocuments: true,
        confidenceThreshold: 0.7,
      })
    }

    if (!parseResult.success || !parseResult.data) {
      throw new Error(parseResult.error || 'AI解析失败')
    }

    // 保存原始全文，供目录视图展开时使用
    originalFullText.value = parseResult.data.content || ''

    // 更新解析结果（用于当前页小结展示）
    const data = parseResult.data
    Object.assign(extractedData, {
      patientName: data.patientName || '',
      department: data.department || '',
      primaryDiagnosis: data.primaryDiagnosis || '',
      majorSurgery: data.majorSurgery || '',
      documents: data.documents
        ? data.documents.map((doc) => ({
            id: doc.id,
            type: doc.type,
            title: doc.title,
            content: doc.content,
            confidence: doc.confidence,
          }))
        : [],
    })

    // 写入全局store与session，并跳转到结果页
    const { useLLMParseStore } = await import('@/stores/llmParse')
    const store = useLLMParseStore()
    store.setResult(parseResult)
    await router.push('/dashboard/llm-result')

    // 成本提示：显示本次解析的 token 用量与节省估算（结果页里也会展示）
    const tokensUsed = parseResult.tokensUsed || 0
    if (tokensUsed > 0) {
      const baselineTokens =
        (parseResult.data?.content
          ? Math.round(parseResult.data.content.length / 4)
          : Math.round((textToParse || '').length / 4)) + 1000
      const saved = Math.max(0, baselineTokens - tokensUsed)
      const savedPct = baselineTokens > 0 ? Math.round((saved / baselineTokens) * 100) : 0
      message.info(`本次LLM用量≈${tokensUsed} tokens，较旧方案预计节省≈${savedPct}%`, 6)
    }

    message.success('AI解析完成！')
  } catch (error) {
    console.error('AI解析失败:', error)
    message.error(error instanceof Error ? error.message : '解析失败，请重试')
    currentStep.value = 0
  } finally {
    processing.value = false
    parsing.value = false
  }
}

const simulateAIParsing = async () => {
  const steps = [
    { step: 1, progress: 25, delay: 1000 },
    { step: 2, progress: 50, delay: 1500 },
    { step: 3, progress: 75, delay: 2000 },
    { step: 4, progress: 100, delay: 1000 },
  ]

  for (const { step, progress, delay } of steps) {
    parsingStep.value = step
    parsingProgress.value = progress
    await new Promise((resolve) => setTimeout(resolve, delay))
  }
}

const handleBackToInput = () => {
  currentStep.value = 0
}

const handleReparse = async () => {
  await handleStartParsing()
}

const handleConfirmImport = async () => {
  importing.value = true
  try {
    // 获取原始文本
    let rawText = ''
    let inputMethodUsed: 'paste' | 'upload' | 'batch' = 'paste'

    if (inputMethod.value === 'paste') {
      rawText = inputText.value
      inputMethodUsed = 'paste'
    } else if (inputMethod.value === 'upload') {
      rawText = uploadedContent.value
      inputMethodUsed = 'upload'
    } else if (inputMethod.value === 'batch') {
      rawText = '批量导入的病历文本内容...'
      inputMethodUsed = 'batch'
    }

    // 构建ExtractedMedicalData对象
    const extractedMedicalData: PersistedExtractedMedicalData = {
      recordNumber: extractedData.recordNumber,
      patientName: extractedData.patientName,
      patientAge: extractedData.patientAge,
      patientGender: extractedData.patientGender,
      department: extractedData.department,
      primaryDiagnosis: extractedData.primaryDiagnosis,
      secondaryDiagnosis: extractedData.secondaryDiagnosis,
      majorSurgery: extractedData.majorSurgery,
      documents: extractedData.documents
        ? extractedData.documents.map(
            (doc): PersistedExtractedDocument => ({
              id: doc.id,
              type: doc.type as PersistedDocumentType,
              title: doc.title,
              content: doc.content,
              confidence: doc.confidence ?? 0,
              extractedAt: new Date(),
              position: doc.position
                ? {
                    startMarker: doc.position.startMarker || '',
                    endMarker: doc.position.endMarker || '',
                    startIndex: doc.position.startIndex,
                    endIndex: doc.position.endIndex,
                    fullContent: doc.position.fullContent,
                  }
                : undefined,
            }),
          )
        : [],
      confidence: averageConfidence.value,
    }

    // 保存到Supabase数据库（测试表）
    const supabaseMedicalRecordService = await getSupabaseMedicalRecordService()
    const savedRecord = await supabaseMedicalRecordService.saveAIExtractionResult(
      extractedMedicalData,
      rawText,
      inputMethodUsed,
      2500,
      1250,
    )

    // 同步写入医疗文书表
    try {
      const { createDocumentsBatch } = await import('@/services/medicalDocumentApi')
      const baseText = originalFullText.value || rawText || ''
      const batch = (extractedMedicalData.documents || []).map((d, idx: number) => {
        const pos: ExtractedDocumentPosition = d.position || {}
        const si = pos.startIndex
        const ei = pos.endIndex

        let full = ''
        if (typeof si === 'number' && typeof ei === 'number' && ei > si && ei <= baseText.length) {
          full = baseText.slice(si, ei)
        } else if (pos.startMarker) {
          const startIdx = baseText.indexOf(pos.startMarker)
          if (startIdx >= 0) {
            if (pos.endMarker) {
              const after = baseText.indexOf(
                pos.endMarker,
                startIdx + String(pos.startMarker).length,
              )
              if (after > startIdx) full = baseText.slice(startIdx, after)
            }
            if (!full) full = baseText.slice(startIdx, Math.min(baseText.length, startIdx + 4000))
          }
        }
        if (!full) full = d.content || ''

        return {
          record_id: savedRecord.id,
          document_type: d.type as any,
          title: d.title || '',
          content: full,
          summary: d.content || '',
          ai_classified: true,
          ai_confidence_score: d.confidence || 0,
          position: d.position || undefined,
          sort_order: idx,
          status: 'active' as const,
        }
      })
      if (batch.length) await createDocumentsBatch(batch)
    } catch (e) {
      console.warn('写入医疗文书表失败（不中断流程）:', e)
    }

    importedCount.value = 1
    importedDocumentsCount.value = extractedData.documents ? extractedData.documents.length : 0

    // 保存记录ID用于后续查看
    localStorage.setItem('lastImportedRecordId', savedRecord.id)

    currentStep.value = 3
    message.success('病历导入成功！')
  } catch (error) {
    console.error('导入失败:', error)
    message.error(error instanceof Error ? error.message : '导入失败，请重试')
  } finally {
    importing.value = false
  }
}

const handleViewImported = () => {
  const recordId = localStorage.getItem('lastImportedRecordId')
  if (recordId) {
    router.push(`/dashboard/medical-records/${recordId}`)
  } else {
    router.push('/dashboard/medical-records')
  }
}

const handleImportAnother = () => {
  // 重置所有状态
  currentStep.value = 0
  inputText.value = ''
  uploadFileList.value = []
  uploadedContent.value = ''
  batchFiles.value = []
  Object.assign(extractedData, {
    recordNumber: '',
    patientName: '',
    department: '',
    primaryDiagnosis: '',
    majorSurgery: '',
    documents: [],
  })
  generateRecordNumber()
}

const handleBackToList = () => {
  router.push('/dashboard/medical-records')
}

// 读取并应用API配置（兼容旧版本）
const loadAndApplyApiConfig = async () => {
  try {
    // 首先尝试从数据库加载默认配置
    const llmService = await getLLMService()
    const success = await llmService.loadConfigFromDatabase('default')
    if (success) {
      console.log('已从数据库加载默认配置')
      return
    }

    // 如果数据库没有配置，尝试从localStorage加载（向后兼容）
    const savedConfig = localStorage.getItem('llm-api-config')
    console.log('尝试从localStorage加载API配置:', savedConfig)

    if (savedConfig) {
      const configData = JSON.parse(savedConfig)
      console.log('解析的配置数据:', configData)

      // 使用基本配置（不依赖ENHANCED_LLM_API_CONFIGS）
      llmService.updateConfig({
        apiEndpoint: 'https://dashscope.aliyuncs.com/compatible-mode/v1',
        apiKey: configData.apiKey || '',
        model: configData.selectedModel || 'qwen-plus',
      })

      console.log('已加载并应用localStorage配置:', {
        model: configData.selectedModel,
        hasApiKey: !!configData.apiKey,
      })
    } else {
      console.log('未找到保存的API配置，使用默认配置')
      console.log('当前localStorage中的所有key:', Object.keys(localStorage))
    }
  } catch (error) {
    console.error('加载API配置失败:', error)
  }
}

// API配置更新处理
const handleApiConfigUpdated = async (config: UserLLMConfig) => {
  console.log('API配置已更新:', config)

  try {
    // 从数据库加载配置到llmService实例
    const llmService = await getLLMService()
    const success = await llmService.loadConfigFromDatabase(config.config_name)
    if (success) {
      message.success(`已切换到配置: ${config.config_name}`)
      showApiConfig.value = false
    } else {
      message.error('加载配置失败')
    }
  } catch (error) {
    console.error('应用API配置失败:', error)
    message.error('应用配置失败')
  }
}

// 处理关闭API配置Modal
const handleCloseApiConfig = () => {
  console.log('🎯 父组件收到关闭Modal事件，当前showApiConfig:', showApiConfig.value)
  showApiConfig.value = false
  console.log('🔒 已设置showApiConfig为false，新值:', showApiConfig.value)
}

// 处理全局配置更新事件
const handleGlobalConfigUpdate = async (event: Event) => {
  const configData = (event as CustomEvent).detail
  console.log('收到全局配置更新事件:', configData)

  try {
    // 从数据库重新加载配置
    const llmService = await getLLMService()
    const success = await llmService.loadConfigFromDatabase('default')
    if (success) {
      console.log('已应用全局配置更新')
    }
  } catch (error) {
    console.error('应用全局配置更新失败:', error)
  }
}

const handleCancel = () => {
  router.back()
}
</script>

<style scoped>
/* 整体布局 */
.page-container {
  @apply p-3;
}

.breadcrumb {
  @apply mb-3;
}

.page-header {
  @apply mb-3;
}

.header-content {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
}

.header-text {
  flex: 1;
}

.header-actions {
  display: flex;
  gap: 8px;
  align-items: center;
}

.page-title {
  @apply text-lg font-bold text-gray-900;
  font-size: 16px;
}

.page-description {
  @apply text-sm text-gray-600 mt-1;
}

/* 步骤卡片 */
.steps-card {
  @apply mb-3 shadow-sm;
}

:deep(.steps-card .ant-card-body) {
  padding: 16px !important;
}

.step-card {
  @apply mb-3 shadow-sm;
}

:deep(.step-card .ant-card-body) {
  padding: 20px !important;
}

:deep(.step-card .ant-card-head-title) {
  font-size: 15px !important;
  font-weight: 600 !important;
}

/* 输入区域样式 */
.input-section {
  @apply space-y-4;
}

.textarea-container {
  position: relative;
  margin-bottom: 16px;
}

.enhanced-text-input {
  font-family:
    'SF Mono', 'Monaco', 'Inconsolata', 'Roboto Mono', 'Source Code Pro', monospace !important;
  font-size: 14px !important;
  line-height: 1.6 !important;
  border-radius: 8px !important;
  border: 2px solid #e8e8e8 !important;
  padding: 16px !important;
  background-color: #fafafa !important;
  transition: all 0.3s ease !important;
  resize: vertical !important;
  min-height: 200px !important;
}

.enhanced-text-input:hover {
  border-color: #40a9ff !important;
  background-color: #ffffff !important;
}

.enhanced-text-input:focus {
  border-color: #1890ff !important;
  background-color: #ffffff !important;
  box-shadow: 0 0 0 2px rgba(24, 144, 255, 0.2) !important;
}

.enhanced-text-input::placeholder {
  color: #bfbfbf !important;
  font-style: italic !important;
}

/* 字符计数器样式优化 */
.enhanced-text-input + .ant-input-data-count {
  position: absolute !important;
  bottom: 8px !important;
  right: 12px !important;
  background: rgba(255, 255, 255, 0.9) !important;
  padding: 2px 6px !important;
  border-radius: 4px !important;
  font-size: 12px !important;
  color: #8c8c8c !important;
  backdrop-filter: blur(4px) !important;
}

/* 滚动条样式优化 */
.enhanced-text-input::-webkit-scrollbar {
  width: 8px !important;
}

.enhanced-text-input::-webkit-scrollbar-track {
  background: #f1f1f1 !important;
  border-radius: 4px !important;
}

.enhanced-text-input::-webkit-scrollbar-thumb {
  background: #c1c1c1 !important;
  border-radius: 4px !important;
}

.enhanced-text-input::-webkit-scrollbar-thumb:hover {
  background: #a8a8a8 !important;
}

.text-input {
  @apply font-mono;
  font-size: 12px !important;
  line-height: 1.4 !important;
}

/* 响应式设计 */
@media (max-width: 768px) {
  .enhanced-text-input {
    font-size: 16px !important; /* 防止iOS缩放 */
    padding: 12px !important;
    min-height: 160px !important;
  }

  .textarea-container {
    margin-bottom: 12px;
  }
}

@media (max-width: 480px) {
  .enhanced-text-input {
    padding: 10px !important;
    min-height: 140px !important;
    border-radius: 6px !important;
  }

  .enhanced-text-input + .ant-input-data-count {
    bottom: 6px !important;
    right: 8px !important;
    font-size: 11px !important;
  }
}

/* 深色模式支持 */
@media (prefers-color-scheme: dark) {
  .enhanced-text-input {
    background-color: #1f1f1f !important;
    border-color: #434343 !important;
    color: #ffffff !important;
  }

  .enhanced-text-input:hover {
    border-color: #177ddc !important;
    background-color: #262626 !important;
  }

  .enhanced-text-input:focus {
    border-color: #1890ff !important;
    background-color: #262626 !important;
  }

  .enhanced-text-input::placeholder {
    color: #8c8c8c !important;
  }
}

.input-tips {
  @apply mt-3;
}

.upload-section {
  @apply space-y-4;
}

.uploaded-preview {
  @apply mt-4 p-4 bg-gray-50 rounded border;
}

.uploaded-preview h4 {
  @apply text-sm font-semibold mb-2;
}

.content-preview {
  @apply text-xs text-gray-600 font-mono bg-white p-3 rounded border max-h-32 overflow-y-auto;
  line-height: 1.4;
}

.content-preview-enhanced {
  @apply bg-white rounded border min-h-[400px] max-h-[600px] overflow-y-auto;
}

.parsing-status {
  @apply flex flex-col items-center justify-center p-8 text-blue-600 bg-blue-50 rounded-lg border border-blue-200;
}

.parsing-status .ant-spin {
  @apply mb-3;
}

.parsing-status span {
  @apply text-base font-medium;
}

.parsed-content {
  @apply p-4;
}

.parsed-content pre {
  @apply text-sm text-gray-800 leading-relaxed;
  font-family: 'Courier New', monospace;
}

.batch-section {
  @apply space-y-4;
}

.batch-preview {
  @apply mt-4;
}

.batch-preview h4 {
  @apply text-sm font-semibold mb-3;
}

/* 解析进度样式 */
.parsing-section {
  @apply text-center py-8;
}

.parsing-content {
  @apply space-y-4;
}

.parsing-icon {
  @apply text-6xl text-blue-500 mb-4;
}

.parsing-content h3 {
  @apply text-lg font-semibold text-gray-900;
}

.parsing-content p {
  @apply text-gray-600;
}

.parsing-steps {
  @apply mt-6 space-y-3;
}

.parsing-step {
  @apply flex items-center justify-center gap-2 text-gray-400 transition-colors;
}

.parsing-step.active {
  @apply text-blue-500;
}

.parsing-step.completed {
  @apply text-green-500;
}

/* 审核区域样式 */
.review-section {
  @apply space-y-4;
}

.review-alert {
  @apply mb-4;
}

.review-form {
  @apply space-y-4;
}

.ai-extracted {
  @apply border-blue-300 bg-blue-50;
}

.ai-confidence {
  @apply text-xs text-blue-600 mt-1 flex items-center gap-1;
}

.documents-review {
  @apply space-y-4;
}

.no-documents {
  @apply text-center py-8;
}

.documents-list {
  @apply space-y-6;
}

.document-review-item {
  @apply border border-gray-200 rounded-lg p-4 bg-gray-50;
}

.document-header {
  @apply flex items-center justify-between mb-3;
}

.document-header h4 {
  @apply text-sm font-semibold text-gray-900 m-0 flex items-center gap-2;
}

.document-type-tag {
  @apply text-xs px-2 py-1 rounded bg-gray-100 font-medium;
  margin-top: 4px;
}

/* 解析统计样式 */
.parsing-stats {
  @apply space-y-4;
}

.confidence-breakdown {
  @apply space-y-3;
}

.confidence-breakdown h4 {
  @apply text-sm font-semibold;
}

.confidence-items {
  @apply space-y-2;
}

.confidence-item {
  @apply flex items-center justify-between gap-4;
}

.confidence-item span {
  @apply text-sm text-gray-700 min-w-20;
}

/* 成功页面样式 */
.success-section {
  @apply py-8;
}

/* 操作按钮区域 */
.step-actions {
  @apply flex justify-end mt-6 pt-4 border-t border-gray-200;
}

/* 通用样式优化 */
:deep(.ant-form-item-label > label) {
  font-size: 12px !important;
  font-weight: 500 !important;
}

:deep(.ant-input) {
  font-size: 12px !important;
  height: 28px !important;
  padding: 3px 8px !important;
}

:deep(.ant-select) {
  font-size: 12px !important;
}

:deep(.ant-select-selector) {
  font-size: 12px !important;
  height: 28px !important;
  padding: 0 8px !important;
}

:deep(.ant-select-selection-item) {
  font-size: 12px !important;
  line-height: 26px !important;
}

:deep(.ant-btn) {
  font-size: 12px !important;
  height: 28px !important;
  padding: 3px 12px !important;
}

:deep(.ant-breadcrumb) {
  font-size: 12px !important;
}

:deep(.ant-breadcrumb a) {
  color: #1890ff !important;
  text-decoration: none !important;
}

:deep(.ant-steps-item-title) {
  font-size: 12px !important;
}

:deep(.ant-steps-item-description) {
  font-size: 11px !important;
}

:deep(.ant-tabs-tab) {
  font-size: 13px !important;
}

:deep(.ant-upload-text) {
  font-size: 14px !important;
}

:deep(.ant-upload-hint) {
  font-size: 12px !important;
}

/* 备用上传工具样式 */
.alternative-upload-section {
  @apply border border-gray-200 rounded-lg p-4 bg-gray-50;
}

.alternative-upload-content {
  @apply space-y-3;
}

.selected-file-info {
  @apply bg-white rounded border p-3;
}

.selected-file-info :deep(.ant-descriptions-item-label) {
  @apply text-xs font-medium text-gray-600;
  width: 80px;
}

.selected-file-info :deep(.ant-descriptions-item-content) {
  @apply text-sm text-gray-800;
}

:deep(.ant-list-item-meta-title) {
  font-size: 12px !important;
}

:deep(.ant-list-item-meta-description) {
  font-size: 11px !important;
}

:deep(.ant-progress-text) {
  font-size: 11px !important;
}

:deep(.ant-statistic-title) {
  font-size: 12px !important;
}

:deep(.ant-statistic-content-value) {
  font-size: 18px !important;
}

:deep(.ant-result-title) {
  font-size: 16px !important;
}

:deep(.ant-result-subtitle) {
  font-size: 12px !important;
}
</style>
