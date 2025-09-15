<template>
  <div class="validation-page">
    <div class="header">
      <h1>三栏布局验证页面</h1>
      <p>验证新的医疗记录详情页面三栏布局实现</p>
    </div>

    <div class="validation-sections">
      <!-- 功能验证 -->
      <a-card title="✅ 功能验证" class="section-card">
        <div class="feature-list">
          <div class="feature-item">
            <CheckCircleOutlined style="color: #52c41a;" />
            <span>三栏响应式布局（左导航、中内容、右上下文）</span>
          </div>
          <div class="feature-item">
            <CheckCircleOutlined style="color: #52c41a;" />
            <span>拖拽调整面板宽度</span>
          </div>
          <div class="feature-item">
            <CheckCircleOutlined style="color: #52c41a;" />
            <span>左右面板折叠功能</span>
          </div>
          <div class="feature-item">
            <CheckCircleOutlined style="color: #52c41a;" />
            <span>状态持久化（localStorage）</span>
          </div>
          <div class="feature-item">
            <CheckCircleOutlined style="color: #52c41a;" />
            <span>文档分类树导航</span>
          </div>
          <div class="feature-item">
            <CheckCircleOutlined style="color: #52c41a;" />
            <span>内容搜索和高亮</span>
          </div>
          <div class="feature-item">
            <CheckCircleOutlined style="color: #52c41a;" />
            <span>工具栏功能（字体、摘要、全屏等）</span>
          </div>
        </div>
      </a-card>

      <!-- 路由测试 -->
      <a-card title="🔗 路由测试" class="section-card">
        <div class="route-buttons">
          <a-button type="primary" @click="openNewLayout" size="large">
            <RocketOutlined />
            新三栏布局
          </a-button>
          <a-button @click="openLegacy" size="large">
            <HistoryOutlined />
            经典版本
          </a-button>
          <a-button @click="openSimple" size="large">
            <ExperimentOutlined />
            简化版本
          </a-button>
        </div>
      </a-card>

      <!-- API 状态 -->
      <a-card title="🔌 API 状态" class="section-card">
        <div class="api-status">
          <a-button @click="checkAPI" :loading="apiLoading">
            检查 API 状态
          </a-button>
          <div v-if="apiStatus" class="status-result">
            <div class="status-item">
              <span class="status-label">后端健康状态:</span>
              <a-tag :color="apiStatus.backend ? 'green' : 'red'">
                {{ apiStatus.backend ? '正常' : '异常' }}
              </a-tag>
            </div>
            <div class="status-item">
              <span class="status-label">患者数据 API:</span>
              <a-tag :color="apiStatus.patient ? 'green' : 'red'">
                {{ apiStatus.patient ? '正常' : '异常' }}
              </a-tag>
            </div>
            <div class="status-item">
              <span class="status-label">文档数据 API:</span>
              <a-tag :color="apiStatus.documents ? 'green' : 'red'">
                {{ apiStatus.documents ? '正常' : '异常' }}
              </a-tag>
            </div>
          </div>
        </div>
      </a-card>

      <!-- 实施说明 -->
      <a-card title="📋 实施说明" class="section-card">
        <div class="implementation-notes">
          <h3>已完成的工作：</h3>
          <ul>
            <li>✅ 备份原页面为 <code>MedicalRecordDetail.legacy.vue</code></li>
            <li>✅ 创建三栏布局组件 (<code>LayoutShell</code>, <code>NavTree</code>, <code>Toolbar</code>, <code>ContextAside</code>)</li>
            <li>✅ 实现数据层 API 封装</li>
            <li>✅ 创建新的主页面集成所有组件</li>
            <li>✅ 配置路由支持新旧版本切换</li>
          </ul>
          
          <h3>技术特性：</h3>
          <ul>
            <li>🎨 Vue 3 + TypeScript + Composition API</li>
            <li>🎯 Ant Design Vue 组件库</li>
            <li>📱 响应式设计，支持移动端</li>
            <li>💾 LocalStorage 状态持久化</li>
            <li>🔍 实时搜索和内容高亮</li>
            <li>🖱️ 拖拽调整面板宽度</li>
          </ul>

          <h3>回滚方案：</h3>
          <p>如果新页面出现问题，可以通过以下方式回滚：</p>
          <ul>
            <li>访问 <code>/medical-records/:id/legacy</code> 使用经典版本</li>
            <li>或者临时修改路由配置指向 legacy 组件</li>
          </ul>
        </div>
      </a-card>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { 
  CheckCircleOutlined, 
  RocketOutlined, 
  HistoryOutlined, 
  ExperimentOutlined 
} from '@ant-design/icons-vue'

const apiLoading = ref(false)
const apiStatus = ref<any>(null)

const recordId = '7fcb8e4c-3892-40c4-92f3-19bf5061aa41'

const openNewLayout = () => {
  window.open(`/medical-records/${recordId}`, '_blank')
}

const openLegacy = () => {
  window.open(`/medical-records/${recordId}/legacy`, '_blank')
}

const openSimple = () => {
  window.open(`/medical-records/${recordId}/simple`, '_blank')
}

const checkAPI = async () => {
  apiLoading.value = true
  const status = {
    backend: false,
    patient: false,
    documents: false
  }

  try {
    // 检查后端健康状态
    const healthResponse = await fetch('/api/health')
    status.backend = healthResponse.ok

    // 检查患者数据 API
    const patientResponse = await fetch(`/api/medical-records/${recordId}`)
    status.patient = patientResponse.ok

    // 检查文档数据 API
    const docsResponse = await fetch(`/api/medical-records/${recordId}/documents`)
    status.documents = docsResponse.ok

  } catch (error) {
    console.error('API 检查失败:', error)
  }

  apiStatus.value = status
  apiLoading.value = false
}
</script>

<style scoped>
.validation-page {
  padding: 24px;
  max-width: 1200px;
  margin: 0 auto;
  background: #f5f5f5;
  min-height: 100vh;
}

.header {
  text-align: center;
  margin-bottom: 32px;
  padding: 24px;
  background: white;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.1);
}

.header h1 {
  color: #1890ff;
  margin-bottom: 8px;
  font-size: 28px;
}

.header p {
  color: #666;
  font-size: 16px;
  margin: 0;
}

.validation-sections {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
  gap: 24px;
}

.section-card {
  box-shadow: 0 2px 8px rgba(0,0,0,0.1);
  border-radius: 8px;
}

.feature-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.feature-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 0;
}

.route-buttons {
  display: flex;
  gap: 16px;
  flex-wrap: wrap;
}

.route-buttons .ant-btn {
  flex: 1;
  min-width: 140px;
  height: 48px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
}

.api-status {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.status-result {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.status-item {
  display: flex;
  align-items: center;
  gap: 12px;
}

.status-label {
  font-weight: 500;
  min-width: 120px;
}

.implementation-notes h3 {
  color: #333;
  margin: 16px 0 8px 0;
  font-size: 16px;
}

.implementation-notes ul {
  margin: 8px 0 16px 0;
  padding-left: 20px;
}

.implementation-notes li {
  margin: 4px 0;
  line-height: 1.6;
}

.implementation-notes code {
  background: #f5f5f5;
  padding: 2px 6px;
  border-radius: 3px;
  font-family: 'Monaco', 'Menlo', monospace;
  font-size: 13px;
}

@media (max-width: 768px) {
  .validation-sections {
    grid-template-columns: 1fr;
  }

  .route-buttons {
    flex-direction: column;
  }

  .route-buttons .ant-btn {
    flex: none;
  }
}
</style>
