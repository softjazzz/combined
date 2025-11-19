<template>
  <div class="simple-layout">
    <!-- 顶部导航栏 -->
    <header class="simple-header">
      <div class="header-content">
        <div class="header-left">
          <div class="logo-icon">
            <MedicineBoxOutlined />
          </div>
          <h1 class="title">泸县人民医院病案质控点测试</h1>
        </div>
      </div>
    </header>

    <!-- 主内容区域 -->
    <main class="simple-main">
      <div class="main-content">
        <router-view />
      </div>
    </main>

    <!-- 水印 -->
    <div class="watermark">演示环境</div>
  </div>
</template>

<script setup lang="ts">
import { ExperimentOutlined, MedicineBoxOutlined } from '@ant-design/icons-vue'
</script>

<style scoped lang="less">
.simple-layout {
  min-height: 100vh;
  background: linear-gradient(135deg, #f8fafc 0%, #e2e8f0 100%); /* Slate-50 to Slate-200 */
  position: relative;
  overflow-x: hidden;
}

.simple-header {
  background: rgba(255, 255, 255, 0.85);
  backdrop-filter: blur(12px);
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.05);
  border-bottom: 1px solid rgba(226, 232, 240, 0.8);
  position: sticky;
  top: 0;
  z-index: 100;
}

.header-content {
  max-width: 1400px;
  margin: 0 auto;
  padding: 12px 24px;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 16px;
}

.logo-icon {
  width: 40px;
  height: 40px;
  background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%); /* Blue-500 to Blue-600 */
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 22px;
  color: white;
  box-shadow: 0 4px 12px rgba(37, 99, 235, 0.25);
}

.title {
  color: #1e293b; /* Slate-800 */
  font-size: 18px;
  font-weight: 700;
  margin: 0;
  letter-spacing: -0.025em;
}

.header-right {
  .demo-tag {
    font-size: 14px;
    padding: 4px 12px;
    font-weight: 500;
  }
}

.simple-main {
  padding: 24px;
  min-height: calc(100vh - 65px);
}

.main-content {
  max-width: 1400px;
  margin: 0 auto;
}

.watermark {
  position: fixed;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%) rotate(-45deg);
  font-size: 120px;
  font-weight: bold;
  color: rgba(0, 0, 0, 0.02); /* Lighter watermark */
  z-index: 0;
  pointer-events: none;
  user-select: none;
  white-space: nowrap;
}
</style>
