<template>
  <div class="medical-record-detail-simple">
    <h1>医疗记录详情页面（简化版）</h1>
    <p>记录ID: {{ recordId }}</p>
    
    <div v-if="loading">
      <a-spin
        size="large"
        tip="加载中..."
      />
    </div>
    
    <div
      v-else-if="error"
      style="color: red;"
    >
      错误: {{ error }}
    </div>
    
    <div v-else>
      <h2>患者信息</h2>
      <div v-if="patient">
        <p>姓名: {{ patient.patient_name }}</p>
        <p>年龄: {{ patient.patient_age }}</p>
        <p>性别: {{ patient.patient_gender }}</p>
        <p>科室: {{ patient.department }}</p>
      </div>
      
      <h2>文档列表</h2>
      <div v-if="documentsResponse">
        <p>总文档数: {{ documentsResponse.total_documents }}</p>
        <div
          v-for="category in documentsResponse.categories"
          :key="category.category_code"
        >
          <h3>{{ category.category_name }} ({{ category.document_count }})</h3>
          <ul>
            <li
              v-for="doc in category.documents"
              :key="doc.id"
            >
              {{ doc.title || doc.type_info?.type_name || '未命名文档' }}
            </li>
          </ul>
        </div>
      </div>
    </div>
    
    <div style="margin-top: 20px;">
      <a-button @click="testAPI">
        测试API
      </a-button>
      <a-button
        style="margin-left: 10px;"
        @click="testComponents"
      >
        测试组件
      </a-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()

interface PatientLite {
  patient_name?: string
  patient_age?: number
  patient_gender?: string
  department?: string
}

interface DocumentCategoryLite {
  category_code: string
  category_name: string
  document_count: number
  documents: Array<{
    id: string
    title?: string
    type_info?: {
      type_name?: string
    }
  }>
}

interface DocumentsResponseLite {
  total_documents?: number
  categories?: DocumentCategoryLite[]
}

// 响应式状态
const loading = ref(false)
const error = ref('')
const patient = ref<PatientLite | null>(null)
const documentsResponse = ref<DocumentsResponseLite | null>(null)

// 计算属性
const recordId = computed(() => route.params.id as string)

// 测试API
const testAPI = async () => {
  loading.value = true
  error.value = ''
  
  try {
    console.log('开始测试API...')
    
    // 测试患者API
    const patientResponse = await fetch(`/api/medical-records/${recordId.value}`)
    if (!patientResponse.ok) {
      throw new Error(`患者API失败: ${patientResponse.status}`)
    }
    const patientData = await patientResponse.json()
    patient.value = patientData
    console.log('患者数据:', patientData)
    
    // 测试文档API
    const docsResponse = await fetch(`/api/medical-records/${recordId.value}/documents`)
    if (!docsResponse.ok) {
      throw new Error(`文档API失败: ${docsResponse.status}`)
    }
    const docsData = await docsResponse.json()
    documentsResponse.value = docsData
    console.log('文档数据:', docsData)
    
  } catch (err) {
    console.error('API测试失败:', err)
    error.value = err instanceof Error ? err.message : String(err)
  } finally {
    loading.value = false
  }
}

// 测试组件导入
const testComponents = async () => {
  try {
    console.log('开始测试组件导入...')
    
    const layoutShell = await import('@/mr/components/LayoutShell.vue')
    console.log('LayoutShell 导入成功:', layoutShell)
    
    const navTree = await import('@/mr/components/NavTree.vue')
    console.log('NavTree 导入成功:', navTree)
    
    const toolbar = await import('@/mr/components/Toolbar.vue')
    console.log('Toolbar 导入成功:', toolbar)
    
    const contextAside = await import('@/mr/components/ContextAside.vue')
    console.log('ContextAside 导入成功:', contextAside)
    
    const api = await import('@/mr/data/api')
    console.log('API 模块导入成功:', api)
    
    alert('所有组件导入成功！')
  } catch (err) {
    console.error('组件导入失败:', err)
    alert('组件导入失败: ' + (err instanceof Error ? err.message : String(err)))
  }
}

// 组件挂载时自动测试API
onMounted(() => {
  testAPI()
})
</script>

<style scoped>
.medical-record-detail-simple {
  padding: 20px;
  max-width: 1200px;
  margin: 0 auto;
}

h1 {
  color: #2b6cf6;
  margin-bottom: 20px;
}

h2 {
  color: #333;
  margin: 20px 0 10px 0;
}

h3 {
  color: #666;
  margin: 15px 0 5px 0;
}

ul {
  margin: 10px 0;
  padding-left: 20px;
}

li {
  margin: 5px 0;
}
</style>
