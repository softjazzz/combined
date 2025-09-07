<template>
  <div class="basic-test">
    <a-card title="基础测试页面">
      <a-space direction="vertical" style="width: 100%">
        <a-alert message="页面加载成功！" type="success" />
        
        <a-button @click="testBasic" :loading="loading" type="primary">
          基础测试
        </a-button>
        
        <a-card size="small" title="测试结果">
          <pre>{{ result }}</pre>
        </a-card>
      </a-space>
    </a-card>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { message } from 'ant-design-vue'

const loading = ref(false)
const result = ref('等待测试...')

const testBasic = async () => {
  loading.value = true
  try {
    result.value = '基础测试成功！\n时间: ' + new Date().toLocaleString()
    message.success('测试成功')
  } catch (error) {
    result.value = `测试失败: ${error}`
    message.error('测试失败')
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.basic-test {
  padding: 20px;
}

pre {
  background: #f5f5f5;
  padding: 10px;
  border-radius: 4px;
}
</style>
