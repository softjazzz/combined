<template>
  <div class="smart-import-container">
    <div class="header-section">
      <div class="header-left">
        <h2>智能导入病历</h2>
        <p>支持文本输入和文件上传，智能解析医疗记录</p>
      </div>
      <div class="header-right">
        <a-button @click="showLLMConfig = true">
          <template #icon>
            <SettingOutlined />
          </template>
          配置 LLM
        </a-button>
      </div>
    </div>

    <a-tabs
      v-model:active-key="activeTab"
      class="import-tabs"
    >
      <!-- 文本输入 -->
      <a-tab-pane
        key="text"
        tab="文本输入"
      >
        <div class="text-input-section">
          <a-textarea
            v-model:value="inputText"
            placeholder="请输入医疗记录文本..."
            :rows="8"
            class="mb-3"
          />
          <div class="action-buttons">
            <a-button
              type="primary"
              :loading="parsing"
              @click="parseText"
            >
              <template #icon>
                <ThunderboltOutlined />
              </template>
              解析文本
            </a-button>
            <a-button @click="clearText">
              清空文本
            </a-button>
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
            :file-list="[]"
            :before-upload="beforeUpload"
            :show-upload-list="false"
            accept=".pdf,.doc,.docx,.txt"
            :multiple="true"
            @change="handleUploadChange"
          >
            <p class="ant-upload-drag-icon">
              <InboxOutlined />
            </p>
            <p class="ant-upload-text">
              点击或拖拽文件到此区域上传
            </p>
            <p class="ant-upload-hint">
              支持 PDF、Word、文本文件
            </p>
          </a-upload-dragger>

          <div
            v-if="uploadedFiles.length > 0"
            class="file-list"
          >
            <div class="file-list-header">
              <h4>已上传文件 ({{ uploadedFiles.length }})</h4>
              <a-space>
                <a-button
                  type="primary"
                  :loading="batchParsing"
                  @click="parseAllFiles"
                >
                  一键解析所有文件
                </a-button>
                <a-button
                  danger
                  @click="clearAllFiles"
                >
                  清空所有文件
                </a-button>
              </a-space>
            </div>

            <a-list
              :data-source="uploadedFiles"
              size="small"
            >
              <template #renderItem="{ item, index }">
                <a-list-item>
                  <template #actions>
                    <a-space>
                      <a-button
                        size="small"
                        :loading="item.parsing"
                        :disabled="item.parsed"
                        @click="parseFile(index)"
                      >
                        {{ item.parsed ? '已解析' : '解析' }}
                      </a-button>
                      <a-button
                        size="small"
                        danger
                        @click="removeFile(index)"
                      >
                        删除
                      </a-button>
                    </a-space>
                  </template>

                  <a-list-item-meta>
                    <template #title>
                      <div class="file-title">
                        <FileOutlined class="file-icon" />
                        <span>{{ item.name }}</span>
                        <a-tag
                          v-if="item.parsed"
                          color="success"
                          size="small"
                        >
                          已解析
                        </a-tag>
                        <a-tag
                          v-else-if="item.parsing"
                          color="processing"
                          size="small"
                        >
                          解析中
                        </a-tag>
                        <a-tag
                          v-else
                          color="default"
                          size="small"
                        >
                          待解析
                        </a-tag>
                      </div>
                    </template>
                    <template #description>
                      <div class="file-details">
                        <span>大小: {{ formatFileSize(item.size) }}</span>
                        <span>类型: {{ item.type }}</span>
                        <span v-if="item.uploadTime">上传时间: {{ item.uploadTime }}</span>
                      </div>
                    </template>
                  </a-list-item-meta>
                </a-list-item>
              </template>
            </a-list>
          </div>
        </div>
      </a-tab-pane>

      <!-- 解析结果 -->
      <a-tab-pane
        key="result"
        tab="解析结果"
        :disabled="!parseResult"
      >
        <div
          v-if="parseResult && parseResult.success"
          class="result-section"
        >
          <!-- 基本信息 -->
          <a-descriptions
            title="解析结果概览"
            bordered
          >
            <a-descriptions-item label="患者姓名">
              {{ displayPatientName }}
            </a-descriptions-item>
            <a-descriptions-item label="科室">
              {{ displayDepartment }}
            </a-descriptions-item>
            <a-descriptions-item label="主要诊断">
              {{ displayPrimaryDiagnosis }}
            </a-descriptions-item>
            <a-descriptions-item label="解析方法">
              {{ (parseResult.data && parseResult.data.method) || '未知' }}
            </a-descriptions-item>
            <a-descriptions-item label="页数">
              {{ (parseResult.data && parseResult.data.pages) || 1 }}
            </a-descriptions-item>
            <a-descriptions-item
              v-if="parseResult.isMerged"
              label="文档数量"
            >
              {{ parseResult.data.totalFiles }} 个文件
            </a-descriptions-item>
            <a-descriptions-item
              v-if="parseResult.isMerged"
              label="合并时间"
            >
              {{ parseResult.mergeTime }}
            </a-descriptions-item>
          </a-descriptions>

          <!-- 多文档分类展示 -->
          <div
            v-if="parseResult.isMerged && parseResult.data.documentsByType"
            class="documents-by-type"
            style="margin-top: 24px;"
          >
            <h4>文档分类视图</h4>
            <a-collapse
              v-model:active-key="activeDocumentTypes"
              ghost
            >
              <a-collapse-panel
                v-for="(docs, type) in parseResult.data.documentsByType"
                :key="type"
                :header="`${type} (${docs.length}个文档)`"
              >
                <div
                  v-for="doc in docs"
                  :key="doc.id"
                  class="document-item"
                >
                  <div class="document-header">
                    <h5>{{ doc.title }}</h5>
                    <a-space>
                      <a-tag color="blue">
                        {{ doc.type }}
                      </a-tag>
                      <a-tag color="green">
                        置信度: {{ Math.round(doc.confidence * 100) }}%
                      </a-tag>
                      <span class="parse-time">{{ doc.parseTime }}</span>
                    </a-space>
                  </div>
                  <a-textarea
                    :value="doc.content"
                    :rows="6"
                    readonly
                    class="document-content"
                    style="margin-top: 8px;"
                  />
                </div>
              </a-collapse-panel>
            </a-collapse>
          </div>

          <!-- 合并内容预览 -->
          <div
            class="content-preview"
            style="margin-top: 24px;"
          >
            <h4>
              {{ parseResult.isMerged ? '合并内容预览' : '内容预览' }}
              <a-tooltip
                v-if="parseResult.isMerged"
                title="显示所有文档的合并内容"
              >
                <InfoCircleOutlined style="margin-left: 8px; color: #1890ff;" />
              </a-tooltip>
            </h4>
            <a-textarea
              :value="(parseResult.data && parseResult.data.content) || ''"
              :rows="12"
              readonly
              class="content-textarea"
            />
          </div>

          <!-- 源文件信息 -->
          <div
            v-if="parseResult.isMerged && parseResult.data.sourceFiles"
            class="source-files"
            style="margin-top: 16px;"
          >
            <h5>源文件列表:</h5>
            <a-space wrap>
              <a-tag
                v-for="(file, index) in parseResult.data.sourceFiles"
                :key="index"
                color="processing"
              >
                {{ file }}
              </a-tag>
            </a-space>
          </div>

          <div
            class="result-actions"
            style="margin-top: 24px;"
          >
            <a-button
              type="primary"
              :loading="importing"
              @click="importToDatabase"
            >
              {{ parseResult.isMerged ? '批量导入数据库' : '导入数据库' }}
            </a-button>
            <a-button
              :loading="llmParsing"
              type="dashed"
              @click="preciseLLMParse"
            >
              LLM精准解析
            </a-button>
            <a-button @click="exportResult">
              {{ parseResult.isMerged ? '导出合并结果' : '导出结果' }}
            </a-button>
            <a-button
              v-if="parseResult.isMerged"
              type="default"
              @click="showIndividualResults"
            >
              查看单个文档结果
            </a-button>
          </div>
        </div>
      </a-tab-pane>
    </a-tabs>
    <!-- LLM 配置抽屉（全局位置，便于任何Tab使用） -->
    <a-drawer
      v-model:open="showLLMConfig"
      title="LLM 配置"
      width="720px"
    >
      <LLMApiConfig
        @config-updated="() => { operationLog += '\nLLM 配置已更新' }"
        @close-drawer="() => { showLLMConfig = false }"
        @close-modal="() => { showLLMConfig = false }"
      />
    </a-drawer>


    <!-- 操作日志 -->
    <div class="log-section">
      <h4>操作日志</h4>
      <a-textarea
        v-model:value="operationLog"
        :rows="6"
        readonly
        class="log-textarea"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import {
  InboxOutlined,
  ThunderboltOutlined,
  FileOutlined,
  SettingOutlined,
  InfoCircleOutlined
} from '@ant-design/icons-vue'
import LLMApiConfig from '@/components/LLMApiConfig.vue'

