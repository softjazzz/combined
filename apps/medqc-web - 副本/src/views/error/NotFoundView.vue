<script setup lang="ts">
import { useRouter } from 'vue-router'

const router = useRouter()

const goHome = () => {
  router.push('/dashboard')
}

const goBack = () => {
  router.back()
}
</script>

<template>
  <div class="not-found-container">
    <a-result
      status="404"
      title="404"
      sub-title="抱歉，您访问的页面不存在"
      class="not-found-result"
    >
      <template #extra>
        <div class="flex justify-center space-x-4">
          <a-button
            type="primary"
            @click="goHome"
          >
            <HomeOutlined />
            返回首页
          </a-button>
          <a-button @click="goBack">
            <ArrowLeftOutlined />
            返回上页
          </a-button>
        </div>
      </template>
    </a-result>

    <!-- 额外信息 -->
    <div class="error-info">
      <a-card
        class="max-w-md mx-auto"
        title="可能的原因"
      >
        <ul class="list-disc list-inside space-y-2 text-gray-600">
          <li>您输入的网址有误</li>
          <li>页面已被删除或移动</li>
          <li>您没有访问权限</li>
          <li>系统正在维护中</li>
        </ul>
      </a-card>
    </div>

    <!-- 快捷导航 -->
    <div class="quick-nav mt-8">
      <h3 class="text-center text-lg font-semibold mb-4 text-gray-700">
        快捷导航
      </h3>
      <div class="grid grid-cols-2 md:grid-cols-4 gap-4 max-w-2xl mx-auto">
        <a-card 
          class="nav-card cursor-pointer hover:shadow-md transition-shadow"
          @click="router.push('/dashboard')"
        >
          <div class="text-center">
            <DashboardOutlined class="text-2xl text-blue-500 mb-2" />
            <p class="text-sm">
              仪表板
            </p>
          </div>
        </a-card>
        
        <a-card 
          class="nav-card cursor-pointer hover:shadow-md transition-shadow"
          @click="router.push('/dashboard/records')"
        >
          <div class="text-center">
            <FileTextOutlined class="text-2xl text-green-500 mb-2" />
            <p class="text-sm">
              病案管理
            </p>
          </div>
        </a-card>
        
        <a-card 
          class="nav-card cursor-pointer hover:shadow-md transition-shadow"
          @click="router.push('/dashboard/qc')"
        >
          <div class="text-center">
            <CheckCircleOutlined class="text-2xl text-purple-500 mb-2" />
            <p class="text-sm">
              质控分析
            </p>
          </div>
        </a-card>
        
        <a-card 
          class="nav-card cursor-pointer hover:shadow-md transition-shadow"
          @click="router.push('/dashboard/settings')"
        >
          <div class="text-center">
            <SettingOutlined class="text-2xl text-orange-500 mb-2" />
            <p class="text-sm">
              系统设置
            </p>
          </div>
        </a-card>
      </div>
    </div>
  </div>
</template>

<style scoped>
.not-found-container {
  min-height: 100vh;
  background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
  padding: 2rem;
  display: flex;
  flex-direction: column;
  justify-content: center;
}

.not-found-result {
  background: rgba(255, 255, 255, 0.9);
  border-radius: 12px;
  padding: 2rem;
  backdrop-filter: blur(10px);
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
}

.error-info {
  margin-top: 2rem;
}

.nav-card {
  border-radius: 8px;
  border: 1px solid #e8e8e8;
}

.nav-card:hover {
  border-color: #1890ff;
  transform: translateY(-2px);
}

@media (max-width: 768px) {
  .not-found-container {
    padding: 1rem;
  }
  
  .quick-nav .grid {
    grid-template-columns: repeat(2, 1fr);
    gap: 0.75rem;
  }
}
</style> 