<template>
  <div class="result-page">
    <!-- 如果没有结果数据，显示警告信息 -->
    <div v-if="!result || !result.success || !data" class="no-result-container">
      <a-page-header title="LLM 精准解析结果" sub-title="结构化信息与文书目录" />
      <a-alert
        type="warning"
        show-icon
        class="mb-3"
        message="没有可展示的结果"
        description="请先在智能导入或简易导入中运行一次 LLM 精准解析。"
      />
      <div class="back-button">
        <a-button type="primary" @click="goBack">返回首页</a-button>
      </div>
    </div>

    <!-- 有结果数据时，直接显示Modal -->
    <LLMResultModal
      v-else
      :visible="true"
      :data="data"
      :result="result"
      :original-text="data?.content"
      @update:visible="handleModalClose"
      @save-and-redirect="saveAndRedirect"
      @save-only="saveOnly"
      @export-result="exportResult"
      @export-pdf="exportPDF"
      @go-to-import="goToImport"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import LLMResultModal from '@/components/LLMResultModal.vue'
import { useLLMParseStore } from '@/stores/llmParse'
import { llmService } from '@/services/llmService'

const router = useRouter()
const store = useLLMParseStore()

// 响应式变量
const saving = ref(false)

// API配置：优先使用环境变量，否则走相对路径交由 Vite 代理
const API_BASE_URL = (import.meta as any)?.env?.VITE_API_BASE_URL ?? ''

onMounted(async () => {
  if (!store.lastResult) store.loadFromSession()

  // 加载保存的LLM配置
  try {
    await llmService.loadConfigFromDatabase('default')
    console.log('LLM配置已加载:', llmService.getCurrentConfig())
  } catch (error) {
    console.warn('加载LLM配置失败:', error)
  }
})

const result = computed(() => store.lastResult)
const data = computed<unknown>(() => result.value?.data)

// 计算属性用于获取解析元数据
const tokensUsed = computed(() => result.value?.tokensUsed || 0)
const confidencePct = computed(() => data.value?.confidence || 0)

// 从LLM服务获取当前配置信息
const providerName = computed(() => {
  const config = llmService.getCurrentConfig()
  return config?.provider?.provider_name || 'Unknown Provider'
})

const modelCode = computed(() => {
  const config = llmService.getCurrentConfig()
  return config?.model?.model_code || llmService.model || 'unknown-model'
})

// Modal关闭处理：优先返回来源页面
const handleModalClose = () => {
  const from = router.currentRoute.value.query.from as string | undefined
  if (from === 'medical-records') {
    router.push('/dashboard/medical-records')
  } else if (from) {
    // 允许未来扩展其他来源路由
    router.push(String(from))
  } else {
    router.push('/dashboard')
  }
}

// 无结果页返回按钮：也遵循来源优先
const goBack = () => {
  const from = router.currentRoute.value.query.from as string | undefined
  if (from === 'medical-records') {
    router.push('/dashboard/medical-records')
  } else if (from) {
    router.push(String(from))
  } else {
    router.push('/dashboard')
  }
}


const exportResult = () => {
  if (!result.value) { message.warning('没有可导出的结果'); return }
  const str = JSON.stringify(result.value, null, 2)
  const blob = new Blob([str], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `llm_parse_result_${Date.now()}.json`
  a.click()
  URL.revokeObjectURL(url)
}

// 保存并跳转到详情页面
const saveAndRedirect = async () => {
  const savedRecordId = await saveToDatabase()
  if (savedRecordId) {
    message.success('保存成功，正在跳转到详情页面...')
    setTimeout(() => {
      router.push(`/dashboard/medical-records/${savedRecordId}`)
    }, 1500)
  }
}

// 仅保存到数据库
const saveOnly = async () => {
  const savedRecordId = await saveToDatabase()
  if (savedRecordId) {
    message.success('解析结果已保存到数据库')
  }
}

// 保存到数据库的核心方法
const saveToDatabase = async (): Promise<string | null> => {
  if (!data.value) {
    message.error('没有可保存的数据')
    return null
  }

  try {
    saving.value = true

    // 构建保存数据 - 优化文档数据以减少请求体大小
    const optimizedDocuments = (data.value.documents || []).map((doc: unknown) => ({
      title: doc.title || '',
      summary: doc.summary || '',
      category: doc.category || '',
      type: doc.type || '',
      confidence: doc.confidence || 0,
      // 只保留内容的前500个字符作为摘要，避免发送完整内容
      content_preview: (doc.content || '').substring(0, 500)
    }))

    const saveData = {
      record_number: data.value.recordNumber || `LLM_${Date.now()}`,
      patient_name: data.value.patientName || '未识别',
      patient_age: data.value.patientAge || null,
      patient_gender: data.value.patientGender || null,
      department: data.value.department || '未识别',
      primary_diagnosis: data.value.primaryDiagnosis || '未识别',
      secondary_diagnosis: data.value.secondaryDiagnosis || [],
      major_surgery: data.value.majorSurgery || '无',
      documents: optimizedDocuments,
      confidence: data.value.confidence || 0,
      content: data.value.content || '',
      method: 'LLM精准解析',
      created_at: new Date().toISOString(),
      // 添加解析元数据
      parse_metadata: {
        provider: providerName.value,
        model: modelCode.value,
        tokens_used: tokensUsed.value,
        processing_time: result.value?.processingTime || 0,
        confidence: confidencePct.value
      }
    }

    // 调试信息：检查请求体大小
    const requestBody = JSON.stringify(saveData)
    const requestSizeKB = Math.round(requestBody.length / 1024)
    console.log(`📊 请求体大小: ${requestSizeKB}KB`)
    console.log('📋 保存数据预览:', {
      ...saveData,
      documents: `${saveData.documents.length} 个文档`,
      content: `${(saveData.content || '').length} 字符`
    })

    // 统一通过相对路径或可选的 API_BASE_URL 调用后端，避免浏览器直连失败
    const apiUrl = API_BASE_URL
      ? `${API_BASE_URL}/api/medical-records`
      : '/api/medical-records'

    const response = await fetch(apiUrl, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: requestBody
    })

    if (!response.ok) {
      const errorText = await response.text()
      console.error('❌ API响应错误:', {
        status: response.status,
        statusText: response.statusText,
        body: errorText
      })
      throw new Error(`保存失败 (${response.status}): ${response.statusText}`)
    }

    const savedRecord = await response.json() as { id: string }
    console.log('✅ 保存成功:', savedRecord)
    return savedRecord.id

  } catch (error: unknown) {
    console.error('❌ 保存失败:', error)

    // 提供更详细的错误信息
    let errorMessage = '保存失败'
    if (error.name === 'TypeError' && error.message.includes('fetch')) {
      errorMessage = '网络连接失败，请检查后端服务是否正常运行'
    } else if (error.message.includes('CORS')) {
      errorMessage = '跨域请求被阻止，请检查服务器CORS配置'
    } else {
      errorMessage = `保存失败: ${error.message}`
    }

    message.error(errorMessage)
    return null
  } finally {
    saving.value = false
  }
}

// 导出PDF报告
const exportPDF = () => {
  message.info('PDF导出功能开发中...')
  // TODO: 实现PDF导出功能
}

// 跳转到导入页面
const goToImport = () => {
  router.push('/dashboard/medical-records/smart-import')
}


</script>

<style scoped>
.result-page {
  height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
}

.no-result-container {
  width: 100%;
  max-width: 800px;
  padding: 32px;
  text-align: center;
}

.back-button {
  margin-top: 24px;
}

.mb-3 {
  margin-bottom: 16px;
}
</style>