interface ParseResultData {
  patientName?: string
  patient_name?: string
  department?: string
  primaryDiagnosis?: string
  diagnosis_primary?: string
  content?: string
  method?: string
  pages?: number
  confidence?: number
  documents?: Array<{ confidence?: number }>
  documentsByType?: Record<string, MergedDocumentInfo[]>
  sourceFiles?: string[]
  totalFiles?: number
  medical_info?: {
    patientName?: string
    department?: string
    primaryDiagnosis?: string
    diagnosis?: string[]
  }
}

interface ParseResponse {
  success: boolean
  data: ParseResultData
  error?: string
  id?: string
  isMerged?: boolean
  mergeTime?: string
  tokensUsed?: number
  processingTime?: number
}

interface UploadFileLike {
  name: string
  size: number
  type: string
  file: File
  parsing: boolean
  parsed: boolean
  uploadTime?: string
  parseTime?: string
  result?: ParseResponse | null
}

interface UploadChangeFileItem {
  name: string
  size: number
  type?: string
  originFileObj?: File
}

interface UploadChangeInfo {
  fileList: UploadChangeFileItem[]
}

interface SourceResultItem extends ParseResponse {
  sourceFile: string
  sourceIndex: number
  documentType: string
  parseTime: string
}

interface MergedDocumentInfo {
  id: string
  type: string
  title: string
  parseTime: string
  content: string
  confidence: number
  extractedAt: string
  position: {
    startIndex: number
    endIndex: number
    fullContent: string
  }
  metadata: {
    sourceFile: string
    parseTime: string
    method: string
    pages: number
  }
}

