<template>
  <div class="p-6 max-w-6xl mx-auto">
    <div class="bg-white rounded-lg shadow-md p-6">
      <h1 class="text-2xl font-bold mb-6">患者数据测试页面</h1>
      
      <!-- 测试按钮 -->
      <div class="mb-6 flex space-x-4">
        <button 
          @click="testDatabaseData"
          :disabled="loading"
          class="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600 disabled:opacity-50"
        >
          {{ loading ? '测试中...' : '测试数据库数据' }}
        </button>
        <button 
          @click="testDemoData"
          :disabled="loading"
          class="px-4 py-2 bg-green-500 text-white rounded hover:bg-green-600 disabled:opacity-50"
        >
          测试演示数据
        </button>
        <button 
          @click="clearResults"
          class="px-4 py-2 bg-gray-500 text-white rounded hover:bg-gray-600"
        >
          清空结果
        </button>
      </div>

      <!-- 测试结果 -->
      <div v-if="testResults.length > 0" class="mb-6">
        <h2 class="text-lg font-semibold mb-3">测试结果</h2>
        <div class="space-y-2 max-h-96 overflow-y-auto">
          <div 
            v-for="(result, index) in testResults" 
            :key="index"
            class="p-3 rounded border"
            :class="{
              'bg-green-50 border-green-200': result.type === 'success',
              'bg-red-50 border-red-200': result.type === 'error',
              'bg-blue-50 border-blue-200': result.type === 'info'
            }"
          >
            <div class="font-mono text-sm">{{ result.message }}</div>
            <div v-if="result.data" class="mt-2 text-xs text-gray-600">
              {{ JSON.stringify(result.data, null, 2) }}
            </div>
          </div>
        </div>
      </div>

      <!-- 患者列表 -->
      <div v-if="patients.length > 0" class="mb-6">
        <h2 class="text-lg font-semibold mb-3">患者列表 ({{ patients.length }} 个)</h2>
        <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          <div 
            v-for="patient in patients" 
            :key="patient.id"
            class="p-4 border rounded-lg hover:shadow-md transition-shadow"
          >
            <div class="flex items-center space-x-3 mb-2">
              <div class="w-10 h-10 bg-blue-500 rounded-full flex items-center justify-center text-white font-semibold">
                {{ patient.patient_name.charAt(0) }}
              </div>
              <div>
                <div class="font-semibold">{{ patient.patient_name }}</div>
                <div class="text-sm text-gray-600">{{ patient.patient_age }}岁 {{ patient.patient_gender === 'M' ? '男' : '女' }}</div>
              </div>
            </div>
            <div class="text-sm space-y-1">
              <div><span class="font-medium">科室:</span> {{ patient.department }}</div>
              <div><span class="font-medium">状态:</span> {{ patient.status }}</div>
              <div><span class="font-medium">入院:</span> {{ patient.admission_date }}</div>
              <div><span class="font-medium">病历长度:</span> {{ patient.content?.length || 0 }} 字符</div>
            </div>
          </div>
        </div>
      </div>

      <!-- 返回按钮 -->
      <div class="flex justify-center">
        <button 
          @click="goBack"
          class="px-6 py-3 bg-gray-500 text-white rounded-lg hover: bg-gray-600"
        >
          返回
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { getMedicalRecords, getDemoMedicalRecords } from '@/api/medical-records'
import type { MedicalRecord } from '@/types/medical-records'

const router = useRouter()
const loading = ref(false)
const patients = ref<MedicalRecord[]>([])
const testResults = ref<Array<{
  type: 'success' | 'error' | 'info'
  message: string
  data?: Record<string, unknown>
}>>([])

const addResult = (type: 'success' | 'error' | 'info', message: string, data?: unknown) => {
  testResults.value.push({
    type,
    message: `[${new Date().toLocaleTimeString()}] ${message}`,
    data
  })
}

const testDatabaseData = async () => {
  loading.value = true
  patients.value = []
  
  try {
    addResult('info', '开始测试数据库数据...')
    
    const response = await getMedicalRecords({
      limit: 50,
      offset: 0
    })
    
    addResult('info', `API响应:success=${response.success}, dataLength=${response.data?.length || 0}`)
    
    if (response.success && response.data) {
      patients.value = response.data
      addResult('success', `成功加载 ${response.data.length} 个患者`)
      
      // 显示前3个患者的详细信息
      response.data.slice(0, 3).forEach((patient, index) => {
        addResult('info', `患者${index + 1}: ${patient.patient_name} (${patient.patient_age}岁, ${patient.department})`)
      })
    } else {
      addResult('error', `加载失败: ${response.error || '未知错误'}`)
    }
  } catch (error: unknown) {
    addResult('error', `异常: ${error instanceof Error ? error.message : '未知错误'}`)
  } finally {
    loading.value = false
  }
}

const testDemoData = async () => {
  loading.value = true
  patients.value = []
  
  try {
    addResult('info', '开始测试演示数据...')
    
    const scenarios = ['complete', 'incomplete', 'inconsistent', 'irrational'] as const
    const allPatients: MedicalRecord[] = []

    for (const scenario of scenarios) {
      const response = await getDemoMedicalRecords(scenario)
      if (response.data) {
        allPatients.push(...response.data)
        addResult('info', `${scenario} 场景: ${response.data.length} 个患者`)
      }
    }

    patients.value = allPatients
    addResult('success', `成功加载 ${allPatients.length} 个演示患者`)
  } catch (error) {
    addResult('error', `异常: ${error instanceof Error ? (error as Error).message : '未知错误'}`)
  } finally {
    loading.value = false
  }
}

const clearResults = () => {
  testResults.value = []
  patients.value = []
}

const goBack = () => {
  router.back()
}
</script>
