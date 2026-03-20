<template>
  <div class="test-page">
    <a-page-header title="多文档合并测试" sub-title="测试多文档解析结果的合并和展示功能" />
    
    <a-card title="测试控制面板" class="mb-4">
      <a-space>
        <a-button type="primary" @click="runMergeTest" :loading="testing">
          运行合并测试
        </a-button>
        <a-button @click="showLLMResult" :disabled="!mergedResult">
          查看LLM结果页面
        </a-button>
        <a-button @click="clearResults">
          清除结果
        </a-button>
      </a-space>
    </a-card>

    <a-row :gutter="16">
      <!-- 左侧：原始数据 -->
      <a-col :span="12">
        <a-card title="模拟原始解析结果" size="small">
          <pre class="json-display">{{ JSON.stringify(mockResults, null, 2) }}</pre>
        </a-card>
      </a-col>

      <!-- 右侧：合并结果 -->
      <a-col :span="12">
        <a-card title="合并后结果" size="small">
          <div v-if="mergedResult">
            <a-descriptions size="small" bordered>
              <a-descriptions-item label="患者姓名">{{ mergedResult.data.patientName }}</a-descriptions-item>
              <a-descriptions-item label="科室">{{ mergedResult.data.department }}</a-descriptions-item>
              <a-descriptions-item label="主要诊断">{{ mergedResult.data.primaryDiagnosis }}</a-descriptions-item>
              <a-descriptions-item label="文档总数">{{ mergedResult.data.totalFiles }}</a-descriptions-item>
              <a-descriptions-item label="合并时间">{{ mergedResult.mergeTime }}</a-descriptions-item>
            </a-descriptions>
            
            <h4 class="mt-3">文档列表 ({{ mergedResult.data.documents.length }}个)</h4>
            <a-list size="small" :data-source="mergedResult.data.documents">
              <template #renderItem="{ item }">
                <a-list-item>
                  <a-list-item-meta
                    :title="item.title"
                    :description="`类型: ${item.type} | 置信度: ${Math.round(item.confidence * 100)}% | 源文件: ${item.metadata.sourceFile}`"
                  />
                </a-list-item>
              </template>
            </a-list>
          </div>
          <a-empty v-else description="暂无合并结果" />
        </a-card>
      </a-col>
    </a-row>

    <!-- LLM结果Modal测试 -->
    <LLMResultModal
      v-if="showModal"
      :visible="showModal"
      :data="mergedResult?.data"
      :result="mergedResult"
      :original-text="mergedResult?.data?.content"
      @update:visible="showModal = false"
      @save-and-redirect="handleSave"
      @save-only="handleSave"
      @export-result="handleExport"
      @export-pdf="handleExportPDF"
      @go-to-import="handleGoToImport"
    />
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import LLMResultModal from '@/components/LLMResultModal.vue'
import { useLLMParseStore } from '@/stores/llmParse'

const router = useRouter()
const store = useLLMParseStore()

// 响应式数据
const testing = ref(false)
const mergedResult = ref<any>(null)
const showModal = ref(false)

// 模拟的多文档解析结果
const mockResults = [
  {
    documentType: '手术记录',
    sourceFile: '手术记录_张三_20231201.pdf',
    parseTime: '2023-12-01 10:30:00',
    data: {
      patientName: '张三',
      department: '外科',
      primaryDiagnosis: '阑尾炎',
      content: '患者张三，男，35岁，因急性阑尾炎入院。手术过程：在全麻下行腹腔镜阑尾切除术，手术顺利，术后恢复良好。术中见阑尾充血水肿，周围有少量渗出。',
      confidence: 0.95,
      pages: 2,
      method: 'PDF解析'
    }
  },
  {
    documentType: '入院记录',
    sourceFile: '入院记录_张三_20231130.pdf',
    parseTime: '2023-11-30 14:20:00',
    data: {
      patientName: '张三',
      department: '外科',
      primaryDiagnosis: '急性阑尾炎',
      content: '患者张三，男，35岁，主诉右下腹痛2天。现病史：患者2天前无明显诱因出现右下腹痛，呈持续性钝痛。体格检查：右下腹压痛明显，反跳痛阳性。',
      confidence: 0.92,
      pages: 3,
      method: 'PDF解析'
    }
  },
  {
    documentType: '检验报告',
    sourceFile: '血常规_张三_20231130.pdf',
    parseTime: '2023-11-30 16:45:00',
    data: {
      patientName: '张三',
      department: '检验科',
      content: '血常规检查结果：白细胞计数：12.5×10^9/L（升高），中性粒细胞比例：85%（升高），血红蛋白：135g/L（正常），血小板计数：280×10^9/L（正常）。',
      confidence: 0.88,
      pages: 1,
      method: 'PDF解析'
    }
  }
]

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

// 合并多个解析结果
const mergeMultipleResults = (results: any[]) => {
  if (results.length === 0) return null
  if (results.length === 1) return results[0]

  // 收集所有患者信息，取最完整的
  const allPatientNames = results.map(r => r.data?.patientName).filter(Boolean)
  const allDepartments = results.map(r => r.data?.department).filter(Boolean)
  const allDiagnoses = results.map(r => r.data?.primaryDiagnosis).filter(Boolean)

  // 按文档类型分组
  const documentsByType: Record<string, any[]> = {}
  const allDocuments: any[] = []

  results.forEach((result, index) => {
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
  const mergedContent = results.map(r => {
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
      pages: results.reduce((sum, r) => sum + (r.data?.pages || 1), 0),
      documents: allDocuments, // 符合 ExtractedDocument[] 格式
      documentsByType: documentsByType,
      sourceFiles: results.map(r => r.sourceFile),
      totalFiles: results.length,
      confidence: results.reduce((sum, r) => sum + (r.data?.confidence || 0.8), 0) / results.length
    },
    isMerged: true,
    mergeTime: new Date().toLocaleString()
  }
}

// 运行合并测试
const runMergeTest = async () => {
  testing.value = true
  try {
    await new Promise(resolve => setTimeout(resolve, 500)) // 模拟异步处理
    mergedResult.value = mergeMultipleResults(mockResults)
    message.success('合并测试完成')
  } catch (error) {
    message.error('合并测试失败: ' + error)
  } finally {
    testing.value = false
  }
}

// 显示LLM结果页面
const showLLMResult = () => {
  if (!mergedResult.value) return
  
  // 保存到store并跳转
  store.setResult(mergedResult.value)
  router.push('/dashboard/llm-result')
}

// 显示Modal
const showModalTest = () => {
  if (!mergedResult.value) return
  showModal.value = true
}

// 清除结果
const clearResults = () => {
  mergedResult.value = null
  message.info('结果已清除')
}

// 事件处理
const handleSave = () => {
  message.success('保存功能测试')
}

const handleExport = () => {
  message.success('导出功能测试')
}

const handleExportPDF = () => {
  message.success('PDF导出功能测试')
}

const handleGoToImport = () => {
  router.push('/dashboard/medical-records/smart-import-simple')
}
</script>

<style scoped>
.test-page {
  padding: 24px;
}

.json-display {
  background: #f5f5f5;
  padding: 12px;
  border-radius: 4px;
  font-size: 12px;
  max-height: 400px;
  overflow-y: auto;
}

.mb-4 {
  margin-bottom: 16px;
}

.mt-3 {
  margin-top: 12px;
}
</style>