const getErrorMessage = (error: unknown): string => {
  return error instanceof Error ? error.message : String(error)
}

const router = useRouter()
const showLLMConfig = ref(false)

// 监听全局关闭事件
const handleGlobalClose = () => {
  console.log('🎯 收到全局关闭事件，关闭LLM配置')
  showLLMConfig.value = false
}

onMounted(() => {
  window.addEventListener('llm-config-close', handleGlobalClose)
})

onUnmounted(() => {
  window.removeEventListener('llm-config-close', handleGlobalClose)
})


// 响应式数据
const activeTab = ref('text')
const inputText = ref('')
const parsing = ref(false)
const importing = ref(false)
const parseResult = ref<ParseResponse | null>(null)
const operationLog = ref('系统已就绪')
const uploadedFiles = ref<UploadFileLike[]>([])
const llmParsing = ref(false)
const batchParsing = ref(false)
const mergedResults = ref<ParseResponse | null>(null) // 存储合并后的多文档结果
const activeDocumentTypes = ref<string[]>([]) // 控制文档分类折叠面板

// 结果显示的兼容性处理
const displayPatientName = computed(() => {
  if (!parseResult.value) return '未识别'
  const d = parseResult.value.data || {}
  return d.patientName || d.patient_name || (d.medical_info && d.medical_info.patientName) || '未识别'
})
const displayDepartment = computed(() => {
  if (!parseResult.value) return '未识别'
  const d = parseResult.value.data || {}
  return d.department || (d.medical_info && d.medical_info.department) || '未识别'
})
const displayPrimaryDiagnosis = computed(() => {
  if (!parseResult.value) return '未识别'
  const d = parseResult.value.data || {}
  return d.primaryDiagnosis || d.diagnosis_primary || (d.medical_info && (d.medical_info.primaryDiagnosis || (Array.isArray(d.medical_info.diagnosis) ? d.medical_info.diagnosis[0] : ''))) || '未识别'
})

