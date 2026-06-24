<template>
  <div class="test-three-column">
    <h1>三栏布局测试页面</h1>
    <p>这是一个测试页面，用于验证三栏布局组件是否正常工作。</p>
    
    <div style="margin: 20px 0;">
      <a-button @click="testComponents">
        测试组件导入
      </a-button>
      <a-button
        style="margin-left: 10px;"
        @click="testAPI"
      >
        测试API
      </a-button>
    </div>
    
    <div
      v-if="testResults.length > 0"
      style="margin-top: 20px;"
    >
      <h3>测试结果：</h3>
      <ul>
        <li
          v-for="result in testResults"
          :key="result.name"
        >
          <strong>{{ result.name }}:</strong> 
          <span :style="{ color: result.success ? 'green' : 'red' }">
            {{ result.success ? '✓ 成功' : '✗ 失败' }}
          </span>
          <span
            v-if="result.error"
            style="color: red; margin-left: 10px;"
          >
            {{ result.error }}
          </span>
        </li>
      </ul>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'

const testResults = ref<Array<{ name: string; success: boolean; error?: string }>>([])

const testComponents = async () => {
  testResults.value = []
  
  // 测试组件导入
  const tests = [
    {
      name: 'LayoutShell 组件',
      test: () => import('@/mr/components/LayoutShell.vue')
    },
    {
      name: 'NavTree 组件',
      test: () => import('@/mr/components/NavTree.vue')
    },
    {
      name: 'Toolbar 组件',
      test: () => import('@/mr/components/Toolbar.vue')
    },
    {
      name: 'ContextAside 组件',
      test: () => import('@/mr/components/ContextAside.vue')
    },
    {
      name: 'API 模块',
      test: () => import('@/mr/data/api')
    }
  ]
  
  for (const test of tests) {
    try {
      await test.test()
      testResults.value.push({ name: test.name, success: true })
    } catch (error) {
      testResults.value.push({ 
        name: test.name, 
        success: false, 
        error: error instanceof Error ? error.message : String(error)
      })
    }
  }
}

const testAPI = async () => {
  try {
    const response = await fetch('/api/medical-records/7fcb8e4c-3892-40c4-92f3-19bf5061aa41')
    if (response.ok) {
      const data = await response.json()
      testResults.value.push({ 
        name: 'API 患者数据', 
        success: true 
      })
      console.log('患者数据:', data)
    } else {
      testResults.value.push({ 
        name: 'API 患者数据', 
        success: false, 
        error: `HTTP ${response.status}` 
      })
    }
  } catch (error) {
    testResults.value.push({ 
      name: 'API 患者数据', 
      success: false, 
      error: error instanceof Error ? error.message : String(error)
    })
  }
  
  try {
    const response = await fetch('/api/medical-records/7fcb8e4c-3892-40c4-92f3-19bf5061aa41/documents')
    if (response.ok) {
      const data = await response.json()
      testResults.value.push({ 
        name: 'API 文档数据', 
        success: true 
      })
      console.log('文档数据:', data)
    } else {
      testResults.value.push({ 
        name: 'API 文档数据', 
        success: false, 
        error: `HTTP ${response.status}` 
      })
    }
  } catch (error) {
    testResults.value.push({ 
      name: 'API 文档数据', 
      success: false, 
      error: error instanceof Error ? error.message : String(error)
    })
  }
}
</script>

<style scoped>
.test-three-column {
  padding: 20px;
  max-width: 800px;
  margin: 0 auto;
}

h1 {
  color: #1890ff;
}

ul {
  list-style-type: none;
  padding: 0;
}

li {
  padding: 8px 0;
  border-bottom: 1px solid #f0f0f0;
}
</style>
