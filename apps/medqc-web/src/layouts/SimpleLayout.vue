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
  background: linear-gradient(135deg, #f5f7fa 0%, #e3e7ed 100%);
  position: relative;
  overflow-x: hidden;
}

.simple-header {
  background: linear-gradient(135deg, #1890ff 0%, #096dd9 100%);
  box-shadow: 0 4px 12px rgba(24, 144, 255, 0.2);
  position: sticky;
  top: 0;
  z-index: 100;
}

.header-content {
  max-width: 1400px;
  margin: 0 auto;
  padding: 16px 24px;
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
  background: linear-gradient(135deg, rgba(255, 255, 255, 0.25) 0%, rgba(255, 255, 255, 0.1) 100%);
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 24px;
  color: white;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
}

.title {
  color: white;
  font-size: 20px;
  font-weight: 600;
  margin: 0;
  text-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
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
  min-height: calc(100vh - 72px);
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
  color: rgba(0, 0, 0, 0.03);
  z-index: 0;
  pointer-events: none;
  user-select: none;
  white-space: nowrap;
}
</style>