// 解析成功后自动切换结果标签
watch(parseResult, (val) => {
  if (val && val.success) {
    activeTab.value = 'result'
  }
})

// 文本解析
const parseText = async () => {
  if (!inputText.value.trim()) {
    message.warning('请输入文本内容')
    return
  }

  parsing.value = true
  operationLog.value += '\n开始解析文本...'

  try {
    const response = await fetch('/api/parse-medical-text', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text: inputText.value })
    })

    if (!response.ok) {
      throw new Error('解析请求失败')
    }

    const result = await response.json()

    if (result.success) {
      parseResult.value = result
      operationLog.value += '\n解析完成'
      message.success('文本解析成功')
      activeTab.value = 'result'
    } else {
      throw new Error(result.error || '解析失败')
    }
  } catch (error) {
    const errorMessage = getErrorMessage(error)
    operationLog.value += '\n解析失败: ' + errorMessage
    message.error('解析失败: ' + errorMessage)
  } finally {
    parsing.value = false
  }
}

// 清空文本
const clearText = () => {
  inputText.value = ''
  parseResult.value = null
  operationLog.value += '\n已清空文本'
}

// 删除文件
const removeFile = (index: number) => {
  const fileObj = uploadedFiles.value[index]
  if (!fileObj) return
  if (fileObj.parsing) {
    message.warning('正在解析的文件无法删除')
    return
  }
  uploadedFiles.value.splice(index, 1)
  operationLog.value += `\n已删除文件: ${fileObj.name}`
}

// 文件上传前检查
const beforeUpload = (file: File) => {
  console.log(`[${new Date().toLocaleTimeString()}] beforeUpload 被调用: ${file.name}`)

  const isValidType = [
    'application/pdf',
    'text/plain',
    'application/msword',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
  ].includes(file.type) ||
  file.name.match(/\.(pdf|txt|doc|docx)$/i)

  if (!isValidType) {
    message.error('只支持 PDF、Word、文本文件')
    return false
  }

  // 检查文件大小 (10MB限制)
  if (file.size > 10 * 1024 * 1024) {
    message.error('文件大小不能超过10MB')
    return false
  }

  console.log(`[${new Date().toLocaleTimeString()}] 文件验证通过: ${file.name}`)
  return false // 阻止自动上传，我们手动处理
}

// 处理文件上传变化
const handleUploadChange = (info: UploadChangeInfo) => {
  console.log(`[${new Date().toLocaleTimeString()}] handleUploadChange 被调用, 文件数量: ${info.fileList.length}`)

  // 过滤出新添加的文件
  const newFiles = info.fileList.filter((fileItem: UploadChangeFileItem) => {
    const exists = uploadedFiles.value.some(existing =>
      existing.name === fileItem.name && existing.size === fileItem.size
    )
    return !exists
  })

  // 添加新文件到列表
  newFiles.forEach((fileItem: UploadChangeFileItem) => {
    const rawFile = fileItem.originFileObj ?? (fileItem as unknown as File)
    const fileObj = {
      name: fileItem.name,
      size: fileItem.size,
      type: fileItem.type || 'application/pdf',
      file: rawFile,
      parsing: false,
      parsed: false,
      uploadTime: new Date().toLocaleString()
    }

    uploadedFiles.value.push(fileObj)
    console.log(`[${new Date().toLocaleTimeString()}] 添加新文件: ${fileObj.name}`)
  })

  operationLog.value += `\n多文件上传完成已加载: ${newFiles.length} 个文件`
}

// 格式化文件大小
const formatFileSize = (bytes: number) => {
  if (bytes === 0) return '0 Bytes'
  const k = 1024
  const sizes = ['Bytes', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
}

// 批量解析所有文件
const parseAllFiles = async () => {
  if (uploadedFiles.value.length === 0) {
    message.warning('请先上传文件')
    return
  }

  batchParsing.value = true
  operationLog.value += `\n开始批量解析 ${uploadedFiles.value.length} 个文件...`

  const allResults: SourceResultItem[] = []
  let successCount = 0
  let failCount = 0

  try {
    for (let i = 0; i < uploadedFiles.value.length; i++) {
      const fileObj = uploadedFiles.value[i]

      if (!fileObj.parsed) {
        operationLog.value += `\n正在解析文件 ${i + 1}/${uploadedFiles.value.length}: ${fileObj.name}`

        try {
          await parseFileSilent(i) // 使用静默解析，不切换到结果页

          if (fileObj.result && fileObj.result.success) {
            // 为每个文档添加来源信息
            const resultWithSource = {
              ...fileObj.result,
              sourceFile: fileObj.name,
              sourceIndex: i,
              documentType: classifyDocument(fileObj.name),
              parseTime: new Date().toLocaleString()
            }
            allResults.push(resultWithSource)
            successCount++
            operationLog.value += `\n✓ ${fileObj.name} 解析成功`
          } else {
            failCount++
            operationLog.value += `\n✗ ${fileObj.name} 解析失败`
          }
        } catch (error) {
          failCount++
          operationLog.value += `\n✗ ${fileObj.name} 解析失败: ${getErrorMessage(error)}`
        }

        // 添加延迟避免请求过快
        await new Promise(resolve => setTimeout(resolve, 1000))
      } else {
        // 文件已解析，直接添加到结果中
        if (fileObj.result && fileObj.result.success) {
          const resultWithSource = {
            ...fileObj.result,
            sourceFile: fileObj.name,
            sourceIndex: i,
            documentType: classifyDocument(fileObj.name),
            parseTime: fileObj.parseTime || new Date().toLocaleString()
          }
          allResults.push(resultWithSource)
          successCount++
        }
      }
    }

    // 合并所有解析结果
    if (allResults.length > 0) {
      mergedResults.value = mergeMultipleResults(allResults)
      parseResult.value = mergedResults.value // 设置为合并结果以便显示
      activeTab.value = 'result'
      operationLog.value += `\n批量解析完成: 成功 ${successCount} 个，失败 ${failCount} 个`
      message.success(`批量解析完成: 成功 ${successCount} 个，失败 ${failCount} 个`)
    } else {
      message.warning('没有成功解析的文件')
      operationLog.value += `\n批量解析完成，但没有成功解析的文件`
    }

  } catch (error) {
    message.error('批量解析过程中出现错误')
    operationLog.value += `\n批量解析错误: ${getErrorMessage(error)}`
  } finally {
    batchParsing.value = false
  }
}

// 清空所有文件
const clearAllFiles = () => {
  uploadedFiles.value = []
  parseResult.value = null
  mergedResults.value = null
  operationLog.value += `\n已清空所有文件`
  message.info('已清空所有文件')
}

// 文档类型分类
const classifyDocument = (fileName: string) => {
  const name = fileName.toLowerCase()
  if (name.includes('病程') || name.includes('病历')) return '病程记录'
  if (name.includes('手术') || name.includes('术后')) return '手术记录'
  if (name.includes('检查') || name.includes('检验')) return '检查报告'
  if (name.includes('诊断') || name.includes('诊疗')) return '诊断记录'
  if (name.includes('护理')) return '护理记录'
  if (name.includes('出院') || name.includes('小结')) return '出院记录'
  if (name.includes('入院')) return '入院记录'
  return '其他文档'
}

// 静默解析文件（不切换到结果页）
const parseFileSilent = async (index: number) => {
  const fileObj = uploadedFiles.value[index]
  if (!fileObj) return

  fileObj.parsing = true

  try {
    const formData = new FormData()
    formData.append('file', fileObj.file)
    formData.append('options', '{}')

    const response = await fetch('/api/parse-medical-file-public', {
      method: 'POST',
      body: formData
    })

    if (!response.ok) {
      throw new Error('文件解析请求失败')
    }

    const result = (await response.json()) as ParseResponse

    if (result.success) {
      fileObj.parsed = true
      fileObj.result = result
      fileObj.parseTime = new Date().toLocaleString()
      // 注意：这里不设置 parseResult.value，避免切换到结果页
    } else {
      throw new Error(result.error || '解析失败')
    }
  } finally {
    fileObj.parsing = false
  }
}

// 合并多个解析结果
const mergeMultipleResults = (results: SourceResultItem[]): ParseResponse | null => {
  if (results.length === 0) return null
  if (results.length === 1) return results[0]

  // 收集所有患者信息，取最完整的
  const allPatientNames = results.map(r => r.data?.patientName).filter(Boolean)
  const allDepartments = results.map(r => r.data?.department).filter(Boolean)
  const allDiagnoses = results.map(r => r.data?.primaryDiagnosis).filter(Boolean)

  // 按文档类型分组
  const documentsByType: Record<string, MergedDocumentInfo[]> = {}
  const allDocuments: MergedDocumentInfo[] = []

  results.forEach((result: SourceResultItem, index: number) => {
    const docType = result.documentType
    const sourceFile = result.sourceFile

    if (!documentsByType[docType]) {
      documentsByType[docType] = []
    }

    // 创建符合 ExtractedDocument 接口的文档对象
    const docInfo = {
      id: `doc_${index}`,
      type: mapDocumentType(docType), // 映射到标准文档类型
      title: `${sourceFile} - ${docType}`,
      parseTime: result.parseTime,
      content: result.data?.content || '',
      confidence: result.data?.confidence || 0.8,
      extractedAt: new Date().toISOString(),
      position: {
        startIndex: 0,
        endIndex: (result.data?.content || '').length,
        fullContent: result.data?.content || ''
      },
      metadata: {
        sourceFile: sourceFile,
        parseTime: result.parseTime,
        method: result.data?.method || '文件解析',
        pages: result.data?.pages || 1
      }
    }

    documentsByType[docType].push(docInfo)
    allDocuments.push(docInfo)
  })

  // 合并内容
  const mergedContent = results.map((r: SourceResultItem) => {
    const content = r.data?.content || ''
    return `=== ${r.sourceFile} (${r.documentType}) ===\n${content}\n`
  }).join('\n')

  return {
    success: true,
    data: {
      patientName: allPatientNames[0] || '未识别',
      department: allDepartments[0] || '未识别',
      primaryDiagnosis: allDiagnoses[0] || '未识别',
      content: mergedContent,
      method: '批量文件解析',
      pages: results.reduce((sum: number, r: SourceResultItem) => sum + (r.data?.pages || 1), 0),
      documents: allDocuments, // 符合 ExtractedDocument[] 格式
      documentsByType: documentsByType,
      sourceFiles: results.map((r: SourceResultItem) => r.sourceFile),
      totalFiles: results.length,
      confidence: results.reduce((sum: number, r: SourceResultItem) => sum + (r.data?.confidence || 0.8), 0) / results.length
    },
    isMerged: true,
    mergeTime: new Date().toLocaleString()
  }
}

// 映射文档类型到标准类型
const mapDocumentType = (docType: string) => {
  const typeMapping: Record<string, string> = {
    '手术记录': 'operation_record',
    '入院记录': 'admission_record',
    '病程记录': 'progress_note',
    '出院记录': 'discharge_record',
    '检验报告': 'auxiliary_examination',
    '检查报告': 'auxiliary_examination',
    '知情同意书': 'informed_consent',
    '医嘱': 'medical_order',
    '护理记录': 'nursing_record'
  }
  return typeMapping[docType] || 'other'
}

// 查看单个文档结果
const showIndividualResults = () => {
  if (!parseResult.value?.isMerged) return

  // 展开所有文档分类
  const types = Object.keys(parseResult.value.data.documentsByType || {})
  activeDocumentTypes.value = types

  message.info('已展开所有文档分类，您可以查看每个文档的详细内容')
}

// 处理文件上传
const handleFileUpload = async (options: { file: File }) => {
  const { file } = options

  const fileObj = {
    name: file.name,
    size: file.size,
    type: file.type,
    file: file,
    parsing: false,
    parsed: false,
    result: null
  }

  uploadedFiles.value.push(fileObj)
  operationLog.value += '\n文件已添加: ' + file.name
  message.success('文件上传成功')
}

// 解析文件
const parseFile = async (index: number) => {
  const fileObj = uploadedFiles.value[index]
  if (!fileObj) return

  fileObj.parsing = true
  operationLog.value += '\n开始解析文件: ' + fileObj.name

  try {
    const formData = new FormData()
    formData.append('file', fileObj.file)
    formData.append('options', '{}')

    const response = await fetch('/api/parse-medical-file-public', {
      method: 'POST',
      body: formData
    })

    if (!response.ok) {
      throw new Error('文件解析请求失败')
    }

    const result = (await response.json()) as ParseResponse

    if (result.success) {
      fileObj.parsed = true
      fileObj.result = result
      parseResult.value = result
      operationLog.value += '\n文件解析完成'
      message.success('文件解析成功')
      activeTab.value = 'result'
    } else {
      throw new Error(result.error || '解析失败')
    }
  } catch (error) {
    const errorMessage = getErrorMessage(error)
    operationLog.value += '\n文件解析失败: ' + errorMessage
    message.error('解析失败: ' + errorMessage)
  } finally {
    fileObj.parsing = false
  }
}

// 导入数据库
const importToDatabase = async () => {
  if (!parseResult.value) {
    message.warning('没有可导入的数据')
    return
  }

  importing.value = true
  operationLog.value += '\n开始导入数据库...'

  try {
    const response = await fetch('/api/medical-records', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        patient_name: parseResult.value.data.patientName || '未知',
        department: parseResult.value.data.department || '未知',
        diagnosis_primary: parseResult.value.data.primaryDiagnosis || '未知',
        content: parseResult.value.data.content || '',
        source: 'smart_import'
      })
    })

    if (!response.ok) {
      throw new Error('导入请求失败')
    }

    const result = await response.json()
    operationLog.value += '\n导入成功，记录ID: ' + result.id
    message.success('导入数据库成功')
  } catch (error) {
    const errorMessage = getErrorMessage(error)
    operationLog.value += '\n导入失败: ' + errorMessage
    message.error('导入失败: ' + errorMessage)
  } finally {
    importing.value = false
  }
}

// 导出结果
const exportResult = () => {
  if (!parseResult.value) {
    message.warning('没有可导出的结果')
    return
  }

  const dataStr = JSON.stringify(parseResult.value, null, 2)
  const dataBlob = new Blob([dataStr], { type: 'application/json' })

// 接收LLM配置更新（可用于更新 llmService 的运行时配置）
const onLLMConfigUpdated = (configData: unknown) => {
  void configData
  operationLog.value += '\nLLM 配置已更新'
}

// 处理关闭LLM配置抽屉
const onCloseDrawer = () => {
  console.log('🎯 父组件收到关闭事件，当前showLLMConfig:', showLLMConfig.value)
  showLLMConfig.value = false
  console.log('🔒 已设置showLLMConfig为false，新值:', showLLMConfig.value)
  operationLog.value += '\nLLM 配置弹窗已关闭'
}

  const url = URL.createObjectURL(dataBlob)

  if (typeof document !== 'undefined') {
    const link = document.createElement('a')
    link.href = url
    link.download = 'parse_result_' + new Date().getTime() + '.json'
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
  }

  URL.revokeObjectURL(url)
  operationLog.value += '\n结果已导出'
  message.success('结果导出成功')
}

// LLM 精准解析（复用 llmService）
const preciseLLMParse = async () => {
  if (!(parseResult.value && parseResult.value.data && parseResult.value.data.content)) {
    message.warning('请先完成基础解析，确保有可用的文本内容')
    return
  }
  llmParsing.value = true
  operationLog.value += '\n开始 LLM 精准解析...'
  try {
    const { llmService } = await import('@/services/llmService')

    // 在使用前确保加载默认配置
    await llmService.loadConfigFromDatabase('default')

    // 直接复用 llmService 的文本抽取能力
    const result = await llmService.extractMedicalData(parseResult.value.data.content, {
      extractPatientInfo: true,
      extractDiagnosis: true,
      classifyDocuments: true,
      confidenceThreshold: 0.7
    })

    // 检查是否是回退到本地算法的结果
    if (result.success && result.data?.documents) {
      const hasLowConfidence = result.data.documents.some(doc => doc.confidence && doc.confidence < 90)
      if (hasLowConfidence) {
        message.warning('⚠️ 检测到LLM API调用可能失败，当前结果可能来自本地算法。请检查API密钥配置。')
        operationLog.value += '\n⚠️ 警告：可能使用了本地算法回退，建议检查LLM配置'
      }
    }

    if (result && result.success) {
      // 合并结果，保留原始内容与来源方法
      const original = parseResult.value
      const merged = {
        success: true,
        data: {
          ...result.data,
          content: original.data?.content || '',
          method: 'LLM 精准解析',
          // 保留多文档相关信息
          ...(original.isMerged && {
            sourceFiles: original.data?.sourceFiles,
            totalFiles: original.data?.totalFiles,
            documentsByType: original.data?.documentsByType
          })
        },
        tokensUsed: result.tokensUsed,
        processingTime: result.processingTime,
        // 保留合并标识
        isMerged: original.isMerged,
        mergeTime: original.mergeTime
      }
      parseResult.value = merged

      // 写入store并跳转到统一结果页
      const { useLLMParseStore } = await import('@/stores/llmParse')
      const store = useLLMParseStore()
      store.setResult(merged)
      // 带上来源页面，便于结果页关闭时返回
      await router.push({ path: '/dashboard/llm-result', query: { from: 'medical-records' } })

      message.success('LLM 精准解析成功')
      operationLog.value += '\nLLM 精准解析成功'
      activeTab.value = 'result'
    } else {
      throw new Error((result && result.error) || 'LLM 解析失败')
    }
  } catch (e: any) {
    console.error('LLM精准解析失败:', e)
    message.error('LLM精准解析失败: ' + (e.message || e))
    operationLog.value += '\nLLM精准解析失败: ' + (e.message || e)
  } finally {
    llmParsing.value = false
  }
}

</script>

<style scoped>
.smart-import-container {
  padding: 24px;
  max-width: 1200px;
  margin: 0 auto;
}

.header-section {
  margin-bottom: 24px;
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.header-left {
  display: flex;
  flex-direction: column;
}
.header-right {
  display: flex;
  gap: 12px;
}

.import-tabs {
  margin-bottom: 24px;
}

.text-input-section {


  padding: 16px;
}

.action-buttons {
  display: flex;
  gap: 12px;
  margin-top: 16px;
}

.upload-section {
  padding: 16px;
}

.file-list {
  margin-top: 24px;
}

.file-item {
  display: flex;
  align-items: center;
  gap: 12px;
  width: 100%;
}

.result-section {
  padding: 16px;
}

.result-actions {
  margin-top: 24px;
  display: flex;
  gap: 12px;
}

.log-section {
  margin-top: 24px;
}

.log-textarea {
  font-family: 'Courier New', monospace;
  font-size: 12px;
}

.file-list-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.file-title {
  display: flex;
  align-items: center;
  gap: 8px;
}

.file-icon {
  color: #1890ff;
}

.file-details {
  display: flex;
  gap: 16px;
  color: #666;
  font-size: 12px;
}

.documents-by-type {
  border: 1px solid #f0f0f0;
  border-radius: 6px;
  padding: 16px;
  background: #fafafa;
}

.document-item {
  margin-bottom: 16px;
  padding: 12px;
  background: white;
  border-radius: 4px;
  border: 1px solid #e8e8e8;
}

.document-item:last-child {
  margin-bottom: 0;
}

.document-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.document-header h5 {
  margin: 0;
  color: #1890ff;
  font-weight: 500;
}

.parse-time {
  color: #999;
  font-size: 12px;
}

.document-content {
  font-family: 'Courier New', monospace;
  font-size: 12px;
}

.source-files {
  padding: 12px;
  background: #f6f8fa;
  border-radius: 4px;
  border-left: 3px solid #1890ff;
}

.source-files h5 {
  margin: 0 0 8px 0;
  color: #1890ff;
}
</style>
